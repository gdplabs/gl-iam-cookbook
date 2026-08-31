"""
Role definitions and assignments, scoped to one tenant.

Every route passes `caller_id=user.id` to the gateway. GL-IAM does the
authorization itself — a PLATFORM_ADMIN may define roles, an ORG_ADMIN may only
assign existing ones inside their own organization, and neither is trusted on
the client's say-so. There is deliberately no "skip the check" path here.
"""

from fastapi import APIRouter, Query

from deps import CurrentUser, Gateway, audit_note, unwrap
from schemas import ChangedResponse, RoleAssignmentRequest, RoleCreateRequest, RoleResponse, RoleUpdateRequest

router = APIRouter(prefix="/orgs/{organization_id}/roles", tags=["roles"])


def _to_response(role) -> RoleResponse:
    """Map a GL-IAM Role onto this API's response model."""
    return RoleResponse(
        name=role.name,
        description=role.description,
        permissions=sorted(role.permissions),
        organization_id=role.organization_id,
        is_system=role.is_system,
        is_active=role.is_active,
    )


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    organization_id: str,
    user: CurrentUser,
    gateway: Gateway,
    include_inactive: bool = Query(False, description="Also return deactivated custom roles"),
) -> list[RoleResponse]:
    """List the roles this tenant can see: its own, plus the global system roles.

    System roles appear with `organization_id=None` — they are one shared row
    each, not a per-tenant copy.
    """
    roles = unwrap(await gateway.list_roles(organization_id, include_inactive=include_inactive))
    return [_to_response(role) for role in roles]


@router.get("/{role_name}", response_model=RoleResponse)
async def get_role(organization_id: str, role_name: str, user: CurrentUser, gateway: Gateway) -> RoleResponse:
    """Fetch one role. A role owned by another tenant is a 404, not a peek."""
    return _to_response(unwrap(await gateway.get_role(role_name, organization_id)))


@router.post("", response_model=RoleResponse, status_code=201)
async def create_role(
    organization_id: str, request: RoleCreateRequest, user: CurrentUser, gateway: Gateway
) -> RoleResponse:
    """Define a custom role for this tenant. PLATFORM_ADMIN only.

    Every name in `permissions` must already exist in this organization (or be
    a global system permission) — create them first via POST /permissions.
    """
    role = unwrap(
        await gateway.create_role(
            name=request.name,
            organization_id=organization_id,
            caller_id=user.id,
            description=request.description,
            permissions=request.permissions or None,
        )
    )
    audit_note(user, "create_role", org=organization_id, role=request.name)
    return _to_response(role)


@router.patch("/{role_name}", response_model=RoleResponse)
async def update_role(
    organization_id: str, role_name: str, request: RoleUpdateRequest, user: CurrentUser, gateway: Gateway
) -> RoleResponse:
    """Edit a custom role. PLATFORM_ADMIN only.

    Passing `permissions` REPLACES the role's whole grant set. Omit it to touch
    only the description.
    """
    role = unwrap(
        await gateway.update_role(
            role_name=role_name,
            organization_id=organization_id,
            caller_id=user.id,
            description=request.description,
            permissions=request.permissions,
        )
    )
    audit_note(user, "update_role", org=organization_id, role=role_name)
    return _to_response(role)


@router.post("/{role_name}/deactivate", response_model=RoleResponse)
async def deactivate_role(organization_id: str, role_name: str, user: CurrentUser, gateway: Gateway) -> RoleResponse:
    """Retire a role reversibly: it stops granting, assignments are kept.

    Prefer this to DELETE when the role might come back — reactivating restores
    every assignment and grant exactly as they were.
    """
    role = unwrap(await gateway.deactivate_role(role_name, organization_id, user.id))
    audit_note(user, "deactivate_role", org=organization_id, role=role_name)
    return _to_response(role)


@router.post("/{role_name}/activate", response_model=RoleResponse)
async def activate_role(organization_id: str, role_name: str, user: CurrentUser, gateway: Gateway) -> RoleResponse:
    """Bring a deactivated role back, grants and assignments intact."""
    role = unwrap(await gateway.activate_role(role_name, organization_id, user.id))
    audit_note(user, "activate_role", org=organization_id, role=role_name)
    return _to_response(role)


@router.delete("/{role_name}", response_model=ChangedResponse)
async def delete_role(organization_id: str, role_name: str, user: CurrentUser, gateway: Gateway) -> ChangedResponse:
    """Permanently remove a role, its assignments, and its grants. No undo."""
    deleted = unwrap(await gateway.delete_role(role_name, organization_id, user.id))
    audit_note(user, "delete_role", org=organization_id, role=role_name)
    return ChangedResponse(changed=deleted, detail=f"Role '{role_name}' deleted")


@router.post("/assign", response_model=ChangedResponse)
async def assign_role(
    organization_id: str, request: RoleAssignmentRequest, user: CurrentUser, gateway: Gateway
) -> ChangedResponse:
    """Attach a role to a user. ORG_ADMIN may do this inside their own tenant.

    Granting a *standard* role (org_member / org_admin / platform_admin) still
    requires PLATFORM_ADMIN, so an org admin cannot promote themselves.

    `changed=False` means the user already had the role — a success, not a
    failure.
    """
    changed = unwrap(await gateway.assign_role(request.user_id, request.role, organization_id, user.id))
    audit_note(user, "assign_role", org=organization_id, role=request.role, target=request.user_id)
    return ChangedResponse(
        changed=changed,
        detail=f"Role '{request.role}' {'assigned' if changed else 'was already assigned'}",
    )


@router.post("/remove", response_model=ChangedResponse)
async def remove_role(
    organization_id: str, request: RoleAssignmentRequest, user: CurrentUser, gateway: Gateway
) -> ChangedResponse:
    """Detach a role from one user. The role itself is untouched."""
    changed = unwrap(await gateway.remove_role(request.user_id, request.role, organization_id, user.id))
    audit_note(user, "remove_role", org=organization_id, role=request.role, target=request.user_id)
    return ChangedResponse(changed=changed, detail=f"Role '{request.role}' removed")
