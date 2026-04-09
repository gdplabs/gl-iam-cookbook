"""Key management service with focused interfaces.

This module implements Interface Segregation Principle by separating
key creation and validation into distinct service classes.

Each class has a single responsibility:
- KeyCreationService: Creating API keys of various types
- KeyValidationService: Validating and checking API key permissions
"""

from datetime import datetime, timedelta, timezone

from gl_iam.core.types.api_key import ApiKeyTier, ApiKey, ApiKeyIdentity
from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider


class KeyCreationService:
    """Service for creating API keys.

    This service encapsulates the logic for creating different types
    of API keys: platform keys, organization keys, and child keys.

    Attributes:
        _provider: The underlying API key provider.
    """

    def __init__(self, provider: PostgreSQLApiKeyProvider):
        """Initialize the key creation service.

        Args:
            provider: PostgreSQL API key provider instance.
        """
        self._provider = provider

    async def create_platform_key(
        self,
        name: str,
        scopes: list[str] | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a PLATFORM tier key for system administration.

        PLATFORM keys have no organization or user context and can
        create keys of any tier. Used for initial system bootstrap.

        Args:
            name: Human-readable name for the key.
            scopes: List of scopes to grant. Defaults to admin scopes.

        Returns:
            Tuple of (ApiKey metadata, plain key string).

        Example:
            >>> key, secret = await service.create_platform_key("Bootstrap")
            >>> print(f"Store this securely: {secret}")
        """
        if scopes is None:
            scopes = ["*"]  # Platform keys typically have full access

        return await self._provider.create_api_key(
            name=name,
            tier=ApiKeyTier.PLATFORM,
            scopes=scopes,
        )

    async def create_forever_org_key(
        self,
        name: str,
        organization_id: str,
        scopes: list[str],
    ) -> tuple[ApiKey, str]:
        """Create a forever ORGANIZATION key (no expiration).

        Forever keys are the primary keys for an organization.
        They never expire and can create child keys.

        Args:
            name: Human-readable name for the key.
            organization_id: Organization this key belongs to.
            scopes: List of scopes to grant.

        Returns:
            Tuple of (ApiKey metadata, plain key string).

        Example:
            >>> key, secret = await service.create_forever_org_key(
            ...     name="Primary API Key",
            ...     organization_id="acme-123",
            ...     scopes=["agents:execute", "agents:read", "keys:create"],
            ... )
        """
        return await self._provider.create_api_key(
            name=name,
            tier=ApiKeyTier.ORGANIZATION,
            organization_id=organization_id,
            scopes=scopes,
            expires_at=None,  # Never expires
        )

    async def create_child_key(
        self,
        name: str,
        organization_id: str,
        parent_key_id: str,
        scopes: list[str],
        expires_in_days: int,
    ) -> tuple[ApiKey, str]:
        """Create a limited-lifetime child key.

        Child keys are created by parent keys and inherit their
        organization context. They must have a subset of parent scopes.

        Args:
            name: Human-readable name for the key.
            organization_id: Organization this key belongs to.
            parent_key_id: ID of the parent key that created this key.
            scopes: List of scopes (must be subset of parent's scopes).
            expires_in_days: Number of days until key expires.

        Returns:
            Tuple of (ApiKey metadata, plain key string).

        Example:
            >>> key, secret = await service.create_child_key(
            ...     name="CI/CD Key",
            ...     organization_id="acme-123",
            ...     parent_key_id=parent.id,
            ...     scopes=["agents:execute"],
            ...     expires_in_days=30,
            ... )
        """
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            days=expires_in_days
        )

        return await self._provider.create_api_key(
            name=name,
            tier=ApiKeyTier.ORGANIZATION,
            organization_id=organization_id,
            scopes=scopes,
            expires_at=expires_at,
            parent_key_id=parent_key_id,
        )


class KeyValidationService:
    """Service for validating API keys.

    This service encapsulates validation and permission checking logic.
    Separated from creation to follow Interface Segregation Principle.

    Attributes:
        _provider: The underlying API key provider.
    """

    def __init__(self, provider: PostgreSQLApiKeyProvider):
        """Initialize the key validation service.

        Args:
            provider: PostgreSQL API key provider instance.
        """
        self._provider = provider

    async def validate(self, plain_key: str) -> ApiKeyIdentity | None:
        """Validate an API key and return its identity.

        Args:
            plain_key: The plain text API key to validate.

        Returns:
            ApiKeyIdentity if valid, None if invalid or expired.

        Example:
            >>> identity = await service.validate("aip_abc123...")
            >>> if identity:
            ...     print(f"Key belongs to org: {identity.organization_id}")
        """
        return await self._provider.validate_api_key(plain_key)

    async def has_scope(self, plain_key: str, scope: str) -> bool:
        """Check if an API key has a specific scope.

        Args:
            plain_key: The plain text API key to check.
            scope: The scope to check for.

        Returns:
            True if key has the scope, False otherwise.

        Example:
            >>> if await service.has_scope(key, "agents:execute"):
            ...     print("Key can execute agents")
        """
        identity = await self.validate(plain_key)
        if identity is None:
            return False
        return identity.has_scope(scope)

    async def has_any_scope(self, plain_key: str, scopes: list[str]) -> bool:
        """Check if an API key has any of the specified scopes.

        Args:
            plain_key: The plain text API key to check.
            scopes: List of scopes to check for.

        Returns:
            True if key has at least one scope, False otherwise.
        """
        identity = await self.validate(plain_key)
        if identity is None:
            return False
        return identity.has_any_scope(scopes)

    async def can_create_child(self, plain_key: str) -> bool:
        """Check if an API key can create child keys.

        Creating child keys requires:
        1. The "keys:create" scope
        2. A tier that allows key creation (not PERSONAL)

        Args:
            plain_key: The plain text API key to check.

        Returns:
            True if key can create children, False otherwise.
        """
        identity = await self.validate(plain_key)
        if identity is None:
            return False
        return identity.can_create_keys()
