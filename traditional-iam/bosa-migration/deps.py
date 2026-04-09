"""FastAPI dependencies for authentication and authorization.

This module provides:
- Provider initialization
- API key validation dependency
- JWT session validation dependency
- Scope-based authorization

BOSA Migration Mapping:
- verify_client() -> get_api_key_identity()
- verify_token() -> get_current_user()
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from gl_iam import User, StandardRole
from gl_iam.core.types.api_key import ApiKeyIdentity, ApiKeyTier
from gl_iam.providers.postgresql import (
    PostgreSQLApiKeyProvider,
    PostgreSQLProvider,
    PostgreSQLThirdPartyProvider,
    PostgreSQLConfig,
)

from config import settings

# =============================================================================
# Provider Initialization
# =============================================================================

# Configuration for all providers
_config = PostgreSQLConfig(
    database_url=settings.database_url,
    secret_key=settings.secret_key,
    encryption_key=settings.encryption_key,
    enable_auth_hosting=True,
    auto_create_tables=True,
)

# Main provider (users, sessions, RBAC)
provider = PostgreSQLProvider(_config)

# API Key provider (3-tier model)
api_key_provider = PostgreSQLApiKeyProvider(provider._engine, _config)

# Third-party integration provider
# Only initialize if encryption key is configured
third_party_provider: PostgreSQLThirdPartyProvider | None = None
if settings.encryption_key:
    third_party_provider = PostgreSQLThirdPartyProvider(
        provider._engine,
        encryption_key=settings.encryption_key,
        db_schema=_config.db_schema,
    )


async def ensure_all_tables() -> None:
    """Ensure all database tables are created.

    This function creates ALL tables including base tables (organizations, users, etc.)
    and additional tables (api_keys, third_party_integrations).
    Using Base.metadata.create_all() without specifying tables ensures proper
    ordering based on foreign key dependencies.
    """
    from sqlalchemy import text
    from gl_iam.providers.postgresql.models import Base

    async with provider._engine.begin() as conn:
        # Create schema if it doesn't exist
        if _config.db_schema:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {_config.db_schema}"))

        # Create ALL tables - this handles foreign key dependencies automatically
        await conn.run_sync(Base.metadata.create_all)


# =============================================================================
# Security Schemes
# =============================================================================

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False, description="API Key for machine-to-machine authentication")


# =============================================================================
# API Key Authentication (BOSA: verify_client)
# =============================================================================


async def get_api_key_identity(
    x_api_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> ApiKeyIdentity:
    """Validate API key and return identity.

    This is equivalent to BOSA's verify_client() function.

    Args:
        x_api_key: API key from X-API-Key header.

    Returns:
        ApiKeyIdentity with key details and scopes.

    Raises:
        HTTPException 401: If API key is missing or invalid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    identity = await api_key_provider.validate_api_key(x_api_key)
    if not identity:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
        )

    return identity


# Type alias for dependency injection
ApiKeyIdentityDep = Annotated[ApiKeyIdentity, Depends(get_api_key_identity)]


# =============================================================================
# JWT Session Authentication (BOSA: verify_token)
# =============================================================================


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ] = None,
) -> User:
    """Validate JWT and return current user.

    This is equivalent to BOSA's verify_token() function.

    Args:
        credentials: Bearer token from Authorization header.

    Returns:
        User object for the authenticated user.

    Raises:
        HTTPException 401: If token is missing or invalid.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await provider.validate_session(
        credentials.credentials,
        settings.default_organization_id,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# Type alias for dependency injection
CurrentUserDep = Annotated[User, Depends(get_current_user)]


# =============================================================================
# Scope-Based Authorization
# =============================================================================


def require_scope(scope: str):
    """Dependency factory to require a specific scope on API key.

    Usage:
        @router.get("/admin", dependencies=[Depends(require_scope("admin"))])
        async def admin_endpoint(): ...

    Args:
        scope: The required scope (e.g., "keys:create", "api:write").

    Returns:
        Dependency function that validates the scope.
    """

    async def _check_scope(
        identity: ApiKeyIdentityDep,
    ) -> None:
        if not identity.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {scope}",
            )

    return _check_scope


def require_any_scope(*scopes: str):
    """Dependency factory to require any of the specified scopes.

    Usage:
        @router.get("/data", dependencies=[Depends(require_any_scope("api:read", "api:write"))])
        async def data_endpoint(): ...

    Args:
        scopes: One or more acceptable scopes.

    Returns:
        Dependency function that validates at least one scope is present.
    """

    async def _check_scopes(
        identity: ApiKeyIdentityDep,
    ) -> None:
        if not identity.has_any_scope(list(scopes)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: one of {scopes}",
            )

    return _check_scopes


def require_tier(tier: ApiKeyTier):
    """Dependency factory to require a specific API key tier.

    Usage:
        @router.post("/platform", dependencies=[Depends(require_tier(ApiKeyTier.PLATFORM))])
        async def platform_endpoint(): ...

    Args:
        tier: The required tier.

    Returns:
        Dependency function that validates the tier.
    """

    async def _check_tier(
        identity: ApiKeyIdentityDep,
    ) -> None:
        # Tier hierarchy: PLATFORM > ORGANIZATION > PERSONAL
        tier_hierarchy = {
            ApiKeyTier.PLATFORM: 3,
            ApiKeyTier.ORGANIZATION: 2,
            ApiKeyTier.PERSONAL: 1,
        }
        if tier_hierarchy.get(identity.tier, 0) < tier_hierarchy.get(tier, 0):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {tier.value} tier or higher",
            )

    return _check_tier


# =============================================================================
# Standard Role-Based Authorization (User RBAC)
# =============================================================================


def require_standard_role(role: StandardRole):
    """Require user to have a standard role (respects hierarchy).

    Role Hierarchy:
        PLATFORM_ADMIN → ORG_ADMIN → ORG_MEMBER

    Usage:
        @router.get("/admin", dependencies=[Depends(require_standard_role(StandardRole.ORG_ADMIN))])
        async def admin_endpoint(): ...

    Args:
        role: The required standard role.

    Returns:
        Dependency function that validates the role.
    """

    async def _check_role(user: CurrentUserDep) -> None:
        if not user.has_standard_role(role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires {role.value} role or higher",
            )

    return _check_role


def require_org_admin():
    """Require ORG_ADMIN or PLATFORM_ADMIN role."""
    return require_standard_role(StandardRole.ORG_ADMIN)


def require_org_member():
    """Require ORG_MEMBER or higher role."""
    return require_standard_role(StandardRole.ORG_MEMBER)


def require_platform_admin():
    """Require PLATFORM_ADMIN role (highest privilege)."""
    return require_standard_role(StandardRole.PLATFORM_ADMIN)


# =============================================================================
# Utility Functions
# =============================================================================


def get_third_party_provider() -> PostgreSQLThirdPartyProvider:
    """Get the third-party provider or raise if not configured.

    Returns:
        PostgreSQLThirdPartyProvider instance.

    Raises:
        HTTPException 503: If encryption key is not configured.
    """
    if not third_party_provider:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Third-party integrations not configured. Set ENCRYPTION_KEY in .env",
        )
    return third_party_provider
