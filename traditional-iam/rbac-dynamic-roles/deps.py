"""
FastAPI dependencies for the multi-tenant admin API.

Two things live here that a real multi-tenant app also needs.

**`get_tenant_user`** separates two organizations that are easy to conflate:

* the **session** organization — where the caller authenticated, carried in the
  token's `org_id` claim. GL-IAM refuses to validate a token against any other
  organization, deliberately, so cross-tenant session reuse is impossible.
* the **target** organization — the tenant in the URL, the one being
  administered. A PLATFORM_ADMIN authenticates in their home organization and
  then acts on any tenant; the two are not the same value for them.

So the session is validated against the token's own organization, and access to
the *target* tenant is a separate decision.

**`unwrap`** preserves a failed GL-IAM `Result` as a typed SDK exception.
The registered v1.2 handler selects the canonical status, message and recovery
guidance; routes do not maintain their own status table.
"""

from typing import Annotated, Any, TypeVar

import jwt
from fastapi import Depends, Header, HTTPException, Path
from gl_iam import IAMGateway, User
from gl_iam.core.error_carrier import raise_for_error
from gl_iam.core.roles.standard import StandardRole
from gl_iam.core.types.result import Result
from gl_iam.fastapi import get_iam_gateway

T = TypeVar("T")

def unwrap(result: Result[T]) -> T:
    """Return the value or preserve the SDK error for the v1.2 HTTP handler."""
    if result.is_err:
        raise_for_error(result.error)
    return result.value


def gateway() -> IAMGateway:
    """The process-wide gateway, wired in main.py's lifespan."""
    return get_iam_gateway()


def _session_organization(token: str) -> str:
    """Read the `org_id` claim without verifying, to choose the validation scope.

    Safe, despite the word "unverified": the claim only selects *which*
    organization the token is then fully validated against, and
    `validate_session` rejects the token outright unless the signature checks
    out **and** the claim matches the scope it was handed. A forged `org_id`
    therefore buys nothing — it just picks the scope its own signature check
    will fail in.

    Args:
        token: The bearer token.

    Returns:
        The organization the session belongs to.

    Raises:
        HTTPException: 401 if the token is unreadable or carries no `org_id`.
    """
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as error:
        raise HTTPException(status_code=401, detail="Malformed token") from error

    session_org = claims.get("org_id")
    if not session_org:
        raise HTTPException(status_code=401, detail="Token carries no organization scope")
    return session_org


async def get_tenant_user(
    organization_id: Annotated[str, Path(description="Tenant being administered")],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Authenticate the caller, then authorize them for the tenant in the path.

    Two steps, deliberately separate:

    1. **Authenticate** against the token's own organization. GL-IAM will not
       validate a session outside its `org_id`, so this is the only scope that
       can succeed.
    2. **Authorize** for the target tenant. A PLATFORM_ADMIN spans every
       organization; anyone else must belong to the one they are addressing.

    Step 2 is the application's job, not the SDK's, and that is worth being
    explicit about: GL-IAM's *write* operations (`create_role`, `assign_role`,
    ...) take a `caller_id` and enforce authority themselves, but its *read*
    operations (`list_roles`, `get_role`, `list_permissions`) take no caller and
    enforce nothing. Without the check below, an ORG_ADMIN of one tenant could
    list another tenant's roles. GL-IAM provides the mechanism; the policy for
    who may look is yours.

    Args:
        organization_id: Target tenant, from the URL path.
        authorization: `Bearer <token>` header.

    Returns:
        The authenticated user, resolved in their own organization.

    Raises:
        HTTPException: 401 if the session is missing or invalid, 403 if the
            caller has no business in the target tenant.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")

    token = authorization.split(" ", 1)[1].strip()
    session_org = _session_organization(token)

    result = await gateway().validate_session(token, organization_id=session_org)
    if result.is_err:
        raise_for_error(result.error)

    user = result.unwrap()
    if session_org != organization_id and not user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "cross_tenant_denied",
                "message": f"{user.email} is not a member of '{organization_id}'",
            },
        )
    return user


CurrentUser = Annotated[User, Depends(get_tenant_user)]
Gateway = Annotated[IAMGateway, Depends(gateway)]


def audit_note(user: User, action: str, **fields: Any) -> None:
    """Print what the caller just did, so the demo's console shows the actor.

    GL-IAM emits a real audit event for every one of these operations; this is
    only the example's own narration. See the Audit Trail guides for wiring the
    genuine trail to a database, a SIEM, or OpenTelemetry.
    """
    extra = " ".join(f"{k}={v}" for k, v in fields.items())
    print(f"[audit] caller={user.email} action={action} {extra}".rstrip())
