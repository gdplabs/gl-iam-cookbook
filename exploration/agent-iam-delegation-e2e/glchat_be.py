"""
GLChat BE — Service 1 (port 8000).

The outermost service: handles user authentication, agent registration,
and the core delegation flow. When a user triggers an agent via /chat/run-agent,
this service:

1. Authenticates the user (Bearer token)
2. Applies ABAC logic — user's role determines the delegation scope ceiling
3. Creates a stateless delegation token via delegate_to_agent()
4. Forwards the request + delegation token to AIP Backend

Architecture role:
    **GLChat BE (8000)** → AIP Backend (8001) → Connectors (8002)
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
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

logger = logging.getLogger("glchat_be")
logging.basicConfig(level=logging.INFO, format="%(message)s")

AIP_BACKEND_URL = os.getenv("AIP_BACKEND_URL", "http://localhost:8001")

# ============================================================================
# ABAC: Role-based scope attenuation
# ============================================================================
# In a real system, user roles/scopes come from the database.
# Here we simulate 3 roles with different scope ceilings.
USER_ROLE_DB: dict[str, str] = {}  # user_id -> role (set at registration)

ROLE_SCOPES: dict[str, dict] = {
    "admin": {
        "scopes": ["calendar:read", "calendar:write", "slack:post", "notion:read", "gmail:send"],
        "description": "Full access — all platform scopes",
    },
    "member": {
        "scopes": ["calendar:read", "calendar:write", "notion:read"],
        "description": "Standard access — no slack, no gmail",
    },
    "viewer": {
        "scopes": ["calendar:read", "notion:read"],
        "description": "Read-only access",
    },
}


def audit_log(event: str, delegation_ref: str, **kwargs):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "glchat_be",
        "event": event,
        "delegation_ref": delegation_ref,
        **kwargs,
    }
    logger.info(json.dumps(entry))


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
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
    title="GLChat BE — Service 1",
    description="User auth, ABAC, delegation token creation",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None
    role: str = "member"  # admin | member | viewer


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class AgentRegisterRequest(BaseModel):
    name: str
    agent_type: str = "orchestrator"
    allowed_scopes: list[str] = []
    max_delegation_depth: int = 5


class RunAgentRequest(BaseModel):
    agent_id: str
    user_message: str = "Schedule a meeting and notify the team"
    tool_inputs: dict[str, dict] = {}


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "glchat_be", "port": 8000}


@app.post("/register")
async def register(request: RegisterRequest):
    """Register a demo user with a role (admin/member/viewer)."""
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

    # Store role for ABAC (in-memory for demo)
    role = request.role if request.role in ROLE_SCOPES else "member"
    USER_ROLE_DB[user.id] = role

    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": role,
    }


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate and return Bearer token."""
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
    raise HTTPException(status_code=401, detail=result.error.message)


# ============================================================================
# Agent Management
# ============================================================================
@app.post("/agents/register")
async def register_agent(
    request: AgentRegisterRequest,
    user: User = Depends(get_current_user),
):
    """Register an agent with allowed_scopes (the agent's scope ceiling)."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    agent_type_map = {
        "orchestrator": AgentType.ORCHESTRATOR,
        "worker": AgentType.WORKER,
        "tool": AgentType.TOOL,
        "autonomous": AgentType.AUTONOMOUS,
    }
    agent_type = agent_type_map.get(request.agent_type.lower(), AgentType.ORCHESTRATOR)

    result = await gateway.register_agent(
        AgentRegistration(
            name=request.name,
            agent_type=agent_type,
            owner_user_id=user.id,
            operator_org_id=org_id,
            allowed_scopes=request.allowed_scopes,
            max_delegation_depth=request.max_delegation_depth,
        )
    )
    if result.is_ok:
        agent = result.value
        return {
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type.value,
            "allowed_scopes": agent.allowed_scopes,
        }
    raise HTTPException(status_code=400, detail=result.error.message)


# ============================================================================
# Core Flow: ABAC → Delegate → Forward to AIP
# ============================================================================
@app.post("/chat/run-agent")
async def run_agent(
    request: RunAgentRequest,
    user: User = Depends(get_current_user),
    authorization: str = Header(),
):
    """
    The star endpoint. Demonstrates the full delegation flow:
    1. Look up user role → apply ABAC scope attenuation
    2. Create delegation token (stateless JWT, no DB write)
    3. Forward to AIP Backend with X-Delegation-Token header
    """
    gateway = get_iam_gateway()
    delegation_ref = f"dlg-{uuid.uuid4().hex[:12]}"

    # --- Step 1: ABAC — determine scopes based on user role ---
    role = USER_ROLE_DB.get(user.id, "member")

    # Look up agent to get its allowed_scopes ceiling
    agents = await gateway.list_agents(owner_user_id=None)
    agent = next((a for a in agents if a.id == request.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {request.agent_id} not found")

    # Apply role-based scope attenuation: intersection of user scopes and agent ceiling
    user_scopes = ROLE_SCOPES[role]["scopes"]
    attenuated_scopes = [s for s in agent.allowed_scopes if s in user_scopes]

    audit_log(
        "abac_applied",
        delegation_ref,
        user_id=user.id,
        user_role=role,
        user_scopes=user_scopes,
        agent_id=request.agent_id,
        agent_ceiling=agent.allowed_scopes,
        attenuated_scopes=attenuated_scopes,
    )

    if not attenuated_scopes:
        raise HTTPException(
            status_code=403,
            detail=f"Role '{role}' has no permitted scopes for this agent",
        )

    # --- Step 2: Create delegation token (stateless JWT) ---
    token = authorization.split(" ", 1)[1] if " " in authorization else authorization

    task = TaskContext(
        id=f"task-{uuid.uuid4().hex[:8]}",
        purpose=f"User '{user.display_name}' ({role}) → agent run",
        metadata={"delegation_ref": delegation_ref, "user_role": role},
    )

    scope = DelegationScope(
        scopes=attenuated_scopes,
        expires_in_seconds=3600,
    )

    result = await gateway.delegate_to_agent(
        principal_token=token,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
        principal_scope=DelegationScope(scopes=attenuated_scopes),
    )

    if result.is_err:
        raise HTTPException(status_code=400, detail=result.error.message)

    delegation = result.value
    audit_log(
        "delegation_created",
        delegation_ref,
        user_id=user.id,
        agent_id=request.agent_id,
        scopes=attenuated_scopes,
    )

    # --- Step 3: Forward to AIP Backend ---
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AIP_BACKEND_URL}/agents/{request.agent_id}/run",
                json={
                    "user_message": request.user_message,
                    "tool_inputs": request.tool_inputs,
                },
                headers={"X-Delegation-Token": delegation.token},
                timeout=30.0,
            )
            aip_result = resp.json()
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"AIP Backend unreachable: {e}")

    return {
        "delegation_ref": delegation_ref,
        "delegation_token": delegation.token,
        "user": {"id": user.id, "email": user.email, "role": role, "scopes": user_scopes},
        "abac": {
            "user_scopes": user_scopes,
            "agent_ceiling": agent.allowed_scopes,
            "attenuated_scopes": attenuated_scopes,
            "rule": ROLE_SCOPES[role]["description"],
        },
        "aip_response": aip_result,
    }


if __name__ == "__main__":
    import uvicorn

    class HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(HealthFilter())

    uvicorn.run(app, host="0.0.0.0", port=8000)
