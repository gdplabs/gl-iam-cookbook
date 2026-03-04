"""
Resource Constraint Validators with GL-IAM.

This example demonstrates how to use resource constraints to control
what resources an agent can access beyond just scopes:
- String equality constraints (e.g., tenant_id must match)
- Set subset constraints (e.g., regions must be a subset)
- Numeric LTE constraints (e.g., budget cannot exceed limit)
- Composite validators combining multiple strategies
- Scope escalation prevention
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import (
    AgentRegistration,
    AgentType,
    DelegationScope,
    IAMGateway,
    TaskContext,
    User,
    composite_validator,
    numeric_lte_validator,
    set_subset_validator,
    string_equality_validator,
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.fastapi import (
    get_current_agent,
    get_current_user,
    get_iam_gateway,
    require_agent_scope,
    require_resource_constraint,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider

load_dotenv()


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Initializes the GL-IAM gateway with a composite resource constraint
    validator that combines string equality, set subset, and numeric
    LTE validators.
    """
    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_auth_hosting=True,
        enable_third_party_provider=False,
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)

    # Composite validator: combines all constraint validation strategies
    validator = composite_validator(
        string_equality_validator,
        set_subset_validator,
        numeric_lte_validator,
    )

    gateway = IAMGateway.from_fullstack_provider(
        provider,
        resource_constraint_validator=validator,
    )
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    yield

    await provider.close()


app = FastAPI(
    title="Scope Constraints API",
    description="GL-IAM Resource Constraint Validators",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response model containing access token."""

    access_token: str
    token_type: str


class DelegateWithConstraintsRequest(BaseModel):
    """Request model for delegation with resource constraints."""

    agent_id: str
    scopes: list[str] = []
    resource_constraints: dict = {}
    expires_in_seconds: int = 3600


class SubDelegateRequest(BaseModel):
    """Request model for sub-delegation."""

    parent_token: str
    agent_id: str
    scopes: list[str] = []
    resource_constraints: dict = {}


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "service": "agent-scope-constraints"}


@app.post("/register")
async def register(request: RegisterRequest):
    """Register a new user."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    user = await gateway.user_store.create_user(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        organization_id=org_id,
    )

    await gateway.user_store.set_user_password(user.id, request.password, org_id)

    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate user and return access token."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=org_id,
    )

    if result.is_ok:
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    else:
        raise HTTPException(status_code=401, detail=result.error.message)


# ============================================================================
# Demo Endpoints
# ============================================================================
@app.post("/setup")
async def setup_agent(user: User = Depends(get_current_user)):
    """Register an agent with broad allowed scopes for constraint demos."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = await gateway.register_agent(
        AgentRegistration(
            name="constrained-agent",
            agent_type=AgentType.WORKER,
            owner_user_id=user.id,
            operator_org_id=org_id,
            allowed_scopes=["docs:read", "docs:write", "analytics:read"],
        )
    )

    if result.is_ok:
        agent = result.value
        return {
            "agent_id": agent.id,
            "name": agent.name,
            "allowed_scopes": agent.allowed_scopes,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/delegate")
async def delegate_with_constraints(
    request: DelegateWithConstraintsRequest,
    user: User = Depends(get_current_user),
):
    """
    Create a delegation token with resource constraints.

    Example constraints:
    - {"tenant_id": "acme"} - string equality
    - {"regions": ["us-east-1", "eu-west-1"]} - set subset
    - {"budget": 100} - numeric LTE
    """
    gateway = get_iam_gateway()

    task = TaskContext(
        id="constraint-task-001",
        purpose="Constrained resource access",
    )

    scope = DelegationScope(
        scopes=request.scopes,
        resource_constraints=request.resource_constraints,
        expires_in_seconds=request.expires_in_seconds,
    )

    result = await gateway.delegate_to_agent(
        principal_token=user.id,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        delegation = result.value
        return {
            "delegation_token": delegation.token,
            "scopes": delegation.scope.scopes,
            "resource_constraints": delegation.scope.resource_constraints,
            "expires_at": delegation.expires_at.isoformat(),
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/delegate/narrow")
async def delegate_narrow(request: SubDelegateRequest):
    """
    Sub-delegate with narrower constraints. This should succeed because
    the child constraints are stricter than the parent.

    Example: parent has budget=100, child requests budget=50 -> OK
    """
    gateway = get_iam_gateway()

    task = TaskContext(
        id="constraint-task-001",
        purpose="Narrower constrained access",
    )

    scope = DelegationScope(
        scopes=request.scopes,
        resource_constraints=request.resource_constraints,
    )

    result = await gateway.delegate_to_agent(
        principal_token=request.parent_token,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        delegation = result.value
        return {
            "status": "success",
            "message": "Narrower constraints accepted",
            "delegation_token": delegation.token,
            "resource_constraints": delegation.scope.resource_constraints,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/delegate/escalate")
async def delegate_escalate(request: SubDelegateRequest):
    """
    Attempt scope escalation. This should fail because the child
    requests scopes not in the parent's delegation.

    Example: parent has ["docs:read"], child requests ["docs:read", "docs:delete"] -> DENIED
    """
    gateway = get_iam_gateway()

    task = TaskContext(
        id="constraint-task-001",
        purpose="Attempted scope escalation",
    )

    scope = DelegationScope(
        scopes=request.scopes,
        resource_constraints=request.resource_constraints,
    )

    result = await gateway.delegate_to_agent(
        principal_token=request.parent_token,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        return {"status": "success", "delegation_token": result.value.token}
    else:
        return {
            "status": "denied",
            "error": result.error.message,
            "error_code": result.error.code,
        }


@app.post("/delegate/constraint-violation")
async def delegate_constraint_violation(request: SubDelegateRequest):
    """
    Attempt constraint violation. This should fail because the child
    constraints are wider than the parent.

    Example: parent has budget=100, child requests budget=200 -> VIOLATION
    """
    gateway = get_iam_gateway()

    task = TaskContext(
        id="constraint-task-001",
        purpose="Attempted constraint violation",
    )

    scope = DelegationScope(
        scopes=request.scopes,
        resource_constraints=request.resource_constraints,
    )

    result = await gateway.delegate_to_agent(
        principal_token=request.parent_token,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        return {"status": "success", "delegation_token": result.value.token}
    else:
        return {
            "status": "denied",
            "error": result.error.message,
            "error_code": result.error.code,
        }


@app.get("/protected")
async def protected_resource(
    agent: AgentIdentity = Depends(get_current_agent),
    _scope: None = Depends(require_agent_scope("docs:read")),
    _constraint: None = Depends(require_resource_constraint("tenant_id", "acme")),
):
    """
    Protected endpoint requiring both agent scope and resource constraint.

    The agent must have:
    - 'docs:read' scope in delegation
    - 'tenant_id' constraint matching 'acme'
    """
    return {
        "agent": agent.name,
        "tenant_id": "acme",
        "documents": [
            {"id": "doc-1", "title": "Acme Project Plan"},
            {"id": "doc-2", "title": "Acme Budget Report"},
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
