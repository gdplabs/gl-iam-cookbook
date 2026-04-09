"""
Multi-Hop Delegation Chains with GL-IAM.

This example demonstrates how delegation authority flows through chains:
- User delegates to an orchestrator agent (broad scopes)
- Orchestrator sub-delegates to a worker agent (narrower scopes)
- Each hop narrows the effective scopes
- Chain inspection reveals the full authority path
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from gl_iam import (
    AgentRegistration,
    AgentType,
    DelegationScope,
    IAMGateway,
    TaskContext,
    User,
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user,
    get_iam_gateway,
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

    Initializes the GL-IAM gateway with PostgreSQL provider on startup
    and cleans up resources on shutdown.
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
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    yield

    await provider.close()


app = FastAPI(
    title="Delegation Chain API",
    description="GL-IAM Multi-Hop Delegation Chains",
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


class SetupResponse(BaseModel):
    """Response model for the chain setup."""

    orchestrator_id: str
    worker_id: str
    message: str


class DelegateResponse(BaseModel):
    """Response model for delegation."""

    token: str
    chain_depth: int
    effective_scopes: list[str]


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "service": "agent-delegation-chain"}


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
# Chain Demo Endpoints
# ============================================================================
@app.post("/setup", response_model=SetupResponse)
async def setup_chain(user: User = Depends(get_current_user)):
    """
    Register an orchestrator and a worker agent for chain demo.

    The orchestrator gets broad scopes, the worker gets narrow scopes.
    """
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # Register orchestrator with broad scopes
    orchestrator_result = await gateway.register_agent(
        AgentRegistration(
            name="orchestrator-agent",
            agent_type=AgentType.ORCHESTRATOR,
            owner_user_id=user.id,
            operator_org_id=org_id,
            allowed_scopes=["docs:read", "docs:write", "docs:delete", "analytics:read"],
            max_delegation_depth=5,
        )
    )

    if not orchestrator_result.is_ok:
        raise HTTPException(status_code=400, detail=orchestrator_result.error.message)

    # Register worker with narrow scopes
    worker_result = await gateway.register_agent(
        AgentRegistration(
            name="worker-agent",
            agent_type=AgentType.WORKER,
            owner_user_id=user.id,
            operator_org_id=org_id,
            allowed_scopes=["docs:read", "analytics:read"],
            max_delegation_depth=3,
        )
    )

    if not worker_result.is_ok:
        raise HTTPException(status_code=400, detail=worker_result.error.message)

    return SetupResponse(
        orchestrator_id=orchestrator_result.value.id,
        worker_id=worker_result.value.id,
        message="Orchestrator and worker agents registered successfully",
    )


@app.post("/delegate/orchestrator", response_model=DelegateResponse)
async def delegate_to_orchestrator(
    orchestrator_id: str,
    user: User = Depends(get_current_user),
    authorization: str = Header(),
):
    """
    User delegates broad authority to the orchestrator.

    This is the first hop in the chain: User -> Orchestrator.
    """
    gateway = get_iam_gateway()

    # Extract the raw JWT from the Authorization header
    token = authorization.split(" ", 1)[1] if " " in authorization else authorization

    task = TaskContext(
        id="chain-task-001",
        purpose="Process quarterly reports and generate analytics",
    )

    # Broad scopes and high budget for the orchestrator
    scope = DelegationScope(
        scopes=["docs:read", "docs:write", "analytics:read"],
        max_actions=100,
        expires_in_seconds=7200,
    )

    result = await gateway.delegate_to_agent(
        principal_token=token,
        agent_id=orchestrator_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        delegation = result.value
        return DelegateResponse(
            token=delegation.token,
            chain_depth=delegation.chain.depth,
            effective_scopes=list(delegation.chain.effective_scopes()),
        )
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/delegate/worker", response_model=DelegateResponse)
async def delegate_to_worker(
    worker_id: str,
    orchestrator_token: str,
):
    """
    Orchestrator sub-delegates narrower authority to the worker.

    This is the second hop: User -> Orchestrator -> Worker.
    The worker receives only a subset of the orchestrator's scopes.
    """
    gateway = get_iam_gateway()

    task = TaskContext(
        id="chain-task-001",
        purpose="Read specific documents for analysis",
    )

    # Narrower scopes and lower budget for the worker
    scope = DelegationScope(
        scopes=["docs:read"],
        max_actions=10,
        expires_in_seconds=1800,
    )

    # The orchestrator's delegation token is used as the principal_token
    result = await gateway.delegate_to_agent(
        principal_token=orchestrator_token,
        agent_id=worker_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        delegation = result.value
        return DelegateResponse(
            token=delegation.token,
            chain_depth=delegation.chain.depth,
            effective_scopes=list(delegation.chain.effective_scopes()),
        )
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.get("/chain/inspect")
async def inspect_chain(token: str = Query(..., description="Delegation token to inspect")):
    """
    Validate a delegation token and inspect its full chain.

    Shows the authority path, scope narrowing at each hop,
    and the effective scopes after intersection.
    """
    gateway = get_iam_gateway()

    result = await gateway.validate_delegation_token(token)

    if not result.is_ok:
        raise HTTPException(status_code=401, detail=result.error.message)

    delegation = result.value
    chain = delegation.chain

    return {
        "valid": True,
        "agent_id": delegation.agent_id,
        "depth": chain.depth,
        "root_principal": {
            "id": chain.root_principal.principal_id,
            "type": chain.root_principal.principal_type.value,
        },
        "leaf_principal": {
            "id": chain.leaf_principal.principal_id,
            "type": chain.leaf_principal.principal_type.value,
        },
        "effective_scopes": list(chain.effective_scopes()),
        "links": [
            {
                "hop": i + 1,
                "principal_id": link.principal_id,
                "principal_type": link.principal_type.value,
                "scopes_at_hop": link.scope.scopes,
                "max_actions": link.scope.max_actions,
                "delegated_at": link.delegated_at.isoformat(),
            }
            for i, link in enumerate(chain.links)
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
