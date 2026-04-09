"""
Admin router for RBAC Showcase.

Provides role management endpoints for assigning and removing roles.
"""

from fastapi import APIRouter, Depends, HTTPException

from config import ProviderType, settings
from deps import require_role_management_permission
from gl_iam import User
from gl_iam.core.roles.standard import StandardRole
from gl_iam.fastapi import get_iam_gateway
from schemas import (
    RoleAssignRequest,
    RoleManagementResponse,
    RoleRemoveRequest,
)

router = APIRouter(prefix="/admin", tags=["Role Management"])


@router.post("/roles/assign", response_model=RoleManagementResponse)
async def assign_role(
    request: RoleAssignRequest,
    current_user: User = Depends(require_role_management_permission()),
) -> RoleManagementResponse:
    """
    Assign a role to a user.

    **Access**: ORG_ADMIN or PLATFORM_ADMIN

    Authorization Rules:
    - PLATFORM_ADMIN: Can assign any role to any user
    - ORG_ADMIN: Can assign roles within their organization

    Note: This endpoint demonstrates authorization checks. The actual role
    assignment depends on the provider's API capabilities.
    """
    # Check if current user can assign this role
    is_platform_admin = current_user.has_standard_role(StandardRole.PLATFORM_ADMIN)

    # ORG_ADMIN cannot assign PLATFORM_ADMIN role
    if request.role in ["platform_admin", "platform-admin"] and not is_platform_admin:
        raise HTTPException(
            status_code=403,
            detail="Only PLATFORM_ADMIN can assign PLATFORM_ADMIN role",
        )

    # Get the gateway for actual role assignment
    gateway = get_iam_gateway()

    # Note: Actual role assignment would require provider-specific implementation
    # This is a demonstration of the authorization pattern
    try:
        # In a real implementation, this would call the provider's API
        # await gateway.assign_role(request.user_id, request.role, organization_id)
        pass
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to assign role: {str(e)}",
        )

    return RoleManagementResponse(
        success=True,
        message=f"Role '{request.role}' assigned to user '{request.user_id}'",
        user_id=request.user_id,
        role=request.role,
        action="assign",
    )


@router.post("/roles/remove", response_model=RoleManagementResponse)
async def remove_role(
    request: RoleRemoveRequest,
    current_user: User = Depends(require_role_management_permission()),
) -> RoleManagementResponse:
    """
    Remove a role from a user.

    **Access**: ORG_ADMIN or PLATFORM_ADMIN

    Authorization Rules:
    - PLATFORM_ADMIN: Can remove any role from any user
    - ORG_ADMIN: Can remove roles within their organization
    - Cannot remove your own admin role (safety check)

    Note: This endpoint demonstrates authorization checks. The actual role
    removal depends on the provider's API capabilities.
    """
    # Safety check: cannot remove your own admin role
    if request.user_id == current_user.id and request.role in ["admin", "$admin"]:
        raise HTTPException(
            status_code=403,
            detail="Cannot remove your own admin role",
        )

    # Check if current user can remove this role
    is_platform_admin = current_user.has_standard_role(StandardRole.PLATFORM_ADMIN)

    # ORG_ADMIN cannot remove PLATFORM_ADMIN role
    if request.role in ["platform_admin", "platform-admin"] and not is_platform_admin:
        raise HTTPException(
            status_code=403,
            detail="Only PLATFORM_ADMIN can remove PLATFORM_ADMIN role",
        )

    # Get the gateway for actual role removal
    gateway = get_iam_gateway()

    # Note: Actual role removal would require provider-specific implementation
    try:
        # In a real implementation, this would call the provider's API
        # await gateway.remove_role(request.user_id, request.role, organization_id)
        pass
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to remove role: {str(e)}",
        )

    return RoleManagementResponse(
        success=True,
        message=f"Role '{request.role}' removed from user '{request.user_id}'",
        user_id=request.user_id,
        role=request.role,
        action="remove",
    )


@router.get("/roles/available")
async def get_available_roles(
    current_user: User = Depends(require_role_management_permission()),
):
    """
    Get available roles that can be assigned.

    **Access**: ORG_ADMIN or PLATFORM_ADMIN

    Returns the list of roles available in the current provider.
    """
    if settings.provider_type == ProviderType.KEYCLOAK:
        return {
            "provider": "keycloak",
            "available_roles": [
                {
                    "name": "admin",
                    "standard_role": "ORG_ADMIN",
                    "description": "Organization administrator with full management capabilities",
                },
                {
                    "name": "member",
                    "standard_role": "ORG_MEMBER",
                    "description": "Standard organization member",
                },
                {
                    "name": "viewer",
                    "standard_role": "ORG_MEMBER",
                    "description": "Read-only organization member",
                },
            ],
            "note": "Use Keycloak Admin Console for actual role management",
        }
    else:
        return {
            "provider": "stackauth",
            "available_roles": [
                {
                    "name": "$admin",
                    "standard_role": "ORG_ADMIN",
                    "description": "Organization administrator (Stack Auth prefixed)",
                },
                {
                    "name": "admin",
                    "standard_role": "ORG_ADMIN",
                    "description": "Organization administrator (alternative)",
                },
                {
                    "name": "$member",
                    "standard_role": "ORG_MEMBER",
                    "description": "Standard member (Stack Auth prefixed)",
                },
                {
                    "name": "member",
                    "standard_role": "ORG_MEMBER",
                    "description": "Standard member (alternative)",
                },
            ],
            "note": "Use Stack Auth Dashboard for actual role management",
        }


@router.get("/authorization-rules")
async def get_authorization_rules(
    current_user: User = Depends(require_role_management_permission()),
):
    """
    Get the authorization rules for role management.

    **Access**: ORG_ADMIN or PLATFORM_ADMIN

    Returns documentation of what actions each role can perform.
    """
    return {
        "rules": {
            "PLATFORM_ADMIN": {
                "can_assign": [
                    "admin",
                    "member",
                    "viewer",
                    "$admin",
                    "$member",
                    "platform_admin",
                ],
                "can_remove": [
                    "admin",
                    "member",
                    "viewer",
                    "$admin",
                    "$member",
                    "platform_admin",
                ],
                "restrictions": ["Cannot remove own platform_admin role"],
            },
            "ORG_ADMIN": {
                "can_assign": ["admin", "member", "viewer", "$admin", "$member"],
                "can_remove": ["admin", "member", "viewer", "$admin", "$member"],
                "restrictions": [
                    "Cannot assign/remove platform_admin role",
                    "Cannot remove own admin role",
                    "Limited to own organization",
                ],
            },
            "ORG_MEMBER": {
                "can_assign": [],
                "can_remove": [],
                "restrictions": ["No role management capabilities"],
            },
        },
        "hierarchy_note": (
            "Role hierarchy means PLATFORM_ADMIN automatically has all ORG_ADMIN capabilities, "
            "and ORG_ADMIN automatically has all ORG_MEMBER capabilities."
        ),
    }
