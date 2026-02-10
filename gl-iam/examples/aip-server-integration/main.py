"""
AIP Server Integration with GL-IAM.

This example demonstrates how to integrate GL-IAM into an AIP server
using Bearer token authentication with role-based access control.
"""

import os
from contextlib import asynccontextmanager
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from starlette.status import HTTP_401_UNAUTHORIZED

from gl_iam import IAMGateway, StandardRole, User
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user as gliam_get_current_user,
    get_iam_gateway,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLProvider, PostgreSQLConfig

load_dotenv()


# =============================================================================
# Configuration
# =============================================================================
class Settings(BaseSettings):
    """Application settings with GL-IAM configuration."""

    # Database
    aip_db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/aip"

    # GL-IAM Configuration
    gliam_secret_key: str | None = None
    gliam_organization_id: str = "default"
    gliam_enable_auth_hosting: bool = True
    gliam_auto_create_tables: bool = True

    @property
    def gliam_enabled(self) -> bool:
        """Check if GL-IAM is configured."""
        return self.gliam_secret_key is not None

    class Config:
        env_file = ".env"


settings = Settings()


# =============================================================================
# Security Schemes
# =============================================================================
bearer_scheme = HTTPBearer(auto_error=False)


# =============================================================================
# GL-IAM Authentication
# =============================================================================
async def get_current_user(
    bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> User:
    """
    Get current user from GL-IAM Bearer token.

    Returns:
        User object if Bearer token is valid

    Raises:
        HTTPException: If GL-IAM not enabled or invalid token
    """
    if not settings.gliam_enabled:
        raise HTTPException(status_code=501, detail="GL-IAM not enabled")

    if not bearer_token:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    gateway = get_iam_gateway()
    result = await gateway.validate_session(
        bearer_token.credentials,
        organization_id=settings.gliam_organization_id,
    )

    if result.is_err:
        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return result.value


def get_account_id_from_user(user: User) -> UUID | None:
    """
    Extract organization ID as UUID from GL-IAM User.

    Returns:
        UUID of the organization or None if not available
    """
    if hasattr(user, "organization_id") and user.organization_id:
        try:
            return UUID(user.organization_id)
        except ValueError:
            return None
    return None


# =============================================================================
# Role-Based Dependencies
# =============================================================================
def require_org_member():
    """Require ORG_MEMBER role via GL-IAM."""

    async def check(
        bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    ):
        if not settings.gliam_enabled:
            raise HTTPException(status_code=501, detail="GL-IAM not enabled")

        if not bearer_token:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        gateway = get_iam_gateway()
        result = await gateway.validate_session(
            bearer_token.credentials,
            organization_id=settings.gliam_organization_id,
        )

        if result.is_err:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = result.value
        if not user.has_standard_role(StandardRole.ORG_MEMBER):
            raise HTTPException(status_code=403, detail="ORG_MEMBER role required")

    return check


def require_org_admin():
    """Require ORG_ADMIN role via GL-IAM."""

    async def check(
        bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    ):
        if not settings.gliam_enabled:
            raise HTTPException(status_code=501, detail="GL-IAM not enabled")

        if not bearer_token:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Bearer token required",
                headers={"WWW-Authenticate": "Bearer"},
            )

        gateway = get_iam_gateway()
        result = await gateway.validate_session(
            bearer_token.credentials,
            organization_id=settings.gliam_organization_id,
        )

        if result.is_err:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = result.value
        if not user.has_standard_role(StandardRole.ORG_ADMIN):
            raise HTTPException(status_code=403, detail="ORG_ADMIN role required")

    return check


# =============================================================================
# Application Setup
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with GL-IAM initialization."""
    provider = None

    # Initialize GL-IAM if configured
    if settings.gliam_enabled:
        config = PostgreSQLConfig(
            database_url=settings.aip_db_url,
            secret_key=settings.gliam_secret_key,
            enable_auth_hosting=settings.gliam_enable_auth_hosting,
            auto_create_tables=settings.gliam_auto_create_tables,
            default_org_id=settings.gliam_organization_id,
        )
        provider = PostgreSQLProvider(config)
        gateway = IAMGateway.from_fullstack_provider(provider)

        # Make gateway available to FastAPI dependencies
        set_iam_gateway(gateway, default_organization_id=settings.gliam_organization_id)
        print(f"GL-IAM initialized with organization: {settings.gliam_organization_id}")
    else:
        print("GL-IAM not configured - set GLIAM_SECRET_KEY to enable")

    yield

    # Cleanup GL-IAM resources
    if provider:
        await provider.close()


app = FastAPI(title="AIP Server with GL-IAM", lifespan=lifespan)


# =============================================================================
# Request/Response Models
# =============================================================================
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


class AgentResponse(BaseModel):
    """Response model for agent data."""

    id: str
    name: str
    account_id: str | None


# =============================================================================
# Auth Endpoints (GL-IAM)
# =============================================================================
@app.post("/auth/register", response_model=dict)
async def register(request: RegisterRequest):
    """Register a new user."""
    if not settings.gliam_enabled:
        raise HTTPException(status_code=501, detail="GL-IAM not configured")

    gateway = get_iam_gateway()
    org_id = settings.gliam_organization_id

    user = await gateway.user_store.create_user(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        organization_id=org_id,
    )
    await gateway.user_store.set_user_password(user.id, request.password, org_id)
    await gateway.user_store.assign_role(user.id, StandardRole.ORG_MEMBER.value, org_id)

    return {"id": user.id, "email": user.email}


@app.post("/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login and get access token."""
    if not settings.gliam_enabled:
        raise HTTPException(status_code=501, detail="GL-IAM not configured")

    gateway = get_iam_gateway()

    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=settings.gliam_organization_id,
    )

    if result.is_ok:
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    else:
        raise HTTPException(status_code=401, detail=result.error.message)


# =============================================================================
# Protected Endpoints
# =============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {
        "status": "healthy",
        "gliam_enabled": settings.gliam_enabled,
    }


@app.get("/agents", response_model=list[AgentResponse])
async def list_agents(
    _: None = Depends(require_org_member()),
    user: User = Depends(get_current_user),
):
    """
    List agents for the current user's organization.

    Requires ORG_MEMBER role.
    """
    account_id = get_account_id_from_user(user)

    # Demo response - in real server, query database
    return [
        AgentResponse(
            id="agent-1",
            name="Demo Agent",
            account_id=str(account_id) if account_id else None,
        )
    ]


@app.post("/agents", response_model=AgentResponse)
async def create_agent(
    name: str,
    _: None = Depends(require_org_member()),
    user: User = Depends(get_current_user),
):
    """
    Create a new agent.

    Requires ORG_MEMBER role.
    """
    account_id = get_account_id_from_user(user)

    # Demo response - in real server, create in database
    return AgentResponse(
        id="new-agent-1",
        name=name,
        account_id=str(account_id) if account_id else None,
    )


@app.get("/admin/accounts")
async def list_accounts(
    _: None = Depends(require_org_admin()),
    user: User = Depends(get_current_user),
):
    """
    Admin endpoint to list all accounts.

    Requires ORG_ADMIN role.
    """
    return {"accounts": ["account-1", "account-2"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
