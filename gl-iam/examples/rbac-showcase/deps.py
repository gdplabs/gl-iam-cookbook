"""
FastAPI dependencies for RBAC Showcase.

This module provides authentication dependencies and RBAC validation helpers
that work with both Keycloak and StackAuth providers.
"""

from typing import Annotated

from fastapi import Depends, Header

from gl_iam import User
from gl_iam.core.exceptions import AuthenticationError, PermissionDeniedError
from gl_iam.core.roles.standard import StandardRole
from gl_iam.fastapi import (
    get_current_user,
    require_org_admin,
    require_org_member,
    require_platform_admin,
    require_standard_role,
)

# Re-export GL-IAM dependencies for convenience
__all__ = [
    "get_current_user",
    "require_org_admin",
    "require_org_member",
    "require_platform_admin",
    "require_standard_role",
    "CurrentUser",
    "get_current_user_with_roles",
]


# Type alias for dependency injection
CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_user_with_roles(
    authorization: str | None = Header(default=None),
) -> User:
    """
    Get the current user with role information.

    This is a wrapper around get_current_user that ensures the user
    has their roles loaded from the provider.

    Args:
        authorization: Authorization header containing Bearer token.

    Returns:
        User: The authenticated user with roles.

    Raises:
        AuthenticationError: If authentication fails.
    """
    user = await get_current_user(authorization)
    return user


def check_can_manage_roles(user: User) -> bool:
    """
    Check if a user can manage roles (assign/remove).

    Role management requires:
    - PLATFORM_ADMIN: Can manage any role
    - ORG_ADMIN: Can manage roles in their organization

    Args:
        user: The user to check.

    Returns:
        bool: True if user can manage roles.
    """
    # Platform admins can manage any role
    if user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        return True

    # Org admins can manage roles in their org
    if user.has_standard_role(StandardRole.ORG_ADMIN):
        return True

    return False


def require_role_management_permission():
    """
    Dependency that requires role management permission.

    Returns a dependency function that checks if the user can manage roles.
    """

    async def dependency(
        authorization: str | None = Header(default=None),
    ) -> User:
        user = await get_current_user(authorization)

        if not check_can_manage_roles(user):
            raise PermissionDeniedError(
                "Role management requires ORG_ADMIN or PLATFORM_ADMIN role"
            )

        return user

    return dependency
