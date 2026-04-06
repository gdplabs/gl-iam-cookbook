"""
Audit Trail with GL-IAM — Production Setup.

This example demonstrates a production-ready audit trail:
- ConsoleAuditHandler + DatabaseAuditHandler via CompositeAuditHandler
- Request context middleware (ip_address, user_agent)
- Multiple auth endpoints generating diverse audit events
- Queryable audit log endpoint with filters (event_type, user_id, severity, date range)

Key learning: from_fullstack_provider() does NOT accept audit_handlers.
You must use the explicit IAMGateway() constructor to wire audit handlers.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func

from gl_iam import (
    ConsoleAuditHandler,
    CompositeAuditHandler,
    IAMGateway,
    User,
    set_audit_context,
    clear_audit_context,
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user,
    get_iam_gateway,
    require_org_admin,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import (
    AuditEventModel,
    PostgreSQLConfig,
    PostgreSQLProvider,
)

load_dotenv()

# Configure logging to see ConsoleAuditHandler output
logging.basicConfig(level=logging.INFO)


# ============================================================================
# Application Setup
# ============================================================================
provider: PostgreSQLProvider | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Sets up the audit trail with:
    1. ConsoleAuditHandler — structured JSON logs to stdout
    2. DatabaseAuditHandler — async batch writes to PostgreSQL
    3. CompositeAuditHandler — routes events to both handlers
    """
    global provider

    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # Step 1: Enable audit logging in PostgreSQLConfig
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_audit_log=True,  # Creates audit_events table + enables DatabaseAuditHandler
        enable_auth_hosting=True,
        enable_third_party_provider=False,
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)

    # Step 2: Build composite handler (console + database)
    console_handler = ConsoleAuditHandler()
    db_handler = provider.create_audit_handler()  # Returns DatabaseAuditHandler
    handlers = [console_handler]
    if db_handler:
        handlers.append(db_handler)
    composite = CompositeAuditHandler(handlers)

    # Step 3: Use explicit IAMGateway constructor (NOT from_fullstack_provider)
    # because from_fullstack_provider() does not accept audit_handlers.
    gateway = IAMGateway(
        auth_provider=provider,
        user_store=provider,
        session_provider=provider,
        organization_provider=provider,
        audit_handlers=[composite],
    )
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    # Store provider reference for audit query endpoint
    app.state.provider = provider

    yield

    await provider.close()


app = FastAPI(
    title="Audit Trail API",
    description="GL-IAM Audit Trail — Production Setup",
    lifespan=lifespan,
)


