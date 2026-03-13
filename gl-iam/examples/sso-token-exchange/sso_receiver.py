"""SSO Token Exchange receiver — GLChat-side FastAPI application.

This example demonstrates IdP-Initiated SSO using GL-IAM's PartnerRegistryProvider.
The flow has two phases:

1. Server-to-server: Partner sends HMAC-signed request -> GL-IAM validates signature
   -> app generates a one-time token (stored in-memory, use Redis in production).
2. Client-side exchange: Widget sends one-time token -> app consumes it ->
   GL-IAM provisions user (JIT) and creates a session -> returns JWT.

Each endpoint is annotated with whether it uses GL-IAM SDK calls or application code.
"""

import hashlib
import hmac as hmac_mod
import logging
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import IAMGateway, User
from gl_iam.core.types import UserCreateInput
from gl_iam.core.types.auth import ExternalIdentity
from gl_iam.core.types.sso import SSOMode, SSOPartnerCreate, SSOUserProvisioning
from gl_iam.fastapi import get_current_user, get_iam_gateway, set_iam_gateway
from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider

load_dotenv()

# Configure logging with clear formatting
logging.basicConfig(
    level=logging.INFO,
    format="\n%(message)s",
)
logger = logging.getLogger("sso-token-exchange")


def log_step(step: str, description: str):
    """Log a clearly formatted step with explanation."""
    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ 🔹 %s\n"
        "│\n"
        "│   %s\n"
        "└─────────────────────────────────────────────────────────────────",
        step,
        description.replace("\n", "\n│   "),
    )


def log_gliam(action: str, detail: str = ""):
    """Log a GL-IAM SDK operation."""
    msg = f"│   [GL-IAM] {action}"
    if detail:
        msg += f" → {detail}"
    logger.info(msg)


def log_app(action: str, detail: str = ""):
    """Log an application-level operation."""
    msg = f"│   [APP]    {action}"
    if detail:
        msg += f" → {detail}"
    logger.info(msg)


# ============================================================================
# One-Time Token Store (Application Code)
# ============================================================================
# In production, replace this with Redis (TTL-based expiry, atomic consume).
# This in-memory dict is for demonstration purposes only.
_one_time_tokens: dict[str, dict] = {}

SSO_TOKEN_TTL = int(os.getenv("SSO_TOKEN_TTL_SECONDS", "60"))


def _store_token(token: str, user_data: dict) -> None:
    """Store a one-time token with expiry. Replace with Redis SET EX in production."""
    _one_time_tokens[token] = {
        "user_data": user_data,
        "expires_at": time.time() + SSO_TOKEN_TTL,
    }


