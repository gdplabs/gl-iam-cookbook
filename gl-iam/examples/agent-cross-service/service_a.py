"""
Cross-Service Delegation: Service A (Delegating Service).

This service handles user authentication, agent registration,
and delegation token creation. It runs on port 8000.

Agents registered here can use their delegation tokens to
access Service B endpoints.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
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

    Service A uses the full PostgreSQLProvider with user auth + agent support.
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
    title="Service A - Delegating Service",
    description="Handles user auth, agent registration, and delegation",
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
    task_purpose: str = "Cross-service task"
    expires_in_seconds: int = 3600


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "service": "service-a", "port": 8000}


@app.post("/register")
async def register(request: RegisterRequest):
    """Register a new user."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    result = await gateway.create_user_with_password(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        password=request.password,
        organization_id=org_id,
    )

    if not result.is_ok:
        raise HTTPException(status_code=400, detail=result.error.message)
    user = result.value

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
# Agent Management Endpoints
# ============================================================================
@app.post("/agents/register")
async def register_agent(
    request: AgentRegisterRequest,
    user: User = Depends(get_current_user),
):
    """Register an agent that can access both Service A and Service B."""
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
            "agent_type": agent.agent_type.value,
            "allowed_scopes": agent.allowed_scopes,
            "message": "Agent can use delegation token with Service B",
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


@app.post("/delegate")
async def delegate(
    request: DelegateRequest,
    user: User = Depends(get_current_user),
    authorization: str = Header(),
):
    """Create a delegation token for cross-service use."""
    gateway = get_iam_gateway()

    # Extract the raw JWT from the Authorization header
    token = authorization.split(" ", 1)[1] if " " in authorization else authorization

    task = TaskContext(
        id="cross-service-task-001",
        purpose=request.task_purpose,
    )

    scope = DelegationScope(
        scopes=request.scopes,
        expires_in_seconds=request.expires_in_seconds,
    )

    result = await gateway.delegate_to_agent(
        principal_token=token,
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
            "usage": "Use this token with Service B via X-Delegation-Token header",
        }
    else:
        raise HTTPException(status_code=400, detail=result.error.message)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
