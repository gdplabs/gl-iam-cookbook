"""
AIP Server Integration with GL-IAM.

This example demonstrates how to integrate GL-IAM into an AIP server
using Bearer token authentication with role-based access control.
"""

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
from gl_iam.core.types.api_key import ApiKeyIdentity, ApiKeyTier
from gl_iam.fastapi import (
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

    # Existing AIP API Keys (backward compatibility). Exact-match legacy master
    # key, still accepted alongside GL-IAM-issued API keys and Bearer tokens
    # (see get_unified_identity()).
    aip_master_api_key: str | None = None

    @property
    def gliam_enabled(self) -> bool:
        """Check if GL-IAM is configured."""
        return self.gliam_secret_key is not None

    class Config:
        env_file = ".env"
        # Ignore .env keys this Settings class doesn't declare (e.g. ENV=,
        # consumed separately by PostgreSQLConfig's own os.environ-based
        # security validator) instead of raising ValidationError on them.
        extra = "ignore"


settings = Settings()


# =============================================================================
# Security Schemes
# =============================================================================
bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


# =============================================================================
# GL-IAM Unified Authentication (Bearer token OR X-API-Key)
# =============================================================================
UnifiedIdentity = User | ApiKeyIdentity


async def get_unified_identity(
    bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key: str | None = Security(api_key_scheme),
) -> UnifiedIdentity:
    """
    Get current identity from either a GL-IAM Bearer token or an X-API-Key header.

    Priority:
        1. Bearer token (GL-IAM session) -> Returns User
        2. X-API-Key:
           a. Legacy master key (exact match against AIP_MASTER_API_KEY) ->
              synthetic PLATFORM-tier ApiKeyIdentity, for backward compatibility
              with the pre-GL-IAM master-key check.
           b. GL-IAM-issued API key -> ApiKeyIdentity, validated via
              gateway.api_key_provider (ApiKeyProvider protocol)

    Returns:
        User | ApiKeyIdentity: The authenticated identity.

    Raises:
        HTTPException: If GL-IAM is not enabled, or no valid Bearer token or
            API key is presented.
    """
    if not settings.gliam_enabled:
        raise HTTPException(status_code=501, detail="GL-IAM not enabled")

    if bearer_token:
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

    if api_key:
        if settings.aip_master_api_key and api_key == settings.aip_master_api_key:
            return ApiKeyIdentity(
                api_key_id="legacy-master-key",
                name="Legacy Master Key",
                tier=ApiKeyTier.PLATFORM,
            )

        gateway = get_iam_gateway()
        if gateway.api_key_provider is None:
            raise HTTPException(status_code=501, detail="GL-IAM API key provider not configured")

        identity = await gateway.api_key_provider.validate_api_key(api_key)
        if identity is None:
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid or expired API key")
        return identity

    raise HTTPException(
        status_code=HTTP_401_UNAUTHORIZED,
        detail="Bearer token or X-API-Key required",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_account_id_from_identity(identity: UnifiedIdentity) -> UUID | None:
    """
    Extract account/organization ID as UUID for data scoping.

    Works for both GL-IAM Users (Bearer auth) and ApiKeyIdentity (API key
    auth). Returns None for PLATFORM-tier identities (e.g. the legacy master
    key), which are not scoped to a single organization.

    Returns:
        UUID of the organization or None if not available
    """
    org_id = getattr(identity, "organization_id", None)
    if not org_id:
        return None
    try:
        return UUID(org_id)
    except ValueError:
        return None


# =============================================================================
# Role-Based Dependencies
# =============================================================================
def _is_org_admin(identity: UnifiedIdentity) -> bool:
    """Check ORG_ADMIN-equivalent access for either Bearer or API key identity."""
    if isinstance(identity, User):
        return identity.has_standard_role(StandardRole.ORG_ADMIN)
    # ApiKeyIdentity: PLATFORM tier = master key (full access, see role mapping
    # in README); ORGANIZATION tier needs the "org:admin" scope (Account Owner).
    return identity.tier == ApiKeyTier.PLATFORM or (
        identity.tier == ApiKeyTier.ORGANIZATION and "org:admin" in identity.scopes
    )


def _is_org_member(identity: UnifiedIdentity) -> bool:
    """Check ORG_MEMBER-equivalent access for either Bearer or API key identity."""
    if isinstance(identity, User):
        return identity.has_standard_role(StandardRole.ORG_MEMBER)
    # Any valid API key (master, organization, or personal tier) counts as at
    # least ORG_MEMBER access (Account Member, see role mapping in README).
    return True


def require_org_member():
    """Require ORG_MEMBER role via GL-IAM (Bearer token or API key)."""

    async def check(identity: UnifiedIdentity = Depends(get_unified_identity)):
        if not _is_org_member(identity):
            raise HTTPException(status_code=403, detail="ORG_MEMBER role required")

    return check


def require_org_admin():
    """Require ORG_ADMIN role via GL-IAM (Bearer token or API key)."""

    async def check(identity: UnifiedIdentity = Depends(get_unified_identity)):
        if not _is_org_admin(identity):
            raise HTTPException(status_code=403, detail="ORG_ADMIN role required")

    return check


# =============================================================================
# Application Setup
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with GL-IAM initialization."""
    provider = None

    if settings.gliam_enabled:
        config = PostgreSQLConfig(
            database_url=settings.aip_db_url,
            secret_key=settings.gliam_secret_key,
            enable_auth_hosting=settings.gliam_enable_auth_hosting,
            auto_create_tables=settings.gliam_auto_create_tables,
            default_org_id=settings.gliam_organization_id,
        )
        provider = PostgreSQLProvider(config)
        # Wired manually (rather than IAMGateway.from_fullstack_provider) so that
        # gateway.api_key_provider is populated. from_fullstack_provider() only
        # picks up a provider's `.api_key_provider` *attribute*; PostgreSQLProvider
        # implements the ApiKeyProvider protocol directly via mixin composition,
        # not as a separate sub-attribute, so it would otherwise be left as None.
        gateway = IAMGateway(
            auth_provider=provider,
            user_store=provider,
            session_provider=provider,
            organization_provider=provider,
            api_key_provider=provider,
        )
        set_iam_gateway(gateway, default_organization_id=settings.gliam_organization_id)
        print(f"GL-IAM initialized with organization: {settings.gliam_organization_id}")
    else:
        print("GL-IAM not configured - set GLIAM_SECRET_KEY to enable")

    yield

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
    identity: UnifiedIdentity = Depends(get_unified_identity),
):
    """
    List agents for the current user's organization.

    Requires ORG_MEMBER role. Accepts either a GL-IAM Bearer token or an
    X-API-Key (legacy master key or GL-IAM-issued API key).
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
    identity: UnifiedIdentity = Depends(get_unified_identity),
):
    """
    Create a new agent.

    Requires ORG_MEMBER role. Accepts either a GL-IAM Bearer token or an
    X-API-Key (legacy master key or GL-IAM-issued API key).
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
    identity: UnifiedIdentity = Depends(get_unified_identity),
):
    """
    Admin endpoint to list all accounts.

    Requires ORG_ADMIN role. Accepts either a GL-IAM Bearer token or an
    X-API-Key (legacy master key or GL-IAM-issued API key with "org:admin" scope).
    """
    return {"accounts": ["account-1", "account-2"]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
