"""
Agent Delegation with Keycloak Provider.

This example demonstrates agent delegation using Keycloak for user
authentication. Users authenticate via Keycloak, then register agents
and create delegation tokens. Agent endpoints are protected with
scope-based access control.

Key difference from PostgreSQL: Keycloak handles user auth externally,
while agent operations use a PostgreSQL-backed agent provider that is
automatically detected by from_fullstack_provider().
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
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.core.types.delegation import DelegationChain
from gl_iam.fastapi import (
    get_current_agent,
    get_current_user,
    get_delegation_chain,
    get_iam_gateway,
    require_agent_scope,
    set_iam_gateway,
)
from gl_iam.providers.keycloak import KeycloakConfig, KeycloakProvider

load_dotenv()


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Initializes the GL-IAM gateway with Keycloak provider.
    The KeycloakProvider includes agent support via PostgreSQL-backed
    agent tables when DATABASE_URL is configured.
    """
    config = KeycloakConfig(
        server_url=os.getenv("KEYCLOAK_SERVER_URL"),
        realm=os.getenv("KEYCLOAK_REALM"),
        client_id=os.getenv("KEYCLOAK_CLIENT_ID"),
        client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET"),
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        auto_create_tables=True,
    )
    provider = KeycloakProvider(config=config)

    # from_fullstack_provider auto-detects agent support
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway, default_organization_id=os.getenv("KEYCLOAK_REALM"))

    is_healthy = await provider.health_check()
    if is_healthy:
        print(f"Connected to Keycloak at {os.getenv('KEYCLOAK_SERVER_URL')}")

    yield


app = FastAPI(
    title="Agent Delegation with Keycloak",
    description="GL-IAM Agent Delegation using Keycloak authentication",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================
class UserResponse(BaseModel):
    """Response model for user data with roles."""

    id: str
    email: str
    display_name: str | None
    roles: list[str]


class AgentRegisterRequest(BaseModel):
    """Request model for agent registration."""

    name: str
    agent_type: str = "worker"
    allowed_scopes: list[str] = []


class DelegateRequest(BaseModel):
    """Request model for delegation."""

    agent_id: str
    scopes: list[str] = []
    task_purpose: str = "Keycloak agent task"
    expires_in_seconds: int = 3600


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "provider": "keycloak", "service": "agent-keycloak"}


# ============================================================================
# User Endpoints (Keycloak Bearer Token)
# ============================================================================
@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile from Keycloak token."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
    )


@app.post("/agents/register")
async def register_agent(
    request: AgentRegisterRequest,
    user: User = Depends(get_current_user),
):
    """Register a new agent. The Keycloak user becomes the owner."""
    gateway = get_iam_gateway()
    realm = os.getenv("KEYCLOAK_REALM", "default")

    agent_type_map = {
        "orchestrator": AgentType.ORCHESTRATOR,
        "worker": AgentType.WORKER,
        "tool": AgentType.TOOL,
        "autonomous": AgentType.AUTONOMOUS,
    }
    agent_type = agent_type_map.get(request.agent_type.lower(), AgentType.WORKER)

    result = await gateway.register_agent(
        AgentRegistration(
            name=request.name,
            agent_type=agent_type,
            owner_user_id=user.id,
            operator_org_id=realm,
            allowed_scopes=request.allowed_scopes,
        )
    )

    if result.is_ok:
        agent = result.value
        return {
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type.value,
            "owner": user.email,
            "allowed_scopes": agent.allowed_scopes,
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

    task = TaskContext(
        id="keycloak-task-001",
        purpose=request.task_purpose,
    )

    scope = DelegationScope(
        scopes=request.scopes,
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
            "agent_id": delegation.agent_id,
            "scopes": delegation.scope.scopes,
            "expires_at": delegation.expires_at.isoformat(),
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.get("/agents")
async def list_agents(user: User = Depends(get_current_user)):
    """List agents owned by the authenticated Keycloak user."""
    gateway = get_iam_gateway()

    agents = await gateway.list_agents(owner_user_id=user.id)

    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "agent_type": agent.agent_type.value,
                "status": agent.status.value,
            }
            for agent in agents
        ]
    }


# ============================================================================
# Agent Endpoints (X-Delegation-Token)
# ============================================================================
@app.get("/agent/me")
async def agent_me(agent: AgentIdentity = Depends(get_current_agent)):
    """Get the current agent's identity."""
    return {
        "id": agent.id,
        "name": agent.name,
        "agent_type": agent.agent_type.value,
        "owner_user_id": agent.owner_user_id,
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
            {"id": "doc-1", "title": "Keycloak Integration Guide"},
            {"id": "doc-2", "title": "SSO Configuration"},
        ],
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
        "effective_scopes": list(chain.effective_scopes()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
