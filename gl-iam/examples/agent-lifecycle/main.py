"""
Agent Lifecycle Management with GL-IAM.

This example demonstrates the full agent lifecycle:
- Register agents
- Suspend agents (temporarily disable)
- Reactivate agents (provider-level operation)
- Revoke agents (permanently disable)
- Audit event capture for all lifecycle operations
- List agents with filtering
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel

from gl_iam import (
    AgentRegistration,
    AgentType,
    AuditEvent,
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
# Audit Log
# ============================================================================
audit_log: list[dict] = []


def audit_callback(event: AuditEvent):
    """Capture audit events into an in-memory log."""
    audit_log.append(
        {
            "event_type": event.event_type.value,
            "resource_id": event.resource_id,
            "severity": event.severity.value,
            "timestamp": event.timestamp.isoformat(),
            "details": event.details,
        }
    )


# ============================================================================
# Application Setup
# ============================================================================
provider: PostgreSQLProvider | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Initializes the GL-IAM gateway with an audit callback to capture
    all agent lifecycle events.
    """
    global provider

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
    gateway = IAMGateway(
        auth_provider=provider,
        user_store=provider,
        session_provider=provider,
        organization_provider=provider,
        agent_provider=provider,
        audit_callback=audit_callback,
    )
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    yield

    await provider.close()


app = FastAPI(
    title="Agent Lifecycle API",
    description="GL-IAM Agent Lifecycle Management",
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
    """Request model for delegation."""

    agent_id: str
    scopes: list[str] = []


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "service": "agent-lifecycle"}


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
# Agent Lifecycle Endpoints
# ============================================================================
@app.post("/agents/register")
async def register_agent(
    request: AgentRegisterRequest,
    user: User = Depends(get_current_user),
):
    """Register a new agent."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

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
            operator_org_id=org_id,
            allowed_scopes=request.allowed_scopes,
        )
    )

    if result.is_ok:
        agent = result.value
        return {
            "id": agent.id,
            "name": agent.name,
            "status": agent.status.value,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/agents/{agent_id}/suspend")
async def suspend_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
):
    """Suspend an agent. Suspended agents cannot receive delegations."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = await gateway.suspend_agent(agent_id, organization_id=org_id)

    if result.is_ok:
        return {"agent_id": agent_id, "status": "suspended", "message": "Agent suspended successfully"}
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/agents/{agent_id}/revoke")
async def revoke_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
):
    """Revoke an agent permanently. Revoked agents cannot be reactivated."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = await gateway.revoke_agent(agent_id, organization_id=org_id)

    if result.is_ok:
        return {"agent_id": agent_id, "status": "revoked", "message": "Agent revoked permanently"}
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/agents/{agent_id}/reactivate")
async def reactivate_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
):
    """
    Reactivate a suspended agent.

    Note: reactivate_agent is a provider-level operation, not available
    on the gateway directly. This is intentional — reactivation requires
    direct provider access for security.
    """
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    agent_provider = gateway.agent_provider
    if agent_provider is None:
        raise HTTPException(status_code=500, detail="Agent provider not configured")

    result = await agent_provider.reactivate_agent(agent_id, organization_id=org_id)

    if result.is_ok:
        return {"agent_id": agent_id, "status": "active", "message": "Agent reactivated successfully"}
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.get("/agents")
async def list_agents(
    user: User = Depends(get_current_user),
    org: str | None = Query(None, description="Filter by organization"),
    owner: str | None = Query(None, description="Filter by owner user ID"),
    type: str | None = Query(None, description="Filter by agent type"),
    include_revoked: bool = Query(False, description="Include revoked agents"),
):
    """List agents with optional filters."""
    gateway = get_iam_gateway()

    agent_type = None
    if type:
        type_map = {
            "orchestrator": AgentType.ORCHESTRATOR,
            "worker": AgentType.WORKER,
            "tool": AgentType.TOOL,
            "autonomous": AgentType.AUTONOMOUS,
        }
        agent_type = type_map.get(type.lower())

    agents = await gateway.list_agents(
        organization_id=org,
        owner_user_id=owner or user.id,
        agent_type=agent_type,
        include_revoked=include_revoked,
    )

    return {
        "agents": [
            {
                "id": agent.id,
                "name": agent.name,
                "agent_type": agent.agent_type.value,
                "status": agent.status.value,
                "created_at": agent.created_at.isoformat() if agent.created_at else None,
                "revoked_at": agent.revoked_at.isoformat() if agent.revoked_at else None,
            }
            for agent in agents
        ],
        "total": len(agents),
    }


@app.post("/delegate")
async def delegate(
    request: DelegateRequest,
    user: User = Depends(get_current_user),
    authorization: str = Header(),
):
    """
    Delegate to an agent. Demonstrates how delegation fails for
    suspended or revoked agents.
    """
    gateway = get_iam_gateway()

    # Extract the raw JWT from the Authorization header
    token = authorization.split(" ", 1)[1] if " " in authorization else authorization

    task = TaskContext(id="lifecycle-task", purpose="Lifecycle demo")
    scope = DelegationScope(scopes=request.scopes)

    result = await gateway.delegate_to_agent(
        principal_token=token,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
    )

    if result.is_ok:
        return {
            "status": "success",
            "delegation_token": result.value.token,
        }
    else:
        return {
            "status": "denied",
            "error": result.error.message,
            "error_code": result.error.code,
        }


# ============================================================================
# Audit Log Endpoint
# ============================================================================
@app.get("/audit-log")
async def get_audit_log(user: User = Depends(get_current_user)):
    """Return captured audit events."""
    return {
        "events": audit_log,
        "total": len(audit_log),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
