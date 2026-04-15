"""Populate audit + request context for every HTTP request.

Derives the real client IP from `X-Forwarded-For` (if present) with a fallback
to the socket peer. The IP is used by GL-IAM's `validate_partner_signature`
to enforce `partner.allowed_source_ips`, so trustworthy extraction matters.
"""

from __future__ import annotations

from fastapi import FastAPI, Request

from gl_iam import clear_audit_context, set_audit_context


def client_ip(request: Request) -> str | None:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def register(app: FastAPI) -> None:
    @app.middleware("http")
    async def _audit_context(request: Request, call_next):
        ip = client_ip(request)
        request.state.client_ip = ip
        set_audit_context(
            ip_address=ip,
            user_agent=request.headers.get("user-agent"),
        )
        try:
            return await call_next(request)
        finally:
            clear_audit_context()
