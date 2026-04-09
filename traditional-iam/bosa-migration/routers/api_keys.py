"""API Key management endpoints.

Demonstrates 3-tier API key model:
- PLATFORM: System-level bootstrap keys (org_id=NULL, user_id=NULL)
- ORGANIZATION: Organization-level keys (org_id=REQUIRED, user_id=NULL)
- PERSONAL: User-level keys (org_id=REQUIRED, user_id=REQUIRED)

BOSA Migration Mapping:
- create_client() -> POST /api/keys (tier=organization)
- verify_client() -> See deps.py get_api_key_identity()
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from gl_iam.core.types.api_key import ApiKeyTier

from config import settings
from deps import (
    ApiKeyIdentityDep,
    api_key_provider,
    require_scope,
)
from schemas import ApiKeyCreateRequest, ApiKeyCreatedResponse, ApiKeyResponse

router = APIRouter(prefix="/api/keys", tags=["API Keys"])


@router.post(
    "",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("keys:create"))],
)
async def create_api_key(
    request: ApiKeyCreateRequest,
    identity: ApiKeyIdentityDep,
):
    """Create a new API key.

    BOSA Equivalent: create_client()

    Requires 'keys:create' scope. The creating key's scopes are inherited
    as the maximum scopes for the new key (scope inheritance).

    Tier Rules:
    - PLATFORM: Can create any tier
    - ORGANIZATION: Can create ORGANIZATION or PERSONAL
    - PERSONAL: Cannot create keys

    Args:
        request: API key creation request.
        identity: Authenticated API key identity.

    Returns:
        Created API key with plain key value (shown only once).
    """
    # Parse and validate tier
    try:
        tier = ApiKeyTier(request.tier.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tier: {request.tier}. Must be: platform, organization, personal",
        )

    # Check tier creation permission
    if not identity.can_create_tier(tier):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your key ({identity.tier.value}) cannot create {tier.value} tier keys",
        )

    # Validate scopes (cannot exceed creator's scopes)
    for scope in request.scopes:
        if scope not in identity.scopes and "*" not in identity.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Cannot grant scope '{scope}' - not in your scopes",
            )

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=request.expires_in_days)

    # Determine organization_id based on tier
    organization_id = None
    if tier in (ApiKeyTier.ORGANIZATION, ApiKeyTier.PERSONAL):
        organization_id = identity.organization_id or settings.default_organization_id

    # Create the key
    api_key, plain_key = await api_key_provider.create_api_key(
        name=request.name,
        tier=tier,
        organization_id=organization_id,
        scopes=request.scopes,
        expires_at=expires_at,
        user_id=request.user_id,
        parent_key_id=identity.api_key_id,
    )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_preview=api_key.key_preview,
        tier=api_key.tier.value,
        scopes=api_key.scopes,
        organization_id=api_key.organization_id,
        user_id=api_key.user_id,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        plain_key=plain_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    identity: ApiKeyIdentityDep,
    tier: str | None = None,
    include_revoked: bool = False,
):
    """List API keys visible to the authenticated key.

    Args:
        identity: Authenticated API key identity.
        tier: Optional tier filter (platform, organization, personal).
        include_revoked: Whether to include revoked keys.

    Returns:
        List of API keys.
    """
    # Parse tier filter if provided
    tier_filter = None
    if tier:
        try:
            tier_filter = ApiKeyTier(tier.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid tier: {tier}",
            )

    # Get organization_id from identity or settings
    organization_id = identity.organization_id or settings.default_organization_id

    keys = await api_key_provider.list_api_keys(
        organization_id=organization_id if identity.tier != ApiKeyTier.PLATFORM else None,
        tier=tier_filter,
        include_revoked=include_revoked,
    )

    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            key_preview=k.key_preview,
            tier=k.tier.value,
            scopes=k.scopes,
            organization_id=k.organization_id,
            user_id=k.user_id,
            is_active=k.is_active,
            expires_at=k.expires_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(
    key_id: str,
    identity: ApiKeyIdentityDep,
):
    """Get a specific API key by ID.

    Args:
        key_id: The API key ID.
        identity: Authenticated API key identity.

    Returns:
        API key details.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    api_key = await api_key_provider.get_api_key(
        key_id=key_id,
        organization_id=organization_id if identity.tier != ApiKeyTier.PLATFORM else None,
    )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )

    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_preview=api_key.key_preview,
        tier=api_key.tier.value,
        scopes=api_key.scopes,
        organization_id=api_key.organization_id,
        user_id=api_key.user_id,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    identity: ApiKeyIdentityDep,
):
    """Revoke an API key.

    Args:
        key_id: The API key ID to revoke.
        identity: Authenticated API key identity.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    success = await api_key_provider.revoke_api_key(
        key_id=key_id,
        organization_id=organization_id if identity.tier != ApiKeyTier.PLATFORM else None,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found or already revoked",
        )


@router.post("/{key_id}/rotate", response_model=ApiKeyCreatedResponse)
async def rotate_api_key(
    key_id: str,
    identity: ApiKeyIdentityDep,
):
    """Rotate an API key (generate new key value).

    The key ID and all metadata remain the same, only the key value changes.

    Args:
        key_id: The API key ID to rotate.
        identity: Authenticated API key identity.

    Returns:
        Updated API key with new plain key value.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    try:
        api_key, plain_key = await api_key_provider.rotate_api_key(
            key_id=key_id,
            organization_id=organization_id if identity.tier != ApiKeyTier.PLATFORM else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_preview=api_key.key_preview,
        tier=api_key.tier.value,
        scopes=api_key.scopes,
        organization_id=api_key.organization_id,
        user_id=api_key.user_id,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        created_at=api_key.created_at,
        plain_key=plain_key,
    )
