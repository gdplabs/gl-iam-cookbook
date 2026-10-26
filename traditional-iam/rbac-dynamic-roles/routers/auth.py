"""Login and whoami — the minimum needed to get a token per tenant."""

from fastapi import APIRouter
from gl_iam.core.error_carrier import raise_for_error
from gl_iam.core.types import PasswordCredentials

from deps import CurrentUser, Gateway
from schemas import LoginRequest, TokenResponse

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, gateway: Gateway) -> TokenResponse:
    """Authenticate within one organization and receive an access token.

    The token is scoped to `organization_id`: presenting it against another
    tenant's routes fails validation. That is the boundary the rest of this
    example relies on.
    """
    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=request.organization_id,
    )
    if result.is_err:
        # A deactivated account reports ACCOUNT_DISABLED, distinct from a wrong
        # password — worth surfacing separately so the client can say why.
        raise_for_error(result.error)

    return TokenResponse(access_token=result.token.access_token, token_type=result.token.token_type)


@router.get("/orgs/{organization_id}/me")
async def whoami(organization_id: str, user: CurrentUser, gateway: Gateway) -> dict:
    """Report the caller's effective authority inside this tenant.

    `user.roles` is *effective*: a role whose definition has been deactivated
    is absent here even though the assignment still exists. `assigned_roles`
    below shows the raw assignments, so the difference is visible side by side.
    """
    assigned = await gateway.get_user_roles(user.id, organization_id)
    if assigned.is_err:
        raise_for_error(assigned.error)
    permissions = await gateway.get_user_permissions(user.id, organization_id)
    if permissions.is_err:
        raise_for_error(permissions.error)

    return {
        "id": user.id,
        "email": user.email,
        "organization_id": organization_id,
        "effective_roles": user.roles,
        "assigned_roles": assigned.value,
        "permissions": sorted(permissions.value),
    }
