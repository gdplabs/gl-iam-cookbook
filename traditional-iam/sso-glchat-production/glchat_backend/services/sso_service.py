"""SSO orchestration — ties HMAC validation → provisioning → session.

This is the only meaningful business-logic module in GLChat's SSO surface:
everything else is either pure SDK calls or transport glue. It enforces the
`max_users` and `allowed_roles` partner restrictions that the SDK stores but
does not itself enforce.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import HTTPException

from gl_iam import IAMGateway
from gl_iam.core.types import UserCreateInput
from gl_iam.core.types.auth import ExternalIdentity
from gl_iam.core.types.audit import AuditEventType, AuditSeverity
from gl_iam.core.types.sso import SSOPartner

from glchat_backend import audit
from glchat_backend.pretty_log import C, app, banner, done, err, kv, sdk, warn
from glchat_backend.services.nonce_store import NonceStore
from glchat_backend.services.token_store import OneTimeTokenStore


class SSOService:
    def __init__(
        self,
        gateway: IAMGateway,
        token_store: OneTimeTokenStore,
        nonce_store: NonceStore,
        organization_id: str,
        timestamp_tolerance_seconds: int,
    ):
        self._gateway = gateway
        self._tokens = token_store
        self._nonces = nonce_store
        self._org = organization_id
        self._tolerance = timestamp_tolerance_seconds

    async def issue_token(
        self,
        *,
        consumer_key: str,
        signature: str,
        timestamp: str,
        nonce: str,
        payload: str,
        source_ip: str | None,
    ) -> str:
        banner(
            "POST /api/v1/sso/token  ←  partner backend (server-to-server)",
            color=C.CYAN,
            subtitle="Phase 1: validate HMAC assertion → mint a one-time SSO token",
        )
        kv("consumer_key", consumer_key)
        kv("source_ip", source_ip or "—")
        kv("timestamp (claimed)", timestamp)
        kv("nonce", f"{nonce[:16]}…")
        kv("signature", f"{signature[:24]}…")
        kv("payload (opaque)", payload[:80] + ("…" if len(payload) > 80 else ""))

        try:
            data = json.loads(payload)
        except ValueError:
            err("Invalid JSON payload")
            raise HTTPException(400, "Invalid JSON payload")

        email = data.get("email")
        if not email:
            err("payload.email is required")
            raise HTTPException(400, "payload.email is required")
        kv("→ extracted email", email, color=C.GREEN)

        # Replay protection: nonce must be fresh
        if not await self._nonces.claim(consumer_key, nonce):
            app("Nonce already seen (replay)", f"consumer_key={consumer_key} nonce={nonce[:12]}…", ok=False)
            audit.emit(
                event_type=AuditEventType.TOKEN_VALIDATION_FAILED,
                severity=AuditSeverity.WARNING,
                sso_event="signature_replay",
                message="Nonce already seen",
                error_code="REPLAY",
                consumer_key=consumer_key,
                nonce=nonce,
            )
            raise HTTPException(401, "Replay detected")
        app("Nonce is fresh (Redis SETNX)", f"TTL={self._tolerance * 2}s for de-dup")

        # SDK: HMAC sig + IP allowlist + email domain + timestamp tolerance
        sdk("PartnerRegistryProvider.validate_partner_signature()",
            "HMAC-SHA256 + IP allowlist (CIDR) + email-domain allowlist + timestamp tolerance")
        result = await self._gateway.partner_registry.validate_partner_signature(
            consumer_key=consumer_key,
            signature=signature,
            payload=payload,
            timestamp=timestamp,
            email=email,
            source_ip=source_ip,
            tolerance_seconds=self._tolerance,
        )
        if result.is_err:
            sdk("validate_partner_signature FAILED",
                f"{result.error.code.value}: {result.error.message}", ok=False)
            audit.emit(
                event_type=AuditEventType.TOKEN_VALIDATION_FAILED,
                severity=AuditSeverity.WARNING,
                sso_event="signature_failed",
                message=result.error.message,
                error_code=result.error.code.value,
                consumer_key=consumer_key,
                source_ip=source_ip,
            )
            raise HTTPException(401, result.error.message)

        partner: SSOPartner = result.value
        sdk("Partner identity verified",
            f"partner={partner.partner_name} id={partner.id} allowed_domains={partner.allowed_email_domains}")

        token = await self._tokens.issue(
            {
                "partner_id": partner.id,
                "partner_name": partner.partner_name,
                "allowed_roles": partner.allowed_roles,
                "max_users": partner.max_users,
                "user": data,
            }
        )
        app("One-time token issued (Redis SET EX)", f"{token[:18]}… TTL=60s, consumable ONCE via GETDEL")
        audit.emit(
            event_type=AuditEventType.TOKEN_ISSUED,
            sso_event="sso_token_issued",
            message=f"One-time token issued for {partner.partner_name}/{email}",
            resource_id=partner.id,
            consumer_key=consumer_key,
            email=email,
        )
        done("Returning SSO token to partner (HTTP 200)")
        return token

    async def exchange_token(self, token: str) -> tuple[str, str]:
        """Consume one-time token → JWT. Returns (access_token, token_type)."""
        banner(
            "POST /api/v1/sso/authenticate  ←  widget (browser, cross-origin fetch)",
            color=C.GREEN,
            subtitle="Phase 2: consume one-time token → JIT provision user → issue session JWT",
        )
        kv("presented token", f"{token[:18]}…")

        data = await self._tokens.consume(token)
        if data is None:
            app("Token consume FAILED (Redis GETDEL returned nil)",
                "invalid, expired (>60s), or already used", ok=False)
            audit.emit(
                event_type=AuditEventType.TOKEN_VALIDATION_FAILED,
                severity=AuditSeverity.WARNING,
                sso_event="token_consume_failed",
                message="Invalid, expired, or replayed one-time token",
                error_code="INVALID_TOKEN",
            )
            raise HTTPException(401, "Invalid or expired token")

        user_info = data["user"]
        email = user_info["email"]
        partner_id = data["partner_id"]
        partner_name = data["partner_name"]
        allowed_roles: list[str] | None = data.get("allowed_roles")
        max_users: int | None = data.get("max_users")

        app("Token consumed (Redis GETDEL, atomic one-shot)", f"email={email} partner={partner_name}")
        audit.emit(
            event_type=AuditEventType.TOKEN_REFRESHED,
            sso_event="sso_token_consumed",
            message=f"One-time token consumed by widget for {email}",
            resource_id=partner_id,
        )

        # Enforce partner role restrictions (app-layer)
        requested_role = user_info.get("role", "member")
        kv("requested role", requested_role)
        kv("partner.allowed_roles", allowed_roles if allowed_roles is not None else "— (unrestricted)")
        kv("partner.max_users cap", max_users if max_users is not None else "— (unrestricted)")
        if allowed_roles is not None and requested_role not in allowed_roles:
            audit.emit(
                event_type=AuditEventType.LOGIN_ERROR,
                severity=AuditSeverity.ERROR,
                sso_event="role_disallowed",
                message=f"Role '{requested_role}' not in partner.allowed_roles {allowed_roles}",
                error_code="ROLE_DISALLOWED",
                resource_id=partner_id,
            )
            raise HTTPException(403, f"Role '{requested_role}' not permitted by partner")

        external = ExternalIdentity(
            provider_type="sso",
            provider_id=partner_name,
            external_id=user_info.get("external_id", email),
            email=email,
            display_name=user_info.get("display_name"),
            username=user_info.get("username"),
            first_name=user_info.get("first_name"),
            last_name=user_info.get("last_name"),
            groups=[],
            attributes={"partner_id": partner_id},
            authenticated_at=datetime.now(timezone.utc),
        )

        sdk("UserStore.get_user_by_external_identity()",
            f"looking up provider_id='{partner_name}' external_id='{external.external_id}'")
        user = await self._gateway.user_store.get_user_by_external_identity(
            external_identity=external,
            organization_id=self._org,
        )

        if user is None:
            app("First-time SSO user — will JIT-provision")
            # Enforce partner.max_users (app-layer) — count only partner-linked users
            if max_users is not None:
                count = await self._count_partner_users(partner_id)
                if count >= max_users:
                    audit.emit(
                        event_type=AuditEventType.LOGIN_ERROR,
                        severity=AuditSeverity.ERROR,
                        sso_event="max_users_exceeded",
                        message=f"Partner user cap reached ({count}/{max_users})",
                        error_code="MAX_USERS",
                        resource_id=partner_id,
                    )
                    raise HTTPException(403, "Partner user cap reached")

            sdk("UserStore.create_user()", f"creating user {email} in org={self._org}")
            user = await self._gateway.user_store.create_user(
                UserCreateInput(
                    email=email,
                    display_name=user_info.get("display_name") or email.split("@")[0],
                ),
                organization_id=self._org,
            )
            sdk("UserStore.link_external_identity()", f"user.id={user.id} ↔ partner external_id={external.external_id}")
            await self._gateway.user_store.link_external_identity(
                user_id=user.id,
                external_identity=external,
                organization_id=self._org,
            )
            app("User JIT-provisioned", f"user.id={user.id} email={email}")
            audit.emit(
                event_type=AuditEventType.JIT_PROVISION,
                sso_event="user_jit_provisioned",
                message=f"JIT-provisioned {email} from {partner_name}",
                user_id=user.id,
                organization_id=self._org,
                resource_id=partner_id,
            )
        else:
            sdk("User found (returning SSO user)", f"user.id={user.id} email={user.email}")

        sdk("SessionProvider.create_session()",
            f"user.id={user.id} metadata={{'auth_method':'sso','partner':'{partner_name}'}}")
        session_token = await self._gateway.session_provider.create_session(
            user=user,
            organization_id=self._org,
            metadata={"auth_method": "sso", "partner": partner_name, "partner_id": partner_id},
        )
        app("Session JWT issued", f"{session_token.access_token[:22]}… token_type={session_token.token_type}")
        audit.emit(
            event_type=AuditEventType.SESSION_CREATED,
            sso_event="sso_session_created",
            message=f"SSO session created for {email}",
            user_id=user.id,
            organization_id=self._org,
            resource_id=partner_id,
        )
        done(f"SSO complete — widget can now use Bearer {session_token.access_token[:14]}… to call GLChat APIs")

        return session_token.access_token, session_token.token_type

    async def _count_partner_users(self, partner_id: str) -> int:
        """Count users JIT-provisioned by this partner via audit events.

        The audit trail records a `JIT_PROVISION` event per newly provisioned
        user with `resource_id=partner_id`. Counting those events gives us a
        monotonic provisioning count. For a cookbook this is the simplest
        persistent counter; in production add a dedicated `partner_users`
        index or a `user.attributes.partner_id` column for O(1) lookup.
        """
        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import AsyncSession

        from gl_iam.providers.postgresql import AuditEventModel

        provider = self._gateway.user_store  # PostgreSQLProvider is multi-proto
        async with AsyncSession(provider.engine) as session:
            stmt = select(func.count()).select_from(AuditEventModel).where(
                AuditEventModel.resource_id == partner_id,
                AuditEventModel.event_type == AuditEventType.JIT_PROVISION.value,
            )
            return (await session.execute(stmt)).scalar() or 0
