"""
Refresh tokens with FastAPI and the GL-IAM Native provider.

Short-lived access tokens keep a stolen token's damage window small; a long-lived
refresh token keeps the user signed in without asking for the password again.
This example shows the whole lifecycle:

- log in with a refresh token and a chosen access-token lifetime
- exchange the refresh token for a new access token
- list the user's signed-in devices (one refresh token per device)
- sign one device out, end only its current access tokens, or sign out everywhere
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from gl_iam import IAMGateway, User, UserAlreadyExistsError
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.core.types.result import ErrorCode
from gl_iam.fastapi import add_exception_handlers, get_current_user, get_iam_gateway, set_iam_gateway
from gl_iam.providers.native import NativeConfig, NativeProvider

load_dotenv()

ORG_ID = os.getenv("DEFAULT_ORGANIZATION_ID", "default")


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the Native provider (PostgreSQL) and register the gateway."""
    provider = NativeProvider(
        NativeConfig(
            database_url=os.getenv("DATABASE_URL"),
            secret_key=os.getenv("SECRET_KEY"),
            default_org_id=ORG_ID,
            # How long a refresh token lives. One year is the SDK default.
            refresh_token_expiry_seconds=int(os.getenv("REFRESH_TOKEN_EXPIRY_SECONDS", "31536000")),
        )
    )
    set_iam_gateway(IAMGateway.from_fullstack_provider(provider), default_organization_id=ORG_ID)
    yield
    await provider.close()


app = FastAPI(title="Refresh Tokens", lifespan=lifespan)
add_exception_handlers(app)


# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: str
    password: str


class LoginRequest(BaseModel):
    """Request model for login."""

    email: str
    password: str
    # "Remember me": also issue a refresh token.
    remember_me: bool = True
    # Access-token lifetime for this login, 300 s (5 min) to 2,592,000 s (30 days).
    access_token_ttl_seconds: int | None = Field(default=300)


class RefreshRequest(BaseModel):
    """Request model for exchanging a refresh token."""

    refresh_token: str


class TokenResponse(BaseModel):
    """Tokens returned by login and refresh."""

    access_token: str
    token_type: str
    expires_at: datetime | None
    refresh_token: str | None = None
    refresh_expires_at: datetime | None = None
    # Identifies this device's refresh token in /devices; not a secret.
    refresh_token_id: str | None = None


def _token_response(token) -> TokenResponse:
    return TokenResponse(
        access_token=token.access_token,
        token_type=token.token_type,
        expires_at=token.expires_at,
        refresh_token=token.refresh_token,
        refresh_expires_at=token.refresh_expires_at,
        refresh_token_id=token.metadata.get("refresh_token_id"),
    )


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy"}


@app.post("/register")
async def register(request: RegisterRequest):
    """Create a user with a password."""
    gateway = get_iam_gateway()
    try:
        user = await gateway.user_store.create_user(UserCreateInput(email=request.email), organization_id=ORG_ID)
    except UserAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    await gateway.user_store.set_user_password(user.id, request.password, ORG_ID)
    return {"id": user.id, "email": user.email}


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Log in. With remember_me, the response also carries a refresh token.

    A lifetime outside 300-2,592,000 seconds is rejected with 400, never clamped.
    """
    result = await get_iam_gateway().authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=ORG_ID,
        issue_refresh_token=request.remember_me,
        access_token_ttl_seconds=request.access_token_ttl_seconds,
    )
    if result.is_err:
        status = 400 if result.error.code == ErrorCode.INVALID_TOKEN_LIFETIME else 401
        raise HTTPException(status_code=status, detail=result.error.message)
    return _token_response(result.token)


@app.post("/token/refresh", response_model=TokenResponse)
async def refresh(request: RefreshRequest):
    """
    Exchange a refresh token for a new access token.

    The refresh token is not rotated: the same one comes back, with its original
    expiry. The new access token never outlives the refresh token.
    """
    result = await get_iam_gateway().refresh_session(request.refresh_token, organization_id=ORG_ID)
    if result.is_err:
        # Revoked, expired, unknown, or the user/organization was deactivated: log in again.
        raise HTTPException(status_code=401, detail=result.error.message)
    return _token_response(result.value)


# ============================================================================
# Protected Endpoints
# ============================================================================
@app.get("/me")
async def me(user: User = Depends(get_current_user)):
    """Works with any access token, including one issued by /token/refresh."""
    return {"id": user.id, "email": user.email}


@app.get("/devices")
async def list_devices(user: User = Depends(get_current_user)):
    """List the user's signed-in devices: one live refresh token each."""
    tokens = (await get_iam_gateway().list_refresh_tokens(user.id, ORG_ID)).unwrap()
    return [
        {
            "refresh_token_id": t.id,
            "preview": t.token_preview,  # safe to show; cannot be used to sign in
            "created_at": t.created_at,
            "expires_at": t.expires_at,
            "last_used_at": t.last_used_at,
            "active_sessions": len(t.active_sessions),
        }
        for t in tokens
    ]


@app.delete("/devices/{refresh_token_id}", status_code=204)
async def sign_out_device(refresh_token_id: str, user: User = Depends(get_current_user)):
    """
    Sign a device out: its refresh token and every access token issued from it stop working.

    Signing out the device making this request is allowed. Another user's device ID
    returns 404.
    """
    result = await get_iam_gateway().revoke_refresh_token(refresh_token_id, user.id, ORG_ID)
    if result.is_err:
        raise HTTPException(status_code=404, detail=result.error.message)


@app.delete("/devices/{refresh_token_id}/sessions")
async def end_device_sessions(refresh_token_id: str, user: User = Depends(get_current_user)):
    """End a device's current access tokens. Its refresh token keeps working."""
    result = await get_iam_gateway().revoke_refresh_token_sessions(refresh_token_id, user.id, ORG_ID)
    return {"revoked_access_tokens": result.unwrap()}


@app.post("/logout-everywhere")
async def logout_everywhere(user: User = Depends(get_current_user)):
    """Revoke every session and refresh token the user has in this organization."""
    result = await get_iam_gateway().revoke_all_sessions(user.id, ORG_ID)
    return {"revoked_sessions": result.unwrap()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
