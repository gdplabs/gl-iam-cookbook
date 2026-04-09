"""
RBAC demonstration router for RBAC Showcase.

This module provides endpoints that demonstrate and visualize GL-IAM's
role-based access control features.
"""

from fastapi import APIRouter, Depends

from config import ProviderType, settings
from deps import CurrentUser, require_org_admin, require_org_member, require_platform_admin
from gl_iam.core.roles.mappings import (
    KEYCLOAK_TO_STANDARD,
    STACKAUTH_TO_STANDARD,
    get_provider_roles,
)
from gl_iam.core.roles.standard import (
    ROLE_HIERARCHY,
    StandardRole,
    get_implied_roles,
)
from schemas import (
    AccessTestResponse,
    AccessTestResult,
    EffectivePermissions,
    HierarchyLevel,
    ProtectedAreaResponse,
    ProviderComparisonResponse,
    ProviderRoleMapping,
    RoleHierarchyResponse,
    RoleMappingEntry,
    RoleMappingResponse,
    UserRoleInfoResponse,
)

router = APIRouter(prefix="/rbac", tags=["RBAC Demonstration"])


# =============================================================================
# Role Mapping Visualization
# =============================================================================


@router.get("/mapping-table", response_model=RoleMappingResponse)
async def get_mapping_table(user: CurrentUser) -> RoleMappingResponse:
    """
    Display role mappings for the current provider.

    Shows how provider-specific role names map to GL-IAM standard roles.
    """
    if settings.provider_type == ProviderType.KEYCLOAK:
        mapping_dict = KEYCLOAK_TO_STANDARD
        provider_name = "keycloak"
        description = (
            "Keycloak uses simple role names: 'admin' maps to ORG_ADMIN, "
            "'member' and 'viewer' map to ORG_MEMBER."
        )
    else:
        mapping_dict = STACKAUTH_TO_STANDARD
        provider_name = "stackauth"
        description = (
            "Stack Auth uses prefixed role names: '$admin' and 'admin' map to ORG_ADMIN, "
            "'$member' and 'member' map to ORG_MEMBER."
        )

    mappings = []
    seen_standards = set()

    for provider_role, standard_role in mapping_dict.items():
        implied = get_implied_roles(standard_role) - {standard_role}
        mappings.append(
            RoleMappingEntry(
                provider_role=provider_role,
                standard_role=standard_role.value,
                implied_roles=[r.value for r in implied],
            )
        )
        seen_standards.add(standard_role)

    return RoleMappingResponse(
        provider_type=provider_name,
        mappings=mappings,
        description=description,
    )


# =============================================================================
# Role Hierarchy Visualization
# =============================================================================


@router.get("/hierarchy", response_model=RoleHierarchyResponse)
async def get_hierarchy(user: CurrentUser) -> RoleHierarchyResponse:
    """
    Show the GL-IAM role hierarchy.

    Role Hierarchy: PLATFORM_ADMIN > ORG_ADMIN > ORG_MEMBER

    Higher roles automatically have all permissions of lower roles.
    """
    hierarchy = [
        HierarchyLevel(
            role=StandardRole.PLATFORM_ADMIN.value,
            level=0,
            implies=[r.value for r in get_implied_roles(StandardRole.PLATFORM_ADMIN) if r != StandardRole.PLATFORM_ADMIN],
            description="Super administrator with access to all resources across all organizations",
        ),
        HierarchyLevel(
            role=StandardRole.ORG_ADMIN.value,
            level=1,
            implies=[r.value for r in get_implied_roles(StandardRole.ORG_ADMIN) if r != StandardRole.ORG_ADMIN],
            description="Organization administrator with full management capabilities",
        ),
        HierarchyLevel(
            role=StandardRole.ORG_MEMBER.value,
            level=2,
            implies=[],
            description="Regular organization member with basic access",
        ),
    ]

    return RoleHierarchyResponse(
        hierarchy=hierarchy,
        explanation=(
            "Role hierarchy means higher roles automatically satisfy lower role requirements. "
            "For example, a PLATFORM_ADMIN can access any endpoint that requires ORG_ADMIN or ORG_MEMBER."
        ),
    )


# =============================================================================
# User Role Information
# =============================================================================


@router.get("/my-roles", response_model=UserRoleInfoResponse)
async def get_my_roles(user: CurrentUser) -> UserRoleInfoResponse:
    """
    Get detailed role information for the current user.

    Shows provider roles, standard roles, and effective permissions.
    """
    standard_roles = user.get_standard_roles()
    is_platform_admin = user.metadata.get("is_platform_admin", False)

    # Calculate effective permissions based on standard roles
    has_platform_admin = StandardRole.PLATFORM_ADMIN in standard_roles or is_platform_admin
    has_org_admin = user.has_standard_role(StandardRole.ORG_ADMIN)
    has_org_member = user.has_standard_role(StandardRole.ORG_MEMBER)

    effective_permissions = EffectivePermissions(
        can_access_platform_admin_area=has_platform_admin,
        can_access_admin_area=has_org_admin or has_platform_admin,
        can_access_member_area=has_org_member or has_org_admin or has_platform_admin,
        can_manage_roles=has_org_admin or has_platform_admin,
    )

    return UserRoleInfoResponse(
        user_id=user.id,
        provider_type=settings.provider_type.value,
        provider_roles=user.roles,
        standard_roles=[r.value for r in standard_roles],
        is_platform_admin=is_platform_admin,
        effective_permissions=effective_permissions,
    )


# =============================================================================
# Access Testing
# =============================================================================


