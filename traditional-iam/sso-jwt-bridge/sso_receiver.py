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

import logging
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

# Configure logging with clear formatting
logging.basicConfig(
    level=logging.INFO,
    format="\n%(message)s",
)
logger = logging.getLogger("sso-jwt-bridge")


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
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize GL-IAM gateway with PostgreSQL provider."""
    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    logger.info(
        "=" * 70 + "\n"
        "  SSO JWT Bridge Receiver — Starting up\n"
        "  (GLChat backend using GL-IAM)\n"
        "=" * 70
    )

    # --- GL-IAM ---
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_auth_hosting=True,
        enable_third_party_provider=False,
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

    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ ✅ GL-IAM gateway initialized\n"
        "│\n"
        "│   Provider:       PostgreSQL\n"
        "│   Organization:   %s\n"
        "│   Auth hosting:   enabled\n"
        "│   Partner issuer: %s\n"
        "│\n"
        "│   Ready to receive SSO JWT authentication requests.\n"
        "│   The partner (e.g., Lokadata) signs a JWT with the shared\n"
        "│   secret and sends it here for verification.\n"
        "└─────────────────────────────────────────────────────────────────",
        default_org_id,
        os.getenv("PARTNER_ISSUER", "partner-portal"),
    )

    yield
    await provider.close()
    logger.info("GL-IAM gateway shut down.")


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
    logger.info("Health check requested → healthy")
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

    # ── Step A: Verify partner JWT ──────────────────────────────────
    log_step(
        "POST /api/v1/sso/jwt-authenticate — Received SSO request",
        "A partner widget is attempting to authenticate a user.\n"
        "The partner signed a JWT with the shared secret containing\n"
        "the user's identity claims (email, name, external ID).\n\n"
        "Now we verify the JWT signature and extract the claims.",
    )

    # --- Application code: Verify partner JWT ---
    log_app("Verifying partner JWT signature", f"algorithm=HS256, expected issuer={expected_issuer}")

    try:
        claims = pyjwt.decode(
            request.partner_jwt,
            sso_secret,
            algorithms=["HS256"],
            issuer=expected_issuer,
            options={"require": ["exp", "iss", "sub", "email"]},
        )
    except pyjwt.ExpiredSignatureError:
        log_app("JWT verification FAILED", "Token has expired")
        raise HTTPException(status_code=401, detail="Partner JWT has expired")
    except pyjwt.InvalidIssuerError:
        log_app("JWT verification FAILED", f"Issuer mismatch (expected: {expected_issuer})")
        raise HTTPException(status_code=401, detail="Invalid JWT issuer")
    except pyjwt.InvalidTokenError as e:
        log_app("JWT verification FAILED", str(e))
        raise HTTPException(status_code=401, detail=f"Invalid partner JWT: {e}")
    # --- End application code ---

    log_app(
        "JWT verification PASSED",
        f"sub={claims.get('sub')}, email={claims.get('email')}, iss={claims.get('iss')}",
    )

    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    email = claims.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="JWT missing 'email' claim")

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

    log_gliam(
        "get_user_by_external_identity()",
        f"Looking up user with external_id={claims.get('sub')}, provider={expected_issuer}",
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

        user = await gateway.user_store.create_user(
            UserCreateInput(
                email=email,
                display_name=claims.get("display_name", email.split("@")[0]),
            ),
            organization_id=org_id,
        )
        log_gliam("create_user()", f"Created user id={user.id}, email={user.email}")

        await gateway.user_store.link_external_identity(
            user_id=user.id,
            external_identity=external_identity,
            organization_id=org_id,
        )
        log_gliam("link_external_identity()", f"Linked external_id={claims.get('sub')} → user_id={user.id}")

    # ── Step C: Create Session ──────────────────────────────────────
    log_step(
        "Create GLChat Session",
        "The user is now verified and provisioned in GLChat.\n"
        "GL-IAM creates a session JWT that the widget will use\n"
        "to access protected GLChat APIs.",
    )

    log_gliam("create_session()", f"Creating session for user_id={user.id}")

    token = await gateway.session_provider.create_session(
        user=user,
        organization_id=org_id,
        metadata={"auth_method": "sso_jwt", "issuer": expected_issuer},
    )
    # --- End GL-IAM ---

    log_gliam("Session created", f"token_type={token.token_type}, token={token.access_token[:20]}...")

    logger.info(
        "┌─────────────────────────────────────────────────────────────────\n"
        "│ ✅ SSO JWT Authentication Complete\n"
        "│\n"
        "│   Partner:     %s\n"
        "│   External ID: %s\n"
        "│   Email:       %s\n"
        "│   GLChat User: %s\n"
        "│   Session:     %s...\n"
        "│\n"
        "│   The widget can now use this session JWT to access GLChat APIs.\n"
        "└─────────────────────────────────────────────────────────────────",
        expected_issuer,
        claims.get("sub"),
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
