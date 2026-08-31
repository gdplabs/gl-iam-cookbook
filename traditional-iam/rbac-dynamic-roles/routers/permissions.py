"""
Permission definitions and role grants, scoped to one tenant.

All of these are PLATFORM_ADMIN-only: creating or granting a permission mints
new authority, rather than spending authority a tenant already holds.
"""

from fastapi import APIRouter

from deps import CurrentUser, Gateway, audit_note, unwrap
from schemas import ChangedResponse, GrantRequest, PermissionCreateRequest, PermissionResponse

router = APIRouter(prefix="/orgs/{organization_id}/permissions", tags=["permissions"])


def _to_response(permission) -> PermissionResponse:
    """Map a GL-IAM Permission onto this API's response model."""
    return PermissionResponse(
        name=permission.name,
        description=permission.description,
        organization_id=permission.organization_id,
        is_system=permission.is_system,
    )


@router.get("", response_model=list[PermissionResponse])
async def list_permissions(organization_id: str, user: CurrentUser, gateway: Gateway) -> list[PermissionResponse]:
    """This tenant's permissions, plus the global system ones."""
    permissions = unwrap(await gateway.list_permissions(organization_id))
    return [_to_response(p) for p in permissions]


@router.post("", response_model=PermissionResponse, status_code=201)
async def create_permission(
    organization_id: str, request: PermissionCreateRequest, user: CurrentUser, gateway: Gateway
) -> PermissionResponse:
    """Define a permission string for this tenant.

    The string is yours — GL-IAM stores and matches it but never interprets it.
    """
    permission = unwrap(
        await gateway.create_permission(
            name=request.name,
            organization_id=organization_id,
            caller_id=user.id,
            description=request.description,
        )
    )
    audit_note(user, "create_permission", org=organization_id, permission=request.name)
    return _to_response(permission)


@router.delete("/{permission_name}", response_model=ChangedResponse)
async def delete_permission(
    organization_id: str, permission_name: str, user: CurrentUser, gateway: Gateway
) -> ChangedResponse:
    """Remove a permission and every grant of it, to roles and to users.

    Any `has_permission(...)` check for it starts returning False, so retire the
    code path first.
    """
    deleted = unwrap(await gateway.delete_permission(permission_name, organization_id, user.id))
    audit_note(user, "delete_permission", org=organization_id, permission=permission_name)
    return ChangedResponse(changed=deleted, detail=f"Permission '{permission_name}' deleted")


@router.post("/grant", response_model=ChangedResponse)
async def grant_permission(
    organization_id: str, request: GrantRequest, user: CurrentUser, gateway: Gateway
) -> ChangedResponse:
    """Add ONE permission to a role, leaving its others alone.

    This is the additive counterpart to PATCH /roles/{name}, which replaces the
    role's entire grant set.
    """
    changed = unwrap(
        await gateway.grant_permission_to_role(
            request.role_name, request.permission_name, organization_id, user.id
        )
    )
    audit_note(user, "grant_permission", org=organization_id, role=request.role_name, permission=request.permission_name)
    return ChangedResponse(
        changed=changed,
        detail=f"'{request.permission_name}' {'granted to' if changed else 'already on'} '{request.role_name}'",
    )


@router.post("/revoke", response_model=ChangedResponse)
async def revoke_permission(
    organization_id: str, request: GrantRequest, user: CurrentUser, gateway: Gateway
) -> ChangedResponse:
    """Remove ONE permission from a role. The permission itself survives."""
    changed = unwrap(
        await gateway.revoke_permission_from_role(
            request.role_name, request.permission_name, organization_id, user.id
        )
    )
    audit_note(user, "revoke_permission", org=organization_id, role=request.role_name, permission=request.permission_name)
    return ChangedResponse(
        changed=changed,
        detail=f"'{request.permission_name}' revoked from '{request.role_name}'",
    )