# ============================================================================
# Audit Context Middleware
# ============================================================================
@app.middleware("http")
async def audit_context_middleware(request, call_next):
    """Attach request IP and user agent to all audit events automatically.

    All AuditEvents emitted during this request will have ip_address and
    user_agent populated from the request context — no manual passing needed.
    """
    set_audit_context(
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    try:
        return await call_next(request)
    finally:
        clear_audit_context()


# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check."""
    return {"status": "healthy", "service": "audit-trail-fastapi"}


@app.post("/register")
async def register(request: RegisterRequest):
    """Register a new user. Triggers: user_created, credential_created."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    user = await gateway.user_store.create_user(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        organization_id=org_id,
    )
    await gateway.user_store.set_user_password(user.id, request.password, org_id)

    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user. Triggers: login_success or login_error."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=org_id,
    )

    if result.is_ok:
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    else:
        raise HTTPException(status_code=401, detail=result.error.message)


# ============================================================================
# Protected Endpoints
# ============================================================================
@app.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@app.get("/admin")
async def admin_only(
    _: None = Depends(require_org_admin()),
    user: User = Depends(get_current_user),
):
    """Admin-only endpoint. Triggers: permission_denied if user lacks ORG_ADMIN role."""
    return {"message": f"Welcome admin {user.email}"}


@app.post("/logout")
async def logout(user: User = Depends(get_current_user)):
    """Logout current user. Triggers: logout, session_revoked_all."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    await gateway.logout(user.id, organization_id=org_id)
    return {"message": "Logged out successfully"}


@app.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
):
    """Change password. Triggers: credential_password_updated."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # Verify current password first
    verify_result = await gateway.authenticate(
        credentials=PasswordCredentials(email=user.email, password=request.current_password),
        organization_id=org_id,
    )
    if not verify_result.is_ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    await gateway.user_store.set_user_password(user.id, request.new_password, org_id)
    return {"message": "Password changed successfully"}


# ============================================================================
# Audit Log Query Endpoint
# ============================================================================
@app.get("/audit-log")
async def get_audit_log(
    user: User = Depends(get_current_user),
    event_type: str | None = Query(None, description="Filter by event type (e.g. login_success)"),
    user_id: str | None = Query(None, description="Filter by user ID"),
    severity: str | None = Query(None, description="Filter by severity (debug/info/warning/error/critical)"),
    from_date: datetime | None = Query(None, description="Events after this datetime (ISO 8601)"),
    to_date: datetime | None = Query(None, description="Events before this datetime (ISO 8601)"),
    limit: int = Query(50, le=200, description="Max events to return"),
    offset: int = Query(0, description="Offset for pagination"),
):
    """Query audit events from the database with optional filters.

    The SDK persists events via DatabaseAuditHandler but does not provide
    a query API. This endpoint shows how to query AuditEventModel directly
    with SQLAlchemy.
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    prov: PostgreSQLProvider = app.state.provider
    async with AsyncSession(prov._async_engine) as session:
        # Build query with optional filters
        query = select(AuditEventModel).order_by(AuditEventModel.timestamp.desc())
        count_query = select(func.count()).select_from(AuditEventModel)

        if event_type:
            query = query.where(AuditEventModel.event_type == event_type)
            count_query = count_query.where(AuditEventModel.event_type == event_type)
        if user_id:
            query = query.where(AuditEventModel.user_id == user_id)
            count_query = count_query.where(AuditEventModel.user_id == user_id)
        if severity:
            query = query.where(AuditEventModel.severity == severity)
            count_query = count_query.where(AuditEventModel.severity == severity)
        if from_date:
            query = query.where(AuditEventModel.timestamp >= from_date)
            count_query = count_query.where(AuditEventModel.timestamp >= from_date)
        if to_date:
            query = query.where(AuditEventModel.timestamp <= to_date)
            count_query = count_query.where(AuditEventModel.timestamp <= to_date)

        # Get total count
        total = (await session.execute(count_query)).scalar() or 0

        # Get paginated results
        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        events = result.scalars().all()

    return {
        "events": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "user_id": e.user_id,
                "organization_id": e.organization_id,
                "ip_address": e.ip_address,
                "user_agent": e.user_agent,
                "resource_id": e.resource_id,
                "error_code": e.error_code,
                "message": e.message,
                "trace_id": e.trace_id,
            }
            for e in events
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ============================================================================
# Advanced: Adding OpenTelemetry (uncomment to enable)
# ============================================================================
# To add OpenTelemetry trace correlation, add OpenTelemetryAuditHandler
# to the composite in the lifespan:
#
#   from gl_iam import OpenTelemetryAuditHandler
#   otel_handler = OpenTelemetryAuditHandler()
#   composite = CompositeAuditHandler([console_handler, db_handler, otel_handler])
#
# Install: pip install opentelemetry-api opentelemetry-sdk
# See: https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/identity-and-access-management/audit-trail/opentelemetry


# ============================================================================
# Advanced: Custom Audit Handler (uncomment to enable)
# ============================================================================
# from gl_iam import AuditHandler
# from gl_iam.core.types.audit import AuditEvent
#
# class WebhookAuditHandler(AuditHandler):
#     """Send high-severity events to an external webhook."""
#
#     def __init__(self, webhook_url: str):
#         self._url = webhook_url
#
#     def handle(self, event: AuditEvent) -> None:
#         if event.severity not in ("error", "critical"):
#             return
#         import requests
#         requests.post(self._url, json={
#             "event_type": event.event_type,
#             "severity": event.severity,
#             "user_id": event.user_id,
#             "message": event.message,
#             "ip_address": event.ip_address,
#         }, timeout=5)
#
# Add to composite: composite.add_handler(WebhookAuditHandler("https://hooks.slack.com/..."))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
