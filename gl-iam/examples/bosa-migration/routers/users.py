"""User management endpoints.

BOSA Migration Mapping:
- create_user() -> POST /api/users
- get_user() -> GET /api/users/{id} or GET /api/users/me
"""

from fastapi import APIRouter, Depends, HTTPException, status

from gl_iam.core.types import UserCreateInput

from config import settings
from deps import (
    ApiKeyIdentityDep,
    CurrentUserDep,
    provider,
    require_scope,
)
from schemas import UserCreateRequest, UserResponse

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("users:create"))],
)
async def create_user(
    request: UserCreateRequest,
    identity: ApiKeyIdentityDep,
):
    """Create a new user.

    BOSA Equivalent: create_user()

    Requires 'users:create' scope on API key.

    Args:
        request: User creation request.
        identity: Authenticated API key identity.

    Returns:
        Created user.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    # Create user via provider
    user_input = UserCreateInput(
        email=request.email,
        display_name=request.display_name or request.email.split("@")[0],
    )

    try:
        user = await provider.create_user(user_input, organization_id)
    except Exception as e:
        if "already exists" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email {request.email} already exists",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

    # Set password
    await provider.set_user_password(user.id, request.password, organization_id)

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(user: CurrentUserDep):
    """Get current authenticated user.

    BOSA Equivalent: get_user() with current user context

    Requires Bearer token authentication.

    Args:
        user: Current authenticated user from JWT.

    Returns:
        Current user details.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id(
    user_id: str,
    identity: ApiKeyIdentityDep,
):
    """Get a user by ID.

    BOSA Equivalent: get_user()

    Requires API key authentication.

    Args:
        user_id: The user's ID.
        identity: Authenticated API key identity.

    Returns:
        User details.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    user = await provider.get_user_by_id(user_id, organization_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.get("/by-email/{email}", response_model=UserResponse)
async def get_user_by_email(
    email: str,
    identity: ApiKeyIdentityDep,
):
    """Get a user by email.

    BOSA Equivalent: get_user() by email

    Requires API key authentication.

    Args:
        email: The user's email address.
        identity: Authenticated API key identity.

    Returns:
        User details.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    user = await provider.get_user_by_email(email, organization_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with email {email} not found",
        )

    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    identity: ApiKeyIdentityDep,
):
    """Delete a user.

    Requires API key authentication with appropriate permissions.

    Args:
        user_id: The user's ID to delete.
        identity: Authenticated API key identity.
    """
    organization_id = identity.organization_id or settings.default_organization_id

    try:
        await provider.delete_user(user_id, organization_id)
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )
        raise
