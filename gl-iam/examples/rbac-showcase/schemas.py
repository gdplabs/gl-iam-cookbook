"""
Pydantic response models for RBAC Showcase.

These models define the request/response schemas for the RBAC
demonstration endpoints.
"""

from pydantic import BaseModel, Field


# =============================================================================
# User Response Models
# =============================================================================


class UserResponse(BaseModel):
    """Basic user information response."""

    id: str
    email: str | None
    display_name: str | None
    roles: list[str]


# =============================================================================
# Role Mapping Models
# =============================================================================


class RoleMappingEntry(BaseModel):
    """A single role mapping entry."""

    provider_role: str = Field(description="Role name in the provider")
    standard_role: str = Field(description="GL-IAM standard role (e.g., ORG_ADMIN)")
    implied_roles: list[str] = Field(
        default_factory=list,
        description="Roles implied by this standard role",
    )


class RoleMappingResponse(BaseModel):
    """Response showing role mappings for the current provider."""

    provider_type: str = Field(description="Current provider type")
    mappings: list[RoleMappingEntry] = Field(description="List of role mappings")
    description: str = Field(description="Explanation of the mapping")


# =============================================================================
# Role Hierarchy Models
# =============================================================================


class HierarchyLevel(BaseModel):
    """A level in the role hierarchy."""

    role: str = Field(description="Standard role name")
    level: int = Field(description="Hierarchy level (0 = highest)")
    implies: list[str] = Field(description="Roles implied by this role")
    description: str = Field(description="Role description")


class RoleHierarchyResponse(BaseModel):
    """Response showing the role hierarchy."""

    hierarchy: list[HierarchyLevel] = Field(description="Role hierarchy from top to bottom")
    explanation: str = Field(description="How role hierarchy works")


# =============================================================================
# User Role Information Models
# =============================================================================


class EffectivePermissions(BaseModel):
    """Effective permissions based on user's roles."""

    can_access_platform_admin_area: bool = Field(description="Can access platform admin endpoints")
    can_access_admin_area: bool = Field(description="Can access org admin endpoints")
    can_access_member_area: bool = Field(description="Can access member endpoints")
    can_manage_roles: bool = Field(description="Can assign/remove roles")


class UserRoleInfoResponse(BaseModel):
    """Detailed user role information."""

    user_id: str = Field(description="User's unique identifier")
    provider_type: str = Field(description="Current authentication provider")
    provider_roles: list[str] = Field(description="Roles from the provider")
    standard_roles: list[str] = Field(description="GL-IAM standard roles")
    is_platform_admin: bool = Field(description="Whether user is a platform admin")
    effective_permissions: EffectivePermissions = Field(
        description="Effective permissions based on roles"
    )


# =============================================================================
# Access Test Models
# =============================================================================


class AccessTestResult(BaseModel):
    """Result of testing access to a role level."""

    role_checked: str = Field(description="Standard role that was checked")
    has_access: bool = Field(description="Whether user has access")
    reason: str = Field(description="Explanation of why access was granted/denied")


class AccessTestResponse(BaseModel):
    """Response from testing access to different role levels."""

    user_standard_roles: list[str] = Field(description="User's standard roles")
    is_platform_admin: bool = Field(description="Whether user is platform admin")
    hierarchy_tests: list[AccessTestResult] = Field(
        description="Results of testing access to each role level"
    )


# =============================================================================
# Provider Comparison Models
# =============================================================================


class ProviderRoleMapping(BaseModel):
    """Role mappings for a specific provider."""

    keycloak: list[str] = Field(description="Keycloak roles that map to this standard role")
    stackauth: list[str] = Field(description="Stack Auth roles that map to this standard role")


class ProviderComparisonResponse(BaseModel):
    """Comparison of role mappings between providers."""

    standard_roles: dict[str, ProviderRoleMapping] = Field(
        description="Standard roles and their provider mappings"
    )
    explanation: str = Field(description="How SIMI pattern enables provider-agnostic code")


# =============================================================================
# Protected Area Response Models
# =============================================================================


class ProtectedAreaResponse(BaseModel):
    """Response from accessing a protected area."""

    message: str
    user_email: str | None
    access_level: str
    required_role: str


# =============================================================================
# Role Management Models
# =============================================================================


class RoleAssignRequest(BaseModel):
    """Request to assign a role to a user."""

    user_id: str = Field(description="User ID to assign the role to")
    role: str = Field(description="Role name to assign (provider-specific)")


class RoleRemoveRequest(BaseModel):
    """Request to remove a role from a user."""

    user_id: str = Field(description="User ID to remove the role from")
    role: str = Field(description="Role name to remove (provider-specific)")


class RoleManagementResponse(BaseModel):
    """Response from role management operations."""

    success: bool
    message: str
    user_id: str
    role: str
    action: str  # "assign" or "remove"


# =============================================================================
# Auth Token Models
# =============================================================================


class TokenRequest(BaseModel):
    """Request for authentication token (Keycloak password grant)."""

    username: str = Field(description="User's email/username")
    password: str = Field(description="User's password")


class TokenResponse(BaseModel):
    """Response containing authentication token."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int | None = None