@router.get("/test-access", response_model=AccessTestResponse)
async def test_access(user: CurrentUser) -> AccessTestResponse:
    """
    Test the user's access to different role levels.

    Demonstrates how role hierarchy affects access control.
    """
    standard_roles = user.get_standard_roles()
    is_platform_admin = user.metadata.get("is_platform_admin", False)

    # Test each role level
    tests = []

    # Test PLATFORM_ADMIN access
    has_platform = user.has_standard_role(StandardRole.PLATFORM_ADMIN)
    tests.append(
        AccessTestResult(
            role_checked="PLATFORM_ADMIN",
            has_access=has_platform,
            reason="User is a platform administrator" if has_platform else "User is not a platform administrator",
        )
    )

    # Test ORG_ADMIN access
    has_admin = user.has_standard_role(StandardRole.ORG_ADMIN)
    if has_admin:
        if is_platform_admin or StandardRole.PLATFORM_ADMIN in standard_roles:
            reason = "PLATFORM_ADMIN implies ORG_ADMIN"
        elif StandardRole.ORG_ADMIN in standard_roles:
            reason = "User has ORG_ADMIN role directly"
        else:
            reason = "Access granted via role hierarchy"
    else:
        reason = "User does not have ORG_ADMIN or higher role"
    tests.append(
        AccessTestResult(
            role_checked="ORG_ADMIN",
            has_access=has_admin,
            reason=reason,
        )
    )

    # Test ORG_MEMBER access
    has_member = user.has_standard_role(StandardRole.ORG_MEMBER)
    if has_member:
        if is_platform_admin or StandardRole.PLATFORM_ADMIN in standard_roles:
            reason = "PLATFORM_ADMIN implies ORG_MEMBER"
        elif StandardRole.ORG_ADMIN in standard_roles:
            reason = "ORG_ADMIN implies ORG_MEMBER"
        elif StandardRole.ORG_MEMBER in standard_roles:
            reason = "User has ORG_MEMBER role directly"
        else:
            reason = "Access granted via role hierarchy"
    else:
        reason = "User does not have any organization role"
    tests.append(
        AccessTestResult(
            role_checked="ORG_MEMBER",
            has_access=has_member,
            reason=reason,
        )
    )

    return AccessTestResponse(
        user_standard_roles=[r.value for r in standard_roles],
        is_platform_admin=is_platform_admin,
        hierarchy_tests=tests,
    )


# =============================================================================
# Provider Comparison
# =============================================================================


@router.get("/provider-comparison", response_model=ProviderComparisonResponse)
async def get_provider_comparison(user: CurrentUser) -> ProviderComparisonResponse:
    """
    Compare role mappings between Keycloak and StackAuth.

    Demonstrates the SIMI pattern - same code works with different providers.
    """
    from gl_iam.core.roles.mappings import ProviderType as IAMProviderType

    standard_roles = {}

    for std_role in [StandardRole.PLATFORM_ADMIN, StandardRole.ORG_ADMIN, StandardRole.ORG_MEMBER]:
        keycloak_roles = get_provider_roles(std_role, IAMProviderType.KEYCLOAK)
        stackauth_roles = get_provider_roles(std_role, IAMProviderType.STACKAUTH)

        standard_roles[std_role.value] = ProviderRoleMapping(
            keycloak=keycloak_roles,
            stackauth=stackauth_roles,
        )

    return ProviderComparisonResponse(
        standard_roles=standard_roles,
        explanation=(
            "GL-IAM's SIMI (Single Interface Multiple Implementation) pattern allows "
            "your application code to use standard roles like ORG_ADMIN and ORG_MEMBER, "
            "while the library handles the mapping to provider-specific role names. "
            "This means you can switch providers without changing your application logic."
        ),
    )


# =============================================================================
# Protected Areas (Role-Based Access)
# =============================================================================


@router.get("/platform-admin-area", response_model=ProtectedAreaResponse)
async def platform_admin_area(
    user: CurrentUser,
    _: None = Depends(require_platform_admin()),
) -> ProtectedAreaResponse:
    """
    Platform administrator area.

    **Access**: PLATFORM_ADMIN only

    This endpoint is only accessible by platform administrators.
    """
    return ProtectedAreaResponse(
        message=f"Welcome to the Platform Admin area, {user.email}!",
        user_email=user.email,
        access_level="platform_admin",
        required_role="PLATFORM_ADMIN",
    )


@router.get("/admin-area", response_model=ProtectedAreaResponse)
async def admin_area(
    user: CurrentUser,
    _: None = Depends(require_org_admin()),
) -> ProtectedAreaResponse:
    """
    Organization administrator area.

    **Access**: ORG_ADMIN or PLATFORM_ADMIN (via hierarchy)

    This endpoint is accessible by organization admins and above.
    """
    return ProtectedAreaResponse(
        message=f"Welcome to the Admin area, {user.email}!",
        user_email=user.email,
        access_level="org_admin",
        required_role="ORG_ADMIN",
    )


@router.get("/member-area", response_model=ProtectedAreaResponse)
async def member_area(
    user: CurrentUser,
    _: None = Depends(require_org_member()),
) -> ProtectedAreaResponse:
    """
    Organization member area.

    **Access**: ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN (via hierarchy)

    This endpoint is accessible by all organization members.
    """
    return ProtectedAreaResponse(
        message=f"Welcome to the Member area, {user.email}!",
        user_email=user.email,
        access_level="org_member",
        required_role="ORG_MEMBER",
    )
