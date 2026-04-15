"""GLChat backend — production-grade IdP-Initiated SSO receiver.

Wires:
  - PostgreSQL provider (users, sessions, partner registry, audit log)
  - Redis-backed one-time token + nonce stores
  - Console + Database audit handlers
  - Rate limiting, CSP, audit-context middleware
  - Partner CRUD + rotation + audit-log admin API (PLATFORM_ADMIN only)
  - Public SSO endpoints: /api/v1/sso/token, /api/v1/sso/authenticate
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gl_iam import (
    CompositeAuditHandler,
    ConsoleAuditHandler,
    IAMGateway,
)
from gl_iam.core.gateway import AuditConfig
from gl_iam.core.exceptions import AuthenticationError, AuthorizationError
from gl_iam.fastapi import set_iam_gateway
from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider

from glchat_backend import audit as audit_module
from glchat_backend.config import get_settings
from glchat_backend.middleware import audit_context, csp, rate_limit
from glchat_backend.routers import admin as admin_router
from glchat_backend.routers import auth as auth_router
from glchat_backend.routers import sso as sso_router
from glchat_backend.services.nonce_store import NonceStore
from glchat_backend.services.sso_service import SSOService
from glchat_backend.services.token_store import OneTimeTokenStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")

# Exposed at module scope so routers/admin.py can query the audit table.
glchat_provider: PostgreSQLProvider | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global glchat_provider
    settings = get_settings()

    config = PostgreSQLConfig(
        database_url=settings.database_url,
        secret_key=settings.secret_key,
        encryption_key=settings.encryption_key,
        default_org_id=settings.default_org_id,
        enable_auth_hosting=True,
        enable_partner_registry=True,
        enable_audit_log=True,
        audit_flush_interval_seconds=1.0,
        audit_batch_size=10,
        auto_create_tables=True,
    )
    glchat_provider = PostgreSQLProvider(config)

    handlers = [ConsoleAuditHandler()]
    if (db_handler := glchat_provider.create_audit_handler()):
        handlers.append(db_handler)
    composite = CompositeAuditHandler(handlers)
    audit_module.set_handler(composite)

    gateway = IAMGateway(
        auth_provider=glchat_provider,
        user_store=glchat_provider,
        session_provider=glchat_provider,
        organization_provider=glchat_provider,
        partner_registry=glchat_provider,
        audit_config=AuditConfig(handlers=[composite]),
    )
    set_iam_gateway(gateway, default_organization_id=settings.default_org_id)

    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    await redis.ping()

    app.state.redis = redis
    app.state.provider = glchat_provider
    app.state.sso_service = SSOService(
        gateway=gateway,
        token_store=OneTimeTokenStore(redis, settings.sso_token_ttl_seconds),
        nonce_store=NonceStore(redis, settings.nonce_ttl_seconds),
        organization_id=settings.default_org_id,
        timestamp_tolerance_seconds=settings.hmac_timestamp_tolerance_seconds,
    )

    logging.getLogger("glchat_backend").info(
        "GLChat BE ready. Partner registry + audit + Redis-backed OTK active."
    )

    yield

    await redis.aclose()
    await glchat_provider.close()


app = FastAPI(title="GLChat Backend — IdP-Initiated SSO (production pattern)", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.partner_site_origin,
        settings.glchat_admin_origin,
        settings.glchat_widget_origin,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

audit_context.register(app)
rate_limit.register(app)
csp.register(app)


@app.exception_handler(AuthenticationError)
async def _auth_err(_r, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=401, content={"detail": str(exc)})


@app.exception_handler(AuthorizationError)
async def _authz_err(_r, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=403, content={"detail": str(exc)})


app.include_router(auth_router.router)
app.include_router(admin_router.router)
app.include_router(sso_router.router)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/widget/demo")
async def widget_demo():
    """Synthetic endpoint: the CSP middleware attaches a dynamic
    `frame-ancestors` header on any path prefixed `/widget`. Used by the E2E
    assertion to verify the allowlist is actually emitted.
    """
    return {"ok": True, "note": "Inspect the Content-Security-Policy header."}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
