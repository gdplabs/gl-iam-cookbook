"""
Secure FastAPI application with GL-IAM authentication.

This example demonstrates how to use GL-IAM with PostgreSQL as a self-managed
user store. It includes user registration, login, and role-based access control.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from gl_iam import IAMGateway, StandardRole, User
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user,
    get_iam_gateway,
    require_org_admin,
    require_org_member,
    require_platform_admin,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import (
    PostgreSQLConfig,
    PostgreSQLProvider,
)
from gl_iam.providers.postgresql.models import RoleModel, UserRoleModel

load_dotenv()


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Initializes the GL-IAM gateway with PostgreSQL provider on startup
    and cleans up resources on shutdown.
    """
    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_auth_hosting=True,
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    app.state.provider = provider

    yield

    await provider.close()


app = FastAPI(title="Secure API", lifespan=lifespan)


# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response model containing access token."""

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


@app.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest):
    """
    Register a new user.

    Creates a user, sets their password, and assigns the default ORG_MEMBER role
    using direct database insert (bypasses RBAC for self-registration).
    """
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

    provider = app.state.provider
    async with provider._session_factory() as session:
        result = await session.execute(
            select(RoleModel).where(RoleModel.name == StandardRole.ORG_MEMBER.value)
        )
        role = result.scalar_one_or_none()

        if role:
            session.add(
                UserRoleModel(
                    user_id=user.id,
                    role_id=role.id,
                )
            )
            await session.commit()

    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """
    Authenticate and get access token.

    Validates credentials and returns a JWT access token on success.
    """
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

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
@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """
    Get current user profile.

    Requires authentication. Returns the authenticated user's profile data.
    """
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


@app.get("/member-only")
async def member_only(
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """
    Member-only endpoint.

    Accessible by ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN.
    """
    return {"message": f"Hello {user.email}, you are an organization member!"}


@app.get("/admin-only")
async def admin_only(
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_admin()),
):
    """
    Admin-only endpoint.

    Accessible by ORG_ADMIN or PLATFORM_ADMIN only.
    """
    return {"message": f"Hello {user.email}, you are an admin!"}


@app.get("/platform-admin-only")
async def platform_admin_only(
    user: User = Depends(get_current_user),
    _: None = Depends(require_platform_admin()),
):
    """
    Platform admin-only endpoint.

    Accessible by PLATFORM_ADMIN only.
    """
    return {"message": f"Hello {user.email}, you are a platform admin!"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
