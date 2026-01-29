"""
AIP Server Integration with GL-IAM.

This example demonstrates how to integrate GL-IAM into an existing AIP server,
supporting both Bearer token (GL-IAM) and X-API-Key (legacy) authentication
while maintaining backward compatibility.
"""

import os
from contextlib import asynccontextmanager
from uuid import UUID

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from starlette.status import HTTP_401_UNAUTHORIZED

from gl_iam import IAMGateway, StandardRole, User
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user as gliam_get_current_user,
    get_iam_gateway,
    require_org_admin as gliam_require_org_admin,
    require_org_member as gliam_require_org_member,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLProvider, PostgreSQLUserStoreConfig

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

    # Legacy API Key (for backward compatibility)
    aip_master_api_key: str = "test-api-key"

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
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# =============================================================================
# Legacy API Key Auth (Simulated)
# =============================================================================
async def verify_api_key(api_key: str) -> UUID | None:
    """
    Verify legacy API key. Returns account_id or None for master key.

    In a real AIP server, this would check against the database.
    """
    if api_key == settings.aip_master_api_key:
        return None  # Master key - no specific account
    # In real implementation: check account API keys in database
    # For this example, accept any key as valid
    return UUID("00000000-0000-0000-0000-000000000001")  # Demo account


# =============================================================================
# Unified Authentication (GL-IAM + Legacy)
# =============================================================================
async def get_unified_identity(
    bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key: str | None = Security(api_key_scheme),
) -> User | UUID | None:
    """
    Get unified identity from either Bearer token or API key.

    Priority:
    1. Bearer token (GL-IAM session) -> Returns User object
    2. X-API-Key (legacy) -> Returns UUID (account_id) or None (master key)

    Returns:
        - User object if Bearer token is valid (GL-IAM)
        - UUID (account_id) if account API key is valid
        - None if master API key is valid

    Raises:
        HTTPException: If no valid authentication provided
    """
    # Try Bearer token first (GL-IAM session)
    if bearer_token and settings.gliam_enabled:
        try:
            gateway = get_iam_gateway()
            user = await gateway.validate_session(
                bearer_token.credentials,
                organization_id=settings.gliam_organization_id,
            )
            if user:
                return user
        except Exception:
            pass  # Fall through to API key

    # Fall back to legacy API key
    if api_key:
        account_id = await verify_api_key(api_key)
        return account_id  # UUID or None

    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide Bearer token or X-API-Key.",
        headers={"WWW-Authenticate": "Bearer, ApiKey"},
    )


def get_account_id_from_identity(identity: User | UUID | None) -> UUID | None:
    """
    Extract account/organization ID from unified identity.

    For GL-IAM User: Returns organization_id as UUID
    For legacy API key: Returns the account_id directly
    For master key: Returns None
    """
    if identity is None:
        return None  # Master key

    if isinstance(identity, UUID):
        return identity  # Legacy API key account_id

    # GL-IAM User - convert organization_id to UUID
    if hasattr(identity, "organization_id"):
        org_id = identity.organization_id
        if org_id:
            try:
                return UUID(org_id)
            except ValueError:
                return None
    return None


# =============================================================================
# Role-Based Dependencies
# =============================================================================
def require_org_member():
    """Require ORG_MEMBER role (GL-IAM) or valid API key (legacy).
    
    This unified dependency supports both:
    - GL-IAM Bearer token authentication with role checking
    - Legacy X-API-Key authentication (any valid API key)
    """
    async def unified_check(
        bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
        api_key: str | None = Security(api_key_scheme),
    ):
        # If Bearer token provided and GL-IAM enabled, check GL-IAM roles
        if bearer_token and settings.gliam_enabled:
            try:
                gateway = get_iam_gateway()
                user = await gateway.validate_session(
                    bearer_token.credentials,
                    organization_id=settings.gliam_organization_id,
                )
                if user and user.has_standard_role(StandardRole.ORG_MEMBER):
                    return  # GL-IAM auth successful
                elif user:
                    raise HTTPException(status_code=403, detail="ORG_MEMBER role required")
            except HTTPException:
                raise
            except Exception:
                pass  # Fall through to API key check

        # Fall back to legacy API key
        if api_key:
            await verify_api_key(api_key)  # Any valid API key is OK for member
            return

        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token or X-API-Key.",
        )

    return unified_check


