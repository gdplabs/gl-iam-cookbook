"""Request and response models for the admin API."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Credentials for the login endpoint."""

    email: str
    password: str
    organization_id: str


class TokenResponse(BaseModel):
    """An issued access token."""

    access_token: str
    token_type: str


class RoleCreateRequest(BaseModel):
    """A new custom role. `permissions` must already exist in the organization."""

    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class RoleUpdateRequest(BaseModel):
    """A role edit.

    `permissions` REPLACES the role's entire grant set — that is the SDK's
    semantics, and this model passes it through unchanged rather than hiding it.
    Leave it `None` to edit only the description. To add a single permission
    without restating the rest, use POST /permissions/{name}/grant instead.
    """

    description: str | None = None
    permissions: list[str] | None = None


class RoleResponse(BaseModel):
    """A role as the API reports it."""

    name: str
    description: str | None
    permissions: list[str]
    organization_id: str | None
    is_system: bool
    is_active: bool


class PermissionCreateRequest(BaseModel):
    """A new custom permission."""

    name: str
    description: str | None = None


class PermissionResponse(BaseModel):
    """A permission as the API reports it."""

    name: str
    description: str | None
    organization_id: str | None
    is_system: bool


class RoleAssignmentRequest(BaseModel):
    """Attach or detach one role on one user."""

    user_id: str
    role: str


class GrantRequest(BaseModel):
    """Grant or revoke one permission on one role."""

    role_name: str
    permission_name: str


class ChangedResponse(BaseModel):
    """Whether the call actually changed anything.

    GL-IAM distinguishes "no change was needed" (`changed=False`, a success)
    from "the call failed" (an error Result, surfaced here as a 4xx). Collapsing
    the two would hide an already-assigned role behind a fake error.
    """

    changed: bool
    detail: str
