"""Third-party integration endpoints.

This module demonstrates GL-IAM's third-party integration provider for
storing and managing external service credentials (e.g., GitHub, Slack tokens).

BOSA Migration Mapping:
- create_integration() -> POST /api/integrations
- get_integration() -> GET /api/integrations/{connector}
- get_selected_integration() -> GET /api/integrations/{connector}/selected
- set_selected_integration() -> POST /api/integrations/{connector}/selected
- delete_integration() -> DELETE /api/integrations/{id}
- has_integration() -> GET /api/integrations/{connector}/exists
"""

from fastapi import APIRouter, HTTPException, status

from gl_iam.core.exceptions import IntegrationAlreadyExistsError, IntegrationNotFoundError

from config import settings
from deps import CurrentUserDep, get_third_party_provider
from schemas import (
    IntegrationResponse,
    SetSelectedIntegrationRequest,
    StoreIntegrationRequest,
)

router = APIRouter(prefix="/api/integrations", tags=["Third-Party Integrations"])


@router.post("", response_model=IntegrationResponse, status_code=status.HTTP_201_CREATED)
async def store_integration(
    request: StoreIntegrationRequest,
    user: CurrentUserDep,
):
    """Store a new third-party integration.

    BOSA Equivalent: create_integration()

    The auth_string (token/credentials) is encrypted at rest using Fernet
    encryption. The first integration for a connector becomes automatically
    selected.

    Args:
        request: Integration details including connector, auth_string, etc.
        user: Current authenticated user.

    Returns:
        Created integration details.
    """
    third_party_provider = get_third_party_provider()

    try:
        integration = await third_party_provider.store_integration(
            user_id=user.id,
            connector=request.connector,
            auth_string=request.auth_string,
            organization_id=settings.default_organization_id,
            user_identifier=request.user_identifier,
            scopes=request.scopes,
            metadata=request.metadata,
        )
    except IntegrationAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Integration already exists for {request.connector}/{request.user_identifier}",
        )

    return IntegrationResponse(
        id=integration.id,
        connector=integration.connector,
        user_identifier=integration.user_identifier,
        auth_string_preview=integration.auth_string_preview,
        scopes=integration.scopes,
        is_selected=integration.is_selected,
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
        metadata=integration.metadata,
    )


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    user: CurrentUserDep,
    connector: str | None = None,
):
    """List user's third-party integrations.

    BOSA Equivalent: get_integrations()

    Args:
        user: Current authenticated user.
        connector: Optional filter by connector name.

    Returns:
        List of integrations.
    """
    third_party_provider = get_third_party_provider()

    integrations = await third_party_provider.get_integrations(
        user_id=user.id,
        organization_id=settings.default_organization_id,
        connector=connector,
    )

    return [
        IntegrationResponse(
            id=i.id,
            connector=i.connector,
            user_identifier=i.user_identifier,
            auth_string_preview=i.auth_string_preview,
            scopes=i.scopes,
            is_selected=i.is_selected,
            is_active=i.is_active,
            created_at=i.created_at,
            updated_at=i.updated_at,
            metadata=i.metadata,
        )
        for i in integrations
    ]


@router.get("/{connector}/selected", response_model=IntegrationResponse | None)
async def get_selected_integration(
    connector: str,
    user: CurrentUserDep,
):
    """Get the selected (default) integration for a connector.

    BOSA Equivalent: get_selected_integration()

    Each connector can have multiple integrations (accounts), but only
    one is "selected" as the default.

    Args:
        connector: Third-party service name (e.g., 'github').
        user: Current authenticated user.

    Returns:
        Selected integration or None if no integration exists.
    """
    third_party_provider = get_third_party_provider()

    integration = await third_party_provider.get_selected_integration(
        user_id=user.id,
        connector=connector,
        organization_id=settings.default_organization_id,
    )

    if not integration:
        return None

    return IntegrationResponse(
        id=integration.id,
        connector=integration.connector,
        user_identifier=integration.user_identifier,
        auth_string_preview=integration.auth_string_preview,
        scopes=integration.scopes,
        is_selected=integration.is_selected,
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
        metadata=integration.metadata,
    )


@router.post("/{connector}/selected", status_code=status.HTTP_204_NO_CONTENT)
async def set_selected_integration(
    connector: str,
    request: SetSelectedIntegrationRequest,
    user: CurrentUserDep,
):
    """Set the selected (default) integration for a connector.

    BOSA Equivalent: set_selected_integration()

    Args:
        connector: Third-party service name.
        request: Request with user_identifier to select.
        user: Current authenticated user.
    """
    third_party_provider = get_third_party_provider()

    if request.connector != connector:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connector in path and body must match",
        )

    try:
        await third_party_provider.set_selected_integration(
            user_id=user.id,
            connector=connector,
            user_identifier=request.user_identifier,
            organization_id=settings.default_organization_id,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration not found: {connector}/{request.user_identifier}",
        )


@router.get("/{connector}/exists")
async def has_integration(
    connector: str,
    user: CurrentUserDep,
):
    """Check if user has any integration for a connector.

    BOSA Equivalent: has_integration()

    Args:
        connector: Third-party service name.
        user: Current authenticated user.

    Returns:
        Boolean indicating if integration exists.
    """
    third_party_provider = get_third_party_provider()

    exists = await third_party_provider.has_integration(
        user_id=user.id,
        connector=connector,
        organization_id=settings.default_organization_id,
    )

    return {"exists": exists}


@router.get("/{connector}/{user_identifier}", response_model=IntegrationResponse)
async def get_integration_by_user_identifier(
    connector: str,
    user_identifier: str,
    user: CurrentUserDep,
):
    """Get a specific integration by connector and user identifier.

    BOSA Equivalent: get_integration()

    Args:
        connector: Third-party service name.
        user_identifier: Account identifier in the third-party service.
        user: Current authenticated user.

    Returns:
        Integration details.
    """
    third_party_provider = get_third_party_provider()

    integration = await third_party_provider.get_integration_by_user_identifier(
        user_id=user.id,
        connector=connector,
        user_identifier=user_identifier,
        organization_id=settings.default_organization_id,
    )

    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration not found: {connector}/{user_identifier}",
        )

    return IntegrationResponse(
        id=integration.id,
        connector=integration.connector,
        user_identifier=integration.user_identifier,
        auth_string_preview=integration.auth_string_preview,
        scopes=integration.scopes,
        is_selected=integration.is_selected,
        is_active=integration.is_active,
        created_at=integration.created_at,
        updated_at=integration.updated_at,
        metadata=integration.metadata,
    )


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    user: CurrentUserDep,
):
    """Delete an integration.

    BOSA Equivalent: delete_integration()

    If the deleted integration was selected, the most recently created
    integration for the same connector will become selected.

    Args:
        integration_id: The integration's ID.
        user: Current authenticated user.
    """
    third_party_provider = get_third_party_provider()

    try:
        await third_party_provider.delete_integration(
            integration_id=integration_id,
            organization_id=settings.default_organization_id,
        )
    except IntegrationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Integration {integration_id} not found",
        )