def _consume_token(token: str) -> dict | None:
    """Consume a one-time token (atomic pop). Replace with Redis GETDEL in production."""
    entry = _one_time_tokens.pop(token, None)
    if entry is None:
        return None
    if time.time() > entry["expires_at"]:
        return None  # Expired
    return entry["user_data"]


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize GL-IAM gateway with PostgreSQL provider + partner registry."""
    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    logger.info(
        "=" * 70 + "\n"
        "  SSO Token Exchange Receiver — Starting up\n"
        "  (GLChat backend using GL-IAM with PartnerRegistryProvider)\n"
        "=" * 70
    )

    # --- GL-IAM ---
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        encryption_key=os.getenv("ENCRYPTION_KEY"),
        enable_auth_hosting=True,
        enable_partner_registry=True,
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)
    gateway = IAMGateway(
        auth_provider=provider,
        user_store=provider,
        session_provider=provider,
        organization_provider=provider,
        partner_registry=provider,
    )
    set_iam_gateway(gateway, default_organization_id=default_org_id)
    # --- End GL-IAM ---

    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ ✅ GL-IAM gateway initialized\n"
        "│\n"
        "│   Provider:          PostgreSQL\n"
        "│   Organization:      %s\n"
        "│   Auth hosting:      enabled\n"
        "│   Partner registry:  enabled (PartnerRegistryProvider)\n"
        "│   Token TTL:         %ds\n"
        "│\n"
        "│   Ready to receive SSO token exchange requests.\n"
        "│   Partners must register first (POST /admin/partners),\n"
        "│   then use HMAC-signed requests to generate one-time tokens.\n"
        "└─────────────────────────────────────────────────────────────────",
        default_org_id,
        SSO_TOKEN_TTL,
    )

    yield
    await provider.close()
    logger.info("GL-IAM gateway shut down.")


app = FastAPI(title="SSO Token Exchange Receiver", lifespan=lifespan)


# ============================================================================
# Request/Response Models (Application Code)
# ============================================================================
class SSOTokenRequest(BaseModel):
    """Request from the partner to generate a one-time token."""

    consumer_key: str
    signature: str
    timestamp: str
    payload: str  # JSON string containing user info


class SSOTokenResponse(BaseModel):
    """Response containing the one-time token."""

    token: str
    expires_in: int


class SSOAuthenticateRequest(BaseModel):
    """Request from the partner widget to exchange a one-time token for a JWT."""

    token: str


class TokenResponse(BaseModel):
    """Response containing the session JWT."""

    access_token: str
    token_type: str


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    display_name: str | None


class PartnerCreateRequest(BaseModel):
    """Request to register a new SSO partner."""

    partner_name: str
    allowed_origins: list[str] = []
    sso_mode: str = "idp_initiated"
    user_provisioning: str = "jit"
    metadata: dict | None = None


class PartnerResponse(BaseModel):
    """Response after registering a partner (includes secret shown once)."""

    id: str
    partner_name: str
    consumer_key: str
    consumer_secret: str  # Shown only once!
    is_active: bool


class PartnerListItem(BaseModel):
    """Partner summary for list endpoints."""

    id: str
    partner_name: str
    consumer_key: str
    is_active: bool
    sso_mode: str
    created_at: str | None


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Health check endpoint.

    Uses GL-IAM's partner registry health_check() to verify database connectivity.
    """
    # --- GL-IAM ---
    gateway = get_iam_gateway()
    healthy = await gateway.partner_registry.health_check()
    # --- End GL-IAM ---

    logger.info("Health check requested → %s", "healthy" if healthy else "unhealthy")
    return {"status": "healthy" if healthy else "unhealthy"}


# ============================================================================
# Admin Endpoints — Partner Management (GL-IAM)
# ============================================================================
@app.post("/admin/partners", response_model=PartnerResponse)
async def register_partner(request: PartnerCreateRequest):
    """Register a new SSO partner.

    In production, protect this with admin authentication.
    Returns consumer_key and consumer_secret (shown only once!).
    """
    log_step(
        "POST /admin/partners — Register New SSO Partner",
        "A new external partner wants to integrate SSO with our application.\n"
        "GL-IAM's PartnerRegistryProvider will:\n"
        "  1. Generate a unique consumer_key (public identifier)\n"
        "  2. Generate a consumer_secret (for HMAC signing)\n"
        "  3. Encrypt and store the secret in PostgreSQL\n"
        "  4. Return both credentials (secret shown only once!)\n\n"
        f"Partner: {request.partner_name}\n"
        f"SSO Mode: {request.sso_mode}\n"
        f"User Provisioning: {request.user_provisioning}",
    )

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # --- GL-IAM ---
    log_gliam("register_partner()", f"Registering '{request.partner_name}' in org={org_id}")

    result = await gateway.partner_registry.register_partner(
        SSOPartnerCreate(
            org_id=org_id,
            partner_name=request.partner_name,
            allowed_origins=request.allowed_origins,
            sso_mode=SSOMode(request.sso_mode),
            user_provisioning=SSOUserProvisioning(request.user_provisioning),
            metadata=request.metadata,
        )
    )
    # --- End GL-IAM ---

    if result.is_err:
        log_gliam("Registration FAILED", result.error.message)
        raise HTTPException(status_code=400, detail=result.error.message)

    reg = result.value
    log_gliam("Registration SUCCESS", f"partner_id={reg.partner.id}, consumer_key={reg.consumer_key}")

    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ ✅ Partner Registered Successfully\n"
        "│\n"
        "│   Partner:        %s\n"
        "│   Consumer Key:   %s\n"
        "│   Consumer Secret: %s... (SAVE THIS — shown only once!)\n"
        "│   Status:         %s\n"
        "│\n"
        "│   The partner must store the consumer_secret securely.\n"
        "│   It will be used to compute HMAC signatures for SSO requests.\n"
        "└─────────────────────────────────────────────────────────────────",
        reg.partner.partner_name,
        reg.consumer_key,
        reg.consumer_secret[:8],
        "active" if reg.partner.is_active else "inactive",
    )

    return PartnerResponse(
        id=reg.partner.id,
        partner_name=reg.partner.partner_name,
        consumer_key=reg.consumer_key,
        consumer_secret=reg.consumer_secret,
        is_active=reg.partner.is_active,
    )


