"""SSO JWT Bridge receiver — GLChat-side FastAPI application.

This example demonstrates a simpler SSO approach (Option B) where the partner
signs a short-lived JWT with a shared secret. No server-to-server token exchange
or partner registry is needed.

Flow:
1. Partner creates a short-lived JWT containing user claims, signed with shared secret.
2. Widget sends JWT to /api/v1/sso/jwt-authenticate.
3. App verifies the JWT signature and expiry.
4. GL-IAM provisions user (JIT) and creates a session → returns session JWT.

Tradeoff vs Option A (sso-token-exchange):
- Simpler: fewer endpoints, no partner registry, no one-time token storage
- Less secure: no per-partner key rotation, no partner deactivation, shared secret
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import jwt as pyjwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import IAMGateway, User
from gl_iam.core.types import UserCreateInput
from gl_iam.core.types.auth import ExternalIdentity
from gl_iam.fastapi import get_current_user, get_iam_gateway, set_iam_gateway
from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider

load_dotenv()


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize GL-IAM gateway with PostgreSQL provider."""
    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # --- GL-IAM ---
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_auth_hosting=True,
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)
    gateway = IAMGateway(
        auth_provider=provider,
        user_store=provider,
        session_provider=provider,
        organization_provider=provider,
    )
    set_iam_gateway(gateway, default_organization_id=default_org_id)
    # --- End GL-IAM ---

    yield
    await provider.close()


app = FastAPI(title="SSO JWT Bridge Receiver", lifespan=lifespan)


# ============================================================================
# Request/Response Models (Application Code)
# ============================================================================
class SSOJwtAuthenticateRequest(BaseModel):
    """Request from the partner widget to authenticate via signed JWT."""

    partner_jwt: str


class TokenResponse(BaseModel):
    """Response containing the session JWT."""

    access_token: str
    token_type: str


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    display_name: str | None


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy"}


# ============================================================================
# SSO Flow Endpoints
# ============================================================================
@app.post("/api/v1/sso/jwt-authenticate", response_model=TokenResponse)
async def sso_jwt_authenticate(request: SSOJwtAuthenticateRequest):
    """Verify partner-signed JWT, provision user (JIT), and return session JWT.

    This single endpoint handles the entire SSO flow for Option B:
    1. Application code verifies the partner JWT signature and claims.
    2. GL-IAM provisions the user and creates a session.
    """
    sso_secret = os.getenv("SSO_SHARED_SECRET")
    expected_issuer = os.getenv("PARTNER_ISSUER", "partner-portal")

    if not sso_secret:
        raise HTTPException(status_code=500, detail="SSO_SHARED_SECRET not configured")

    # --- Application code: Verify partner JWT ---
    try:
        claims = pyjwt.decode(
            request.partner_jwt,
            sso_secret,
            algorithms=["HS256"],
            issuer=expected_issuer,
            options={"require": ["exp", "iss", "sub", "email"]},
        )
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Partner JWT has expired")
    except pyjwt.InvalidIssuerError:
        raise HTTPException(status_code=401, detail="Invalid JWT issuer")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid partner JWT: {e}")
    # --- End application code ---

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="JWT missing 'email' claim")

    # --- GL-IAM: JIT user provisioning ---
    external_identity = ExternalIdentity(
        provider_type="sso_jwt",
        provider_id=expected_issuer,
        external_id=claims.get("sub", email),
        email=email,
        display_name=claims.get("display_name"),
        username=claims.get("username"),
        first_name=claims.get("first_name"),
        last_name=claims.get("last_name"),
        groups=[],
        attributes={"issuer": expected_issuer},
        authenticated_at=datetime.now(timezone.utc),
    )

    existing_user = await gateway.user_store.get_user_by_external_identity(
        external_identity=external_identity,
        organization_id=org_id,
    )

    if existing_user:
        user = existing_user
    else:
        user = await gateway.user_store.create_user(
            UserCreateInput(
                email=email,
                display_name=claims.get("display_name", email.split("@")[0]),
            ),
            organization_id=org_id,
        )
        await gateway.user_store.link_external_identity(
            user_id=user.id,
            external_identity=external_identity,
            organization_id=org_id,
        )

    token = await gateway.session_provider.create_session(
        user=user,
        organization_id=org_id,
        metadata={"auth_method": "sso_jwt", "issuer": expected_issuer},
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