def require_org_admin():
    """Require ORG_ADMIN role (GL-IAM) or master API key (legacy).
    
    This unified dependency supports both:
    - GL-IAM Bearer token authentication with ORG_ADMIN role checking
    - Legacy X-API-Key authentication (master API key only)
    """
    async def unified_check(
        bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
        api_key: str | None = Security(api_key_scheme),
    ):
        # If Bearer token provided and GL-IAM enabled, check GL-IAM roles
        if bearer_token and settings.gliam_enabled:
            try:
                gateway = get_iam_gateway()
                user = await gateway.validate_session(
                    bearer_token.credentials,
                    organization_id=settings.gliam_organization_id,
                )
                if user and user.has_standard_role(StandardRole.ORG_ADMIN):
                    return  # GL-IAM admin auth successful
                elif user:
                    raise HTTPException(status_code=403, detail="ORG_ADMIN role required")
            except HTTPException:
                raise
            except Exception:
                pass  # Fall through to API key check

        # Fall back to legacy API key - require master key for admin
        if api_key:
            if api_key == settings.aip_master_api_key:
                return  # Master key = admin access
            raise HTTPException(status_code=403, detail="Admin access requires master API key")

        raise HTTPException(
            status_code=HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token or X-API-Key.",
        )

    return unified_check


# =============================================================================
# Application Setup
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with GL-IAM initialization."""
    provider = None

    # Initialize GL-IAM if configured
    if settings.gliam_enabled:
        config = PostgreSQLUserStoreConfig(
            database_url=settings.aip_db_url,
            secret_key=settings.gliam_secret_key,
            enable_auth_hosting=settings.gliam_enable_auth_hosting,
            auto_create_tables=settings.gliam_auto_create_tables,
        )
        provider = PostgreSQLProvider(config)
        gateway = IAMGateway.from_fullstack_provider(provider)

        # Make gateway available to FastAPI dependencies
        set_iam_gateway(gateway, default_organization_id=settings.gliam_organization_id)
        print(f"GL-IAM initialized with organization: {settings.gliam_organization_id}")
    else:
        print("GL-IAM not configured - using legacy API key auth only")

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
    """Register a new user (GL-IAM only)."""
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
    """Login and get access token (GL-IAM only)."""
    if not settings.gliam_enabled:
        raise HTTPException(status_code=501, detail="GL-IAM not configured")

    gateway = get_iam_gateway()

    try:
        result = await gateway.authenticate(
            credentials=PasswordCredentials(email=request.email, password=request.password),
            organization_id=settings.gliam_organization_id,
        )
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")


# =============================================================================
# Protected Endpoints (Unified Auth)
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
    identity=Depends(get_unified_identity),
):
    """
    List agents for the current account.

    Supports both:
    - Bearer token (GL-IAM): Returns agents for user's organization
    - X-API-Key (legacy): Returns agents for account
    """
    account_id = get_account_id_from_identity(identity)

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
    identity=Depends(get_unified_identity),
):
    """
    Create a new agent.

    Authentication:
    - Bearer token: GL-IAM user (ORG_MEMBER role required)
    - X-API-Key: Legacy API key
    """
    account_id = get_account_id_from_identity(identity)

    # Demo response - in real server, create in database
    return AgentResponse(
        id="new-agent-1",
        name=name,
        account_id=str(account_id) if account_id else None,
    )


@app.get("/admin/accounts")
async def list_accounts(
    _: None = Depends(require_org_admin()),
    identity=Depends(get_unified_identity),
):
    """
    Admin endpoint to list all accounts.

    Requires ORG_ADMIN role (GL-IAM) or master API key (legacy).
    """
    return {"accounts": ["account-1", "account-2"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
