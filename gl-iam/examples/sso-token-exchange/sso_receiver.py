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

    yield
    await provider.close()


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
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # --- GL-IAM ---
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
        raise HTTPException(status_code=400, detail=result.error.message)

    reg = result.value
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
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # --- GL-IAM ---
    result = await gateway.partner_registry.list_partners(organization_id=org_id)
    # --- End GL-IAM ---

    if result.is_err:
        raise HTTPException(status_code=500, detail=result.error.message)

    return [
        PartnerListItem(
            id=p.id,
            partner_name=p.partner_name,
            consumer_key=p.consumer_key,
            is_active=p.is_active,
            sso_mode=p.sso_mode.value,
            created_at=p.created_at.isoformat() if p.created_at else None,
        )
        for p in result.value
    ]


@app.post("/admin/partners/{partner_id}/rotate", response_model=PartnerResponse)
async def rotate_secret(partner_id: str):
    """Rotate a partner's consumer secret.

    In production, protect this with admin authentication.
    Returns the new consumer_secret (shown only once!).
    """
    gateway = get_iam_gateway()

    # --- GL-IAM ---
    result = await gateway.partner_registry.rotate_consumer_secret(partner_id)
    # --- End GL-IAM ---

    if result.is_err:
        raise HTTPException(status_code=404, detail=result.error.message)

    reg = result.value
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
    gateway = get_iam_gateway()

    # --- GL-IAM: Validate the partner's HMAC signature ---
    result = await gateway.partner_registry.validate_partner_signature(
        consumer_key=request.consumer_key,
        signature=request.signature,
        payload=request.payload,
        timestamp=request.timestamp,
    )

    if result.is_err:
        raise HTTPException(status_code=401, detail=result.error.message)

    partner = result.value
    # --- End GL-IAM ---

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

    return SSOTokenResponse(token=one_time_token, expires_in=SSO_TOKEN_TTL)


@app.post("/api/v1/sso/authenticate", response_model=TokenResponse)
async def sso_authenticate(request: SSOAuthenticateRequest):
    """Phase 2: Exchange one-time token for a JWT session.

    This endpoint is called by the partner's client-side widget.
    - Application code consumes the one-time token.
    - GL-IAM provisions the user (JIT) and creates a session.
    """
    # --- Application code: Consume the one-time token ---
    user_data = _consume_token(request.token)
    if user_data is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    # --- End application code ---

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    email = user_data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Token payload missing 'email'")

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

    existing_user = await gateway.user_store.get_user_by_external_identity(
        external_identity=external_identity,
        organization_id=org_id,
    )

    if existing_user:
        user = existing_user
    else:
        # Create new user (JIT provisioning)
        user = await gateway.user_store.create_user(
            UserCreateInput(
                email=email,
                display_name=user_data.get("display_name", email.split("@")[0]),
            ),
            organization_id=org_id,
        )
        # Link external identity for future lookups
        await gateway.user_store.link_external_identity(
            user_id=user.id,
            external_identity=external_identity,
            organization_id=org_id,
        )

    # Create session (JWT)
    token = await gateway.session_provider.create_session(
        user=user,
        organization_id=org_id,
        metadata={"auth_method": "sso", "partner": user_data.get("partner_name")},
    )
    # --- End GL-IAM ---

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
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
