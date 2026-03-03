"""
Agent Delegation with GL-IAM (FastAPI + PostgreSQL).

This example demonstrates the core agent delegation system:
- Register AI agents with specific types and allowed scopes
- Delegate authority from users to agents via delegation tokens
- Validate delegation tokens and inspect delegation chains
- Protect endpoints with agent scope requirements
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
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.core.types.delegation import DelegationChain, DelegationToken
from gl_iam.fastapi import (
    get_current_agent,
    get_current_user,
    get_delegation_chain,
    get_delegation_token,
    get_iam_gateway,
    require_agent_scope,
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
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)

    # from_fullstack_provider auto-detects agent_provider from PostgreSQLProvider
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    yield

    await provider.close()


app = FastAPI(
    title="Agent Delegation API",
    description="GL-IAM Agent Delegation with FastAPI",
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


class AgentRegisterRequest(BaseModel):
    """Request model for agent registration."""

    name: str
    agent_type: str = "worker"
    allowed_scopes: list[str] = []


class DelegateRequest(BaseModel):
    """Request model for creating a delegation token."""

    agent_id: str
    task_id: str = "task-001"
    task_purpose: str = "General task"
    scopes: list[str] = []
    max_actions: int | None = None
    expires_in_seconds: int = 3600


class AgentDocumentRequest(BaseModel):
    """Request model for agent document queries."""

    query: str


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "service": "agent-delegation-fastapi"}


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
# User Endpoints (Bearer Token)
# ============================================================================
@app.post("/agents/register")
async def register_agent(
    request: AgentRegisterRequest,
    user: User = Depends(get_current_user),
):
    """Register a new agent. The authenticated user becomes the agent owner."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    agent_type_map = {
        "orchestrator": AgentType.ORCHESTRATOR,
        "worker": AgentType.WORKER,
        "tool": AgentType.TOOL,
        "autonomous": AgentType.AUTONOMOUS,
    }
    agent_type = agent_type_map.get(request.agent_type.lower(), AgentType.WORKER)

    registration = AgentRegistration(
        name=request.name,
        agent_type=agent_type,
        owner_user_id=user.id,
        operator_org_id=org_id,
        allowed_scopes=request.allowed_scopes,
    )

    result = await gateway.register_agent(registration)

    if result.is_ok:
        agent = result.value
        return {
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type.value,
            "owner_user_id": agent.owner_user_id,
            "allowed_scopes": agent.allowed_scopes,
            "status": agent.status.value,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/agents/delegate")
async def delegate_to_agent(
    request: DelegateRequest,
    user: User = Depends(get_current_user),
):
    """Create a delegation token for an agent."""
    gateway = get_iam_gateway()

    # Get the user's access token from the authorization header
    # We need to re-authenticate to get a fresh token for delegation
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # Build task context and scope
    task = TaskContext(
        id=request.task_id,
        purpose=request.task_purpose,
    )

    scope = DelegationScope(
        scopes=request.scopes,
        max_actions=request.max_actions,
        expires_in_seconds=request.expires_in_seconds,
    )

    # Re-authenticate to get a valid token for delegation
    # In production, you'd use the token from the request
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
            "agent_id": delegation.agent_id,
            "task_id": delegation.chain.task_id,
            "scopes": delegation.scope.scopes,
            "expires_at": delegation.expires_at.isoformat(),
            "chain_depth": delegation.chain.depth,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.get("/agents")
async def list_agents(user: User = Depends(get_current_user)):
    """List agents owned by the authenticated user."""
    gateway = get_iam_gateway()

    agents = await gateway.list_agents(owner_user_id=user.id)

    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "agent_type": agent.agent_type.value,
                "status": agent.status.value,
                "allowed_scopes": agent.allowed_scopes,
            }
            for agent in agents
        ]
    }


# ============================================================================
# Agent Endpoints (X-Delegation-Token)
# ============================================================================
@app.get("/agent/me")
async def agent_me(agent: AgentIdentity = Depends(get_current_agent)):
    """Get the current agent's identity from the delegation token."""
    return {
        "id": agent.id,
        "name": agent.name,
        "agent_type": agent.agent_type.value,
        "status": agent.status.value,
        "owner_user_id": agent.owner_user_id,
        "allowed_scopes": agent.allowed_scopes,
    }


@app.get("/agent/documents")
async def agent_documents(
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("docs:read")),
):
    """Agent endpoint requiring 'docs:read' scope."""
    return {
        "agent": agent.name,
        "documents": [
            {"id": "doc-1", "title": "Quarterly Report", "type": "pdf"},
            {"id": "doc-2", "title": "Meeting Notes", "type": "md"},
            {"id": "doc-3", "title": "API Specification", "type": "yaml"},
        ],
    }


@app.get("/agent/task")
async def agent_task(delegation: DelegationToken = Depends(get_delegation_token)):
    """Get task information from the delegation token."""
    return {
        "task_id": delegation.task.id,
        "task_purpose": delegation.task.purpose,
        "scopes": delegation.scope.scopes,
        "agent_id": delegation.agent_id,
        "issued_at": delegation.issued_at.isoformat(),
        "expires_at": delegation.expires_at.isoformat(),
    }


@app.get("/agent/chain")
async def agent_chain(chain: DelegationChain = Depends(get_delegation_chain)):
    """Get delegation chain information."""
    return {
        "depth": chain.depth,
        "task_id": chain.task_id,
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
                "principal_id": link.principal_id,
                "principal_type": link.principal_type.value,
                "delegated_at": link.delegated_at.isoformat(),
                "scopes": link.scope.scopes,
            }
            for link in chain.links
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