@app.get("/admin/partners", response_model=list[PartnerListItem])
async def list_partners():
    """List all registered SSO partners.

    In production, protect this with admin authentication.
    """
    log_step(
        "GET /admin/partners — List Registered Partners",
        "Listing all SSO partners registered in the system.\n"
        "This is useful for admin dashboards to see which partners\n"
        "are active and when they were registered.",
    )

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # --- GL-IAM ---
    log_gliam("list_partners()", f"Querying partners for org={org_id}")
    result = await gateway.partner_registry.list_partners(organization_id=org_id)
    # --- End GL-IAM ---

    if result.is_err:
        raise HTTPException(status_code=500, detail=result.error.message)

    partners = result.value
    log_gliam("Query result", f"Found {len(partners)} partner(s)")
    for p in partners:
        log_gliam(f"  Partner: {p.partner_name}", f"key={p.consumer_key}, active={p.is_active}")

    return [
        PartnerListItem(
            id=p.id,
            partner_name=p.partner_name,
            consumer_key=p.consumer_key,
            is_active=p.is_active,
            sso_mode=p.sso_mode.value,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in partners
    ]


@app.post("/admin/partners/{partner_id}/rotate", response_model=PartnerResponse)
async def rotate_secret(partner_id: str):
    """Rotate a partner's consumer secret.

    In production, protect this with admin authentication.
    Returns the new consumer_secret (shown only once!).
    """
    log_step(
        f"POST /admin/partners/{partner_id}/rotate — Rotate Consumer Secret",
        "Rotating a partner's consumer secret. The old secret is invalidated\n"
        "immediately. The partner must update their configuration with the\n"
        "new secret to continue sending SSO requests.",
    )

    gateway = get_iam_gateway()

    # --- GL-IAM ---
    log_gliam("rotate_consumer_secret()", f"partner_id={partner_id}")
    result = await gateway.partner_registry.rotate_consumer_secret(partner_id)
    # --- End GL-IAM ---

    if result.is_err:
        log_gliam("Rotation FAILED", result.error.message)
        raise HTTPException(status_code=404, detail=result.error.message)

    reg = result.value
    log_gliam("Rotation SUCCESS", f"New consumer_key={reg.consumer_key}")

    return PartnerResponse(
        id=reg.partner.id,
        partner_name=reg.partner.partner_name,
        consumer_key=reg.consumer_key,
        consumer_secret=reg.consumer_secret,
        is_active=reg.partner.is_active,
    )


# ============================================================================
# SSO Flow Endpoints
# ============================================================================
@app.post("/api/v1/sso/token", response_model=SSOTokenResponse)
async def sso_generate_token(request: SSOTokenRequest):
    """Phase 1: Validate partner HMAC signature and generate a one-time token.

    This endpoint is called server-to-server by the partner system.
    - GL-IAM validates the HMAC-SHA256 signature against the registered partner.
    - Application code generates and stores a one-time token.
    """
    # ── Step A: Validate HMAC Signature ─────────────────────────────
    log_step(
        "POST /api/v1/sso/token — Phase 1: Server-to-Server Token Request",
        "A partner backend is requesting a one-time SSO token.\n"
        "This is a SERVER-TO-SERVER call (the user's browser is not involved).\n\n"
        "The partner sent:\n"
        f"  consumer_key: {request.consumer_key}\n"
        f"  timestamp:    {request.timestamp}\n"
        f"  signature:    {request.signature[:32]}...\n"
        f"  payload:      {request.payload[:50]}...\n\n"
        "Now we use GL-IAM to validate the HMAC signature:\n"
        "  1. Look up the partner by consumer_key\n"
        "  2. Decrypt the stored consumer_secret\n"
        "  3. Recompute HMAC-SHA256(secret, 'timestamp|key|payload')\n"
        "  4. Constant-time compare with the provided signature",
    )

    gateway = get_iam_gateway()

    # --- GL-IAM: Validate the partner's HMAC signature ---
    log_gliam(
        "validate_partner_signature()",
        f"consumer_key={request.consumer_key}",
    )

    result = await gateway.partner_registry.validate_partner_signature(
        consumer_key=request.consumer_key,
        signature=request.signature,
        payload=request.payload,
        timestamp=request.timestamp,
    )

    if result.is_err:
        log_gliam("Signature validation FAILED", result.error.message)
        raise HTTPException(status_code=401, detail=result.error.message)

    partner = result.value
    log_gliam(
        "Signature validation PASSED",
        f"partner={partner.partner_name}, id={partner.id}",
    )
    # --- End GL-IAM ---

    # ── Step B: Generate One-Time Token ─────────────────────────────
    log_step(
        "Generate One-Time Token",
        "The partner's identity is verified. Now we generate a one-time\n"
        "token that the partner will pass to the GLChat widget.\n\n"
        "This is APPLICATION CODE (not GL-IAM) — in production, use Redis:\n"
        "  SET sso:<token> <user_data> EX 60  (store with 60s TTL)\n"
        "  GETDEL sso:<token>                  (atomic consume)",
    )

    # --- Application code: Generate and store one-time token ---
    import json

    try:
        user_data = json.loads(request.payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    user_data["partner_id"] = partner.id
    user_data["partner_name"] = partner.partner_name

    one_time_token = secrets.token_urlsafe(32)
    _store_token(one_time_token, user_data)
    # --- End application code ---

    log_app("Generated one-time token", f"{one_time_token[:16]}... (TTL: {SSO_TOKEN_TTL}s)")
    log_app("Stored in memory", f"Total active tokens: {len(_one_time_tokens)}")

    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ ✅ One-Time Token Generated\n"
        "│\n"
        "│   Partner:  %s\n"
        "│   User:     %s\n"
        "│   Token:    %s... (expires in %ds)\n"
        "│\n"
        "│   The partner will now pass this token to the GLChat widget\n"
        "│   via iframe URL: glchat.com/widget?sso_token=<token>\n"
        "│   The widget will exchange it for a JWT session (Phase 2).\n"
        "└─────────────────────────────────────────────────────────────────",
        partner.partner_name,
        user_data.get("email", "unknown"),
        one_time_token[:16],
        SSO_TOKEN_TTL,
    )

    return SSOTokenResponse(token=one_time_token, expires_in=SSO_TOKEN_TTL)


@app.post("/api/v1/sso/authenticate", response_model=TokenResponse)
async def sso_authenticate(request: SSOAuthenticateRequest):
    """Phase 2: Exchange one-time token for a JWT session.

    This endpoint is called by the partner's client-side widget.
    - Application code consumes the one-time token.
    - GL-IAM provisions the user (JIT) and creates a session.
    """
    # ── Step A: Consume One-Time Token ──────────────────────────────
    log_step(
        "POST /api/v1/sso/authenticate — Phase 2: Token Exchange",
        "The GLChat widget (iframe) is exchanging a one-time token for\n"
        "a JWT session. This is the CLIENT-SIDE part of the SSO flow.\n\n"
        f"Token: {request.token[:16]}...\n\n"
        "First, we consume the one-time token (it can only be used ONCE).\n"
        "If someone tries to replay this token, it will be rejected.",
    )

    # --- Application code: Consume the one-time token ---
    log_app("Consuming one-time token", f"{request.token[:16]}...")

    user_data = _consume_token(request.token)
    if user_data is None:
        log_app("Token consumption FAILED", "Token invalid, expired, or already used")
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    log_app(
        "Token consumed successfully",
        f"email={user_data.get('email')}, partner={user_data.get('partner_name')}",
    )
    # --- End application code ---

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    email = user_data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Token payload missing 'email'")

    # ── Step B: JIT User Provisioning ───────────────────────────────
    log_step(
        "JIT User Provisioning",
        "Now we use GL-IAM to find or create a GLChat user for this\n"
        "external identity. If the user has logged in before via SSO,\n"
        "we find their existing account. Otherwise, we create a new one.\n\n"
        "This is called 'Just-In-Time' (JIT) provisioning — no need to\n"
        "pre-create user accounts in GLChat.",
    )

    # --- GL-IAM: JIT user provisioning ---
    # Check if user already exists via external identity
    external_identity = ExternalIdentity(
        provider_type="sso",
        provider_id=user_data.get("partner_name", "unknown"),
        external_id=user_data.get("external_id", email),
        email=email,
        display_name=user_data.get("display_name"),
        username=user_data.get("username"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        groups=[],
        attributes={"partner_id": user_data.get("partner_id", "")},
        authenticated_at=datetime.now(timezone.utc),
    )

    log_gliam(
        "get_user_by_external_identity()",
        f"Looking up external_id={user_data.get('external_id')}, partner={user_data.get('partner_name')}",
    )

    existing_user = await gateway.user_store.get_user_by_external_identity(
        external_identity=external_identity,
        organization_id=org_id,
    )

    if existing_user:
        user = existing_user
        log_gliam("User found", f"id={user.id}, email={user.email} (returning user)")
    else:
        log_gliam("User NOT found", "First-time SSO login — creating new GLChat account")

        # Create new user (JIT provisioning)
        user = await gateway.user_store.create_user(
            UserCreateInput(
                email=email,
                display_name=user_data.get("display_name", email.split("@")[0]),
            ),
            organization_id=org_id,
        )
        log_gliam("create_user()", f"Created user id={user.id}, email={user.email}")

        # Link external identity for future lookups
        await gateway.user_store.link_external_identity(
            user_id=user.id,
            external_identity=external_identity,
            organization_id=org_id,
        )
        log_gliam(
            "link_external_identity()",
            f"Linked external_id={user_data.get('external_id')} → user_id={user.id}",
        )

    # ── Step C: Create Session ──────────────────────────────────────
    log_step(
        "Create GLChat Session",
        "The user is now verified and provisioned in GLChat.\n"
        "GL-IAM creates a session JWT that the widget will use\n"
        "to access protected GLChat APIs.",
    )

    # Create session (JWT)
    log_gliam("create_session()", f"Creating session for user_id={user.id}")

    token = await gateway.session_provider.create_session(
        user=user,
        organization_id=org_id,
        metadata={"auth_method": "sso", "partner": user_data.get("partner_name")},
    )
    # --- End GL-IAM ---

    log_gliam("Session created", f"token_type={token.token_type}, token={token.access_token[:20]}...")

    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ ✅ SSO Token Exchange Complete\n"
        "│\n"
        "│   Partner:     %s\n"
        "│   External ID: %s\n"
        "│   Email:       %s\n"
        "│   GLChat User: %s\n"
        "│   Session:     %s...\n"
        "│\n"
        "│   The widget can now use this session JWT to access GLChat APIs.\n"
        "└─────────────────────────────────────────────────────────────────",
        user_data.get("partner_name"),
        user_data.get("external_id"),
        email,
        user.id,
        token.access_token[:20],
    )

    return TokenResponse(
        access_token=token.access_token,
        token_type=token.token_type,
    )


# ============================================================================
# Protected Endpoints
# ============================================================================
@app.get("/api/v1/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile.

    Uses GL-IAM's get_current_user dependency to validate the JWT.
    """
    log_step(
        "GET /api/v1/me — Protected Endpoint",
        "The widget is accessing a protected endpoint using the session JWT.\n"
        "GL-IAM's get_current_user dependency automatically validates the\n"
        "Bearer token and extracts the authenticated user.",
    )
    log_gliam("get_current_user()", f"Validated session → user_id={user.id}, email={user.email}")

    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
