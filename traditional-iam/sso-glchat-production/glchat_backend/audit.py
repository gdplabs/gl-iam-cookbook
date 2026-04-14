"""Audit wiring + helpers to emit application-level SSO events.

The SDK's AuditEventType enum doesn't have SSO-specific values yet, so we
use close generic types (TOKEN_ISSUED, TOKEN_VALIDATION_FAILED, JIT_PROVISION,
IDENTITY_LINKED, SESSION_CREATED, USER_CREATED) and attach a `sso.event` tag
in `details` so dashboards can filter by it.
"""

from __future__ import annotations

from gl_iam import AuditHandler, CompositeAuditHandler, get_audit_context
from gl_iam.core.types.audit import AuditEvent, AuditEventType, AuditSeverity

_handler: AuditHandler | None = None


def set_handler(handler: AuditHandler) -> None:
    global _handler
    _handler = handler


def emit(
    *,
    event_type: AuditEventType,
    severity: AuditSeverity = AuditSeverity.INFO,
    sso_event: str,
    message: str,
    user_id: str | None = None,
    organization_id: str | None = None,
    resource_id: str | None = None,
    error_code: str | None = None,
    **details,
) -> None:
    """Emit an SSO audit event tagged with `details['sso.event']`."""
    if _handler is None:
        return
    ctx = get_audit_context()
    event = AuditEvent(
        event_type=event_type,
        severity=severity,
        user_id=user_id,
        organization_id=organization_id,
        resource_id=resource_id,
        ip_address=ctx.ip_address if ctx else None,
        user_agent=ctx.user_agent if ctx else None,
        error_code=error_code,
        message=message,
        details={"sso.event": sso_event, **details},
        provider_type="sso-idp-initiated",
    )
    _handler.handle(event)


__all__ = ["set_handler", "emit", "CompositeAuditHandler"]
