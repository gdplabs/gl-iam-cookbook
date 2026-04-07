"""
GLChat BE — Service 1 (port 8000).

Extended from the E2E demo with:
- Tenant enforcement (UC-DE-04, UC-DE-05)
- Feature-level ABAC scope gating (UC-DE-06)
- Resource context pass-through
- Scenario endpoints for dashboard
- Autonomous agent run (AIP use cases)
- Audit event storage
- CORS for dashboard frontend
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
    composite_validator,
    string_equality_validator,
    set_subset_validator,
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user,
    get_iam_gateway,
    set_iam_gateway,
)
from gl_iam import ConsoleAuditHandler, CallbackAuditHandler
from gl_iam.core.gateway import AuditConfig
from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider, DatabaseAuditHandler

from mock_data import USERS as MOCK_USERS
from scenarios import SCENARIOS, get_scenarios_by_product
from shared import AUDIT_STORE, add_audit_routes, add_cors, audit_log

load_dotenv()

logger = logging.getLogger("glchat_be")
logging.basicConfig(level=logging.INFO, format="%(message)s")

AIP_BACKEND_URL = os.getenv("AIP_BACKEND_URL", "http://localhost:8001")
DEFAULT_PASSWORD = "SecurePass123!"

# =============================================================================
# ABAC: Role-based scope attenuation (extended with DE/AIP scopes)
# =============================================================================
USER_ROLE_DB: dict[str, dict] = {}  # user_id -> {role, tenant, features, email, ...}

ROLE_SCOPES: dict[str, dict] = {
    "admin": {
        "scopes": [
            "calendar:read", "calendar:write", "slack:post", "notion:read", "gmail:send",
            "meemo:read", "meemo:write", "gdoc:read", "gdoc:write", "gdoc:share",
            "invoice:send", "directory:lookup",
        ],
        "description": "Full access - all platform scopes",
    },
    "member": {
        "scopes": [
            "calendar:read", "calendar:write", "notion:read",
            "meemo:read", "meemo:write", "gdoc:read", "gdoc:write", "gdoc:share",
            "gmail:send", "directory:lookup",
        ],
        "description": "Standard access - no slack, no invoice by default",
    },
    "viewer": {
        "scopes": ["calendar:read", "notion:read", "meemo:read", "gdoc:read", "directory:lookup"],
        "description": "Read-only access",
    },
}

# Agent configurations for different products
AGENT_CONFIGS = {
    "scheduling-agent": {
        "type": "orchestrator",
        "product": "glchat",
        "allowed_scopes": ["calendar:read", "calendar:write", "slack:post", "notion:read", "directory:lookup"],
        "tenant": "*",
    },
    "de-pm-agent": {
        "type": "orchestrator",
        "product": "de",
        "allowed_scopes": [
            "meemo:read", "meemo:write", "gdoc:read", "gdoc:write", "gdoc:share",
            "gmail:send", "calendar:read", "invoice:send",
        ],
        "tenant": "*",
    },
    "weekly-report-agent": {
        "type": "autonomous",
        "product": "aip",
        "allowed_scopes": ["gdoc:read", "gdoc:write", "gdoc:share", "gmail:send"],
        "tenant": "*",
    },
}

WORKER_CONFIGS = {
    "calendar-worker": {
        "type": "worker",
        "allowed_scopes": ["calendar:read", "calendar:write"],
    },
    "comms-worker": {
        "type": "worker",
        "allowed_scopes": ["slack:post", "notion:read", "gmail:send"],
    },
    "meemo-worker": {
        "type": "worker",
        "allowed_scopes": ["meemo:read", "meemo:write"],
    },
    "gdoc-worker": {
        "type": "worker",
        "allowed_scopes": ["gdoc:read", "gdoc:write", "gdoc:share"],
    },
    "invoice-worker": {
        "type": "worker",
        "allowed_scopes": ["invoice:send", "gmail:send"],
    },
    "directory-worker": {
        "type": "worker",
        "allowed_scopes": ["directory:lookup"],
    },
}

# Store registered agent/user IDs for scenario execution
REGISTERED_AGENTS: dict[str, str] = {}  # agent_name -> agent_id
REGISTERED_USERS: dict[str, dict] = {}  # email -> {id, token, ...}


# =============================================================================
# Application Setup
# =============================================================================
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
    # Register resource constraint validator for delegation token enforcement
    gateway._resource_constraint_validator = composite_validator(
        string_equality_validator,
        set_subset_validator,
    )
    # Enable GL-IAM audit trail — SDK auto-emits events for authenticate, delegate, etc.
    from shared import capture_sdk_event
    console_handler = ConsoleAuditHandler(logger_name="gl_iam.audit")
    callback_handler = CallbackAuditHandler(capture_sdk_event)
    db_audit_handler = DatabaseAuditHandler(provider)
    gateway._audit_handlers = [console_handler, callback_handler, db_audit_handler]
    set_iam_gateway(gateway, default_organization_id=default_org_id)
    yield
    db_audit_handler.close()
    await provider.close()


app = FastAPI(
    title="GLChat BE - Agent IAM Dashboard",
    description="User auth, ABAC, delegation, tenant enforcement, scenario runner",
    lifespan=lifespan,
)
add_cors(app)
add_audit_routes(app)


# =============================================================================
# Request/Response Models
# =============================================================================
class RegisterRequest(BaseModel):
    email: str
    password: str = DEFAULT_PASSWORD
    display_name: str | None = None
    role: str = "member"
    tenant: str = "GLC"
    features: list[str] = []


class LoginRequest(BaseModel):
    email: str
    password: str = DEFAULT_PASSWORD


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
    resource_context: dict = {}


class RunScenarioRequest(BaseModel):
    scenario_id: str


# =============================================================================
# Public Endpoints
# =============================================================================
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "glchat_be", "port": 8000}


@app.post("/register")
async def register(request: RegisterRequest):
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

    role = request.role if request.role in ROLE_SCOPES else "member"
    mock_user = MOCK_USERS.get(request.email, {})

    USER_ROLE_DB[user.id] = {
        "role": role,
        "tenant": request.tenant,
        "features": request.features or mock_user.get("features", []),
        "email": request.email,
        "active": mock_user.get("active", True),
        "is_super_user": mock_user.get("is_super_user", False),
    }

    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": role,
        "tenant": request.tenant,
    }


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
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


# =============================================================================
# Agent Management
# =============================================================================
@app.post("/agents/register")
async def register_agent(
    request: AgentRegisterRequest,
    user: User = Depends(get_current_user),
):
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
        REGISTERED_AGENTS[request.name] = agent.id
        return {
            "id": agent.id,
            "name": agent.name,
            "agent_type": agent.agent_type.value,
            "allowed_scopes": agent.allowed_scopes,
        }
    raise HTTPException(status_code=400, detail=result.error.message)


@app.get("/agents")
async def list_agents():
    gateway = get_iam_gateway()
    agents = await gateway.list_agents(owner_user_id=None)
    return [
        {
            "id": a.id,
            "name": a.name,
            "agent_type": a.agent_type.value,
            "allowed_scopes": a.allowed_scopes,
            "status": a.status.value,
        }
        for a in agents
    ]


# =============================================================================
# Core Flow: ABAC -> Delegate -> Forward to AIP
# =============================================================================
@app.post("/chat/run-agent")
async def run_agent(
    request: RunAgentRequest,
    user: User = Depends(get_current_user),
    authorization: str = Header(),
):
    gateway = get_iam_gateway()
    delegation_ref = f"dlg-{uuid.uuid4().hex[:12]}"

    # --- Step 0: Check user account validity ---
    user_info = USER_ROLE_DB.get(user.id, {})
    if not user_info.get("active", True):
        audit_log("glchat_be", "account_invalid", delegation_ref, user_id=user.id)
        raise HTTPException(
            status_code=403,
            detail="Account is deactivated. Authorization is no longer valid.",
        )

    # --- Step 0b: Tenant enforcement ---
    user_tenant = user_info.get("tenant", "GLC")
    agents = await gateway.list_agents(owner_user_id=None)
    agent = next((a for a in agents if a.id == request.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {request.agent_id} not found")

    # Check agent config for tenant
    # Agent tenant="*" means accessible to all orgs (resource constraints enforce boundaries)
    agent_config = AGENT_CONFIGS.get(agent.name, {})
    agent_tenant = agent_config.get("tenant", "*")
    if agent_tenant != "*" and user_tenant != "NONE" and user_tenant != agent_tenant:
        audit_log(
            "glchat_be", "tenant_boundary_violation", delegation_ref,
            user_id=user.id, user_tenant=user_tenant, agent_tenant=agent_tenant,
        )
        raise HTTPException(
            status_code=403,
            detail=f"Tenant boundary violation. User ({user_tenant}) cannot invoke agent ({agent_tenant}).",
        )

    # --- Step 1: ABAC - determine scopes based on role + features ---
    role = user_info.get("role", "member")
    user_scopes = list(ROLE_SCOPES[role]["scopes"])

    # Feature-level scope gating: add feature-specific scopes
    user_features = user_info.get("features", [])
    # If user doesn't have invoice:send feature, remove it from scopes
    if "invoice:send" not in user_features and "invoice:send" in user_scopes:
        user_scopes.remove("invoice:send")

    # Apply role-based scope attenuation: intersection of user scopes and agent ceiling
    attenuated_scopes = [s for s in agent.allowed_scopes if s in user_scopes]

    # --- Step 1b: Resource context ---
    resource_context = request.resource_context
    # Note: write_to_others is NOT rejected here — it flows through the delegation
    # chain and is enforced at the connector/tool level via resource constraints.

    audit_log(
        "glchat_be", "abac_applied", delegation_ref,
        user_id=user.id, user_role=role, user_scopes=user_scopes,
        user_features=user_features,
        agent_id=request.agent_id, agent_ceiling=agent.allowed_scopes,
        attenuated_scopes=attenuated_scopes,
    )

    if not attenuated_scopes:
        return {
            "delegation_ref": delegation_ref,
            "delegation_token": None,
            "user": {"id": user.id, "email": user.email, "role": role, "scopes": user_scopes},
            "abac": {
                "user_scopes": user_scopes,
                "agent_ceiling": agent.allowed_scopes,
                "attenuated_scopes": [],
                "rule": ROLE_SCOPES[role]["description"],
            },
            "outcome": "rejected",
            "reason": f"Role '{role}' has no permitted scopes for this agent",
            "aip_response": None,
        }

    # --- Step 2: Create delegation token (stateless JWT) ---
    token = authorization.split(" ", 1)[1] if " " in authorization else authorization

    task = TaskContext(
        id=f"task-{uuid.uuid4().hex[:8]}",
        purpose=f"User '{user.display_name}' ({role}) -> agent run",
        metadata={
            "delegation_ref": delegation_ref,
            "user_role": role,
            "resource_context": resource_context,
        },
    )

    # Build resource constraints based on role + user's org
    user_tenant = user_info.get("tenant", "GLC")
    constraints: dict[str, object] = {
        "tenant_id": user_tenant,
        "user_email": user.email,
    }
    # Agent calendar access constraint (role-based, org-dynamic)
    if role == "admin":
        constraints["agent_calendar_access"] = "*"       # read: any calendar, any org
        constraints["agent_calendar_write_access"] = "*"  # write: any calendar
    elif role == "member":
        # Dynamic: org constraint based on the user who triggered the agent
        constraints["agent_calendar_access"] = ["onlee@gdplabs.id", f"org:{user_tenant}"]  # read: CEO + user's own org
        constraints["agent_calendar_write_access"] = ["onlee@gdplabs.id"]                    # write: only Pak On
    else:
        constraints["agent_calendar_access"] = ["onlee@gdplabs.id"]  # viewer/guest — only Pak On (read)
        constraints["agent_calendar_write_access"] = []               # no write access

    # Add scenario-specific resource constraints
    if resource_context.get("target_calendar"):
        constraints["target_calendar"] = resource_context["target_calendar"]
    # Note: write_to_others is detected at tool level by comparing
    # target_calendar vs user_email — not set as a constraint here

    # User features (for feature-level scope)
    if user_features:
        constraints["user_features"] = user_features

    scope = DelegationScope(
        scopes=attenuated_scopes,
        resource_constraints=constraints,
        expires_in_seconds=3600,
    )

    result = await gateway.delegate_to_agent(
        principal_token=token,
        agent_id=request.agent_id,
        task=task,
        scope=scope,
        principal_scope=DelegationScope(
            scopes=attenuated_scopes,
            resource_constraints=constraints,
        ),
    )

    if result.is_err:
        raise HTTPException(status_code=400, detail=result.error.message)

    delegation = result.value
    audit_log(
        "glchat_be", "delegation_created", delegation_ref,
        user_id=user.id, agent_id=request.agent_id, scopes=attenuated_scopes,
    )

    # --- Step 3: Forward to AIP Backend ---
    # Enrich resource_context with user_role for credential routing at connectors
    enriched_context = {**resource_context, "_user_role": role}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AIP_BACKEND_URL}/agents/{request.agent_id}/run",
                json={
                    "user_message": request.user_message,
                    "tool_inputs": request.tool_inputs,
                    "resource_context": enriched_context,
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
        "outcome": "delegated",
        "aip_response": aip_result,
    }


# =============================================================================
# Autonomous Agent Run (AIP use cases - no user bearer token)
# =============================================================================
@app.post("/agents/autonomous-run")
async def autonomous_run(request: RunAgentRequest):
    """Run an agent under its own identity (no user delegation)."""
    gateway = get_iam_gateway()
    delegation_ref = f"dlg-{uuid.uuid4().hex[:12]}"

    agents = await gateway.list_agents(owner_user_id=None)
    agent = next((a for a in agents if a.id == request.agent_id), None)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {request.agent_id} not found")

    # For autonomous agents, we need to create a delegation using owner's token
    owner_info = None
    for uid, info in USER_ROLE_DB.items():
        if info.get("role") in ("admin", "member"):
            owner_info = (uid, info)
            break

    if not owner_info:
        raise HTTPException(status_code=500, detail="No owner user available for autonomous delegation")

    # Find the owner's registered data to get their token
    owner_email = owner_info[1].get("email")
    owner_reg = REGISTERED_USERS.get(owner_email)
    if not owner_reg:
        raise HTTPException(status_code=500, detail="Owner user not logged in")

    task = TaskContext(
        id=f"task-{uuid.uuid4().hex[:8]}",
        purpose=f"Autonomous agent '{agent.name}' execution",
        metadata={
            "delegation_ref": delegation_ref,
            "autonomous": True,
            "resource_context": request.resource_context,
        },
    )

    autonomous_constraints: dict[str, object] = {
        "tenant_id": "GLC",
        "autonomous": True,
        "agent_calendar_access": "*",
    }

    scope = DelegationScope(
        scopes=agent.allowed_scopes,
        resource_constraints=autonomous_constraints,
        expires_in_seconds=3600,
    )

    result = await gateway.delegate_to_agent(
        principal_token=owner_reg["token"],
        agent_id=request.agent_id,
        task=task,
        scope=scope,
        principal_scope=DelegationScope(
            scopes=agent.allowed_scopes,
            resource_constraints=autonomous_constraints,
        ),
    )

    if result.is_err:
        raise HTTPException(status_code=400, detail=result.error.message)

    delegation = result.value
    audit_log(
        "glchat_be", "autonomous_delegation_created", delegation_ref,
        agent_id=request.agent_id, scopes=agent.allowed_scopes,
    )

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{AIP_BACKEND_URL}/agents/{request.agent_id}/run",
                json={
                    "user_message": request.user_message,
                    "tool_inputs": request.tool_inputs,
                    "resource_context": request.resource_context,
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
        "user": None,
        "abac": {
            "user_scopes": agent.allowed_scopes,
            "agent_ceiling": agent.allowed_scopes,
            "attenuated_scopes": agent.allowed_scopes,
            "rule": "Autonomous agent - uses own scope ceiling",
        },
        "outcome": "delegated",
        "aip_response": aip_result,
    }


# =============================================================================
# Scenario & Interactive Endpoints (for Dashboard)
# =============================================================================
@app.get("/scenarios")
async def list_scenarios():
    return get_scenarios_by_product()


@app.get("/scenarios/{scenario_id}")
async def get_scenario(scenario_id: str):
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")
    return {"id": scenario_id, **scenario}


@app.get("/demo/users")
async def list_demo_users():
    """Return 4 user archetypes with org info."""
    archetypes = [
        {"role": "admin",  "email": "onlee@gdplabs.id",    "label": "Pak On"},
        {"role": "member", "email": "maylina@gdplabs.id",  "label": "Maylina"},
        {"role": "member", "email": "petry@gdplabs.id",    "label": "Petry"},
        {"role": "viewer", "email": "guest@gdplabs.id",    "label": "Guest"},
    ]
    result = []
    for arch in archetypes:
        email = arch["email"]
        mock = MOCK_USERS.get(email, {})
        role = arch["role"]
        result.append({
            "email": email,
            "display_name": arch["label"],
            "role": role,
            "tenant": mock.get("tenant", "GLC"),
            "features": mock.get("features", []),
            "is_super_user": mock.get("is_super_user", False),
            "scopes": ROLE_SCOPES.get(role, {}).get("scopes", []),
        })
    return result


@app.get("/demo/orchestrators")
async def list_orchestrator_agents():
    """Return registered orchestrator/autonomous agents (for interactive picker)."""
    result = []
    for agent_name, agent_id in REGISTERED_AGENTS.items():
        config = AGENT_CONFIGS.get(agent_name)
        if config:
            result.append({
                "id": agent_id,
                "name": agent_name,
                "type": config["type"],
                "product": config.get("product", ""),
                "allowed_scopes": config["allowed_scopes"],
            })
    return result


# Deduplicated action catalog — maps action key to base scenario ID.
# The interactive-run endpoint resolves the correct variant based on user role.
ACTION_CATALOG: dict[str, dict] = {
    # scheduling-agent
    "check-own-calendar": {
        "agent": "scheduling-agent",
        "title": "Check own calendar schedule",
        "message": "Give me a list of my meetings today",
        "description": "Read-only access to the user's own calendar.",
        "concepts": ["Delegated Access", "Auto-Approval (Read-Only)"],
        "base_scenario": "UC-GLCHAT-01.1",
    },
    "check-ceo-calendar": {
        "agent": "scheduling-agent",
        "title": "Check Pak On (CEO) calendar schedule",
        "message": "Give me a list of Pak On's meetings today",
        "description": "Access CEO's calendar. All logged-in roles can use Agent OAuth (whitelisted). Guest rejected.",
        "concepts": ["Delegated Access", "Resource Constraint", "Agent OAuth"],
        "base_scenario": "UC-GLCHAT-01.2",
    },
    "check-sandy-calendar": {
        "agent": "scheduling-agent",
        "title": "Check Sandy's calendar (GLC)",
        "message": "Give me a list of Sandy's meetings today",
        "description": "Sandy is in GLC org. Same-org members can access via Agent OAuth. Cross-org members rejected.",
        "concepts": ["Delegated Access", "Resource Constraint", "Org Boundary"],
        "base_scenario": "UC-GLCHAT-01.3",
    },
    "check-petry-calendar": {
        "agent": "scheduling-agent",
        "title": "Check Petry's calendar (GLAIR)",
        "message": "Give me a list of Petry's meetings today",
        "description": "Petry is in GLAIR org. Same-org (GLAIR) members can access. Cross-org (GLC) members rejected by resource constraint.",
        "concepts": ["Delegated Access", "Resource Constraint", "Org Boundary"],
        "base_scenario": "UC-GLCHAT-01.4",
    },
    "schedule-own-meeting": {
        "agent": "scheduling-agent",
        "title": "Schedule meeting on own calendar",
        "message": "Schedule a 1-hour sync with Sandy and Petry this Friday at 3pm",
        "description": "Write action on own calendar.",
        "concepts": ["Delegated Access", "Approval Boundary (Write)"],
        "base_scenario": "UC-GLCHAT-02.1",
    },
    "write-colleague-calendar": {
        "agent": "scheduling-agent",
        "title": "Write to colleague's calendar",
        "message": "Add a dentist appointment to Sandy's calendar tomorrow at 10am",
        "description": "Attempt to write to another user's calendar. Rejected for all roles.",
        "concepts": ["Resource Constraint", "Write Protection"],
        "base_scenario": "UC-GLCHAT-02.2",
    },
    "scheduled-task": {
        "agent": "scheduling-agent",
        "title": "Scheduled task (daily meeting list)",
        "message": "Send daily meeting list (scheduled task)",
        "description": "Pre-authorized recurring task. Admin only — tests account validity at execution time.",
        "concepts": ["Pre-authorised Revalidation", "Admin Only"],
        "admin_only": True,
        "base_scenario": "UC-GLCHAT-03.1",
    },
    # de-pm-agent
    "create-mom": {
        "agent": "de-pm-agent",
        "title": "Create Minutes of Meeting",
        "message": "Create minutes of meeting for GL IAM standup",
        "description": "DE PM creates MoM on Meemo and Google Docs.",
        "concepts": ["Implicit Consent", "Agent's Own Access"],
        "base_scenario": "UC-DE-01.1",
    },
    "share-mom": {
        "agent": "de-pm-agent",
        "title": "Share MoM with attendees",
        "message": "Share the GL IAM standup MoM with all attendees",
        "description": "Share meeting notes. Only organiser can share.",
        "concepts": ["Delegated Access", "Resource Ownership"],
        "base_scenario": "UC-DE-02.1",
    },
    "access-mom": {
        "agent": "de-pm-agent",
        "title": "Access/summarize MoM",
        "message": "Summarize yesterday's GL IAM standup",
        "description": "Read MoM. Access depends on attendee status and role.",
        "concepts": ["Delegated Access", "Hierarchical Access"],
        "base_scenario": "UC-DE-03.1",
    },
    "send-invoice": {
        "agent": "de-pm-agent",
        "title": "Send Invoice",
        "message": "Send all AWS invoices April 2026",
        "description": "Feature-level access control. Only entitled users can send invoices.",
        "concepts": ["Feature-Level Access Control"],
        "base_scenario": "UC-DE-06.1",
    },
    # weekly-report-agent
    "weekly-report": {
        "agent": "weekly-report-agent",
        "title": "Send weekly report",
        "message": "Send final weekly report for onlee@gdplabs.id",
        "description": "Autonomous agent sends compiled weekly report.",
        "concepts": ["Agent's Own Identity", "Autonomous Execution"],
        "base_scenario": "UC-AIP-01.1",
    },
    "draft-report": {
        "agent": "weekly-report-agent",
        "title": "Send draft report",
        "message": "Send draft weekly report to onlee@gdplabs.id",
        "description": "Autonomous agent creates and sends draft for employee to fill.",
        "concepts": ["Agent's Own Identity", "Agent Resource Access"],
        "base_scenario": "UC-AIP-02.1",
    },
}

# Map (action_key, role) -> scenario_id override
# If not in this map, use the base_scenario from ACTION_CATALOG
ACTION_ROLE_OVERRIDES: dict[tuple[str, str], str] = {
    # Member (Petry) variants
    ("check-own-calendar", "member"): "UC-GLCHAT-01.1-M",
    ("check-ceo-calendar", "member"): "UC-GLCHAT-01.2-M",
    ("check-sandy-calendar", "member"): "UC-GLCHAT-01.3-M",
    # Note: check-petry-calendar for member uses base scenario — dynamic constraint
    # resolves correctly: Maylina (GLC) gets org:GLC → rejects petry (GLAIR),
    # Petry (GLAIR) gets org:GLAIR → allows petry (GLAIR)
    ("schedule-own-meeting", "member"): "UC-GLCHAT-02.1-M",
    ("write-colleague-calendar", "member"): "UC-GLCHAT-02.2-M",
}


@app.get("/demo/actions")
async def list_actions():
    """Return deduplicated actions grouped by agent. No spoilers."""
    grouped: dict[str, list[dict]] = {}
    for action_key, action in ACTION_CATALOG.items():
        agent = action["agent"]
        if agent not in grouped:
            grouped[agent] = []
        grouped[agent].append({
            "id": action_key,
            "title": action["title"],
            "message": action["message"],
            "description": action["description"],
            "concepts": action["concepts"],
        })
    return grouped


@app.post("/demo/setup")
async def demo_setup():
    """One-click setup: register all demo users + agents. Returns tokens and IDs."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    # Collect unique users from scenarios + role archetypes
    users_to_register = set()
    for scenario in SCENARIOS.values():
        if scenario.get("user_email"):
            users_to_register.add(scenario["user_email"])
    # Always register archetype users for the interactive picker
    users_to_register.add("onlee@gdplabs.id")      # Admin (Pak On)
    users_to_register.add("maylina@gdplabs.id")   # Member (Maylina, GLC)
    users_to_register.add("petry@gdplabs.id")     # Member (Petry, GLAIR)
    users_to_register.add("guest@gdplabs.id")      # Guest (no org)

    # Register users (or login if already exists)
    registered = {}
    for email in sorted(users_to_register):
        mock = MOCK_USERS.get(email, {})
        if not mock.get("active", True):
            registered[email] = {"id": None, "token": None, "role": mock.get("role", "member"),
                                 "active": False, "skipped": True}
            continue

        role = mock.get("role", "member")

        try:
            user = await gateway.user_store.create_user(
                UserCreateInput(
                    email=email,
                    display_name=mock.get("display_name", email.split("@")[0]),
                ),
                organization_id=org_id,
            )
            await gateway.user_store.set_user_password(user.id, DEFAULT_PASSWORD, org_id)
            logger.info(f"Created user: {email}")
        except Exception:
            # User already exists — that's fine, we'll just login
            user = None
            logger.info(f"User already exists: {email}, will login")

        # Login to get token (works for both new and existing users)
        try:
            auth_result = await gateway.authenticate(
                credentials=PasswordCredentials(email=email, password=DEFAULT_PASSWORD),
                organization_id=org_id,
            )
            if auth_result.is_ok:
                token = auth_result.token.access_token
                user_id = user.id if user else auth_result.user.id
                USER_ROLE_DB[user_id] = {
                    "role": role,
                    "tenant": mock.get("tenant", "GLC"),
                    "features": mock.get("features", []),
                    "email": email,
                    "active": mock.get("active", True),
                    "is_super_user": mock.get("is_super_user", False),
                }
                registered[email] = {
                    "id": user_id,
                    "email": email,
                    "display_name": mock.get("display_name", email.split("@")[0]),
                    "role": role,
                    "tenant": mock.get("tenant", "GLC"),
                    "token": token,
                    "active": True,
                }
                REGISTERED_USERS[email] = {"id": user_id, "token": token}
            else:
                registered[email] = {"error": f"Login failed: {auth_result.error.message}"}
        except Exception as e:
            registered[email] = {"error": f"Login error: {e}"}

    # Register agents (using first admin user's token)
    admin_user = next(
        (r for r in registered.values() if r.get("token") and r.get("role") == "admin"),
        next((r for r in registered.values() if r.get("token")), None),
    )

    registered_agents = {}
    if not admin_user:
        logger.error("No admin user with token found! Agent registration skipped.")
        logger.error(f"Registered users: {list(registered.keys())}")
        for email, info in registered.items():
            logger.error(f"  {email}: token={'yes' if info.get('token') else 'no'}, role={info.get('role')}, error={info.get('error')}")
    if admin_user:
        all_agent_configs = {**AGENT_CONFIGS, **WORKER_CONFIGS}
        type_map = {
            "orchestrator": AgentType.ORCHESTRATOR,
            "worker": AgentType.WORKER,
            "autonomous": AgentType.AUTONOMOUS,
        }

        # First, check if agents already exist in the database
        existing_agents = await gateway.list_agents(owner_user_id=None)
        existing_by_name = {a.name: a for a in existing_agents}

        logger.info(f"Registering agents with owner: {admin_user['id']} (org: {org_id})")
        logger.info(f"  Existing agents in DB: {list(existing_by_name.keys())}")

        for agent_name, config in all_agent_configs.items():
            # If agent already exists, just use it
            if agent_name in existing_by_name:
                agent = existing_by_name[agent_name]
                REGISTERED_AGENTS[agent_name] = agent.id
                registered_agents[agent_name] = {
                    "id": agent.id,
                    "name": agent.name,
                    "type": config["type"],
                    "allowed_scopes": config["allowed_scopes"],
                }
                logger.info(f"  {agent_name} -> already exists: {agent.id}")
                continue

            try:
                logger.info(f"Registering agent: {agent_name} (type: {config['type']})")
                result = await gateway.register_agent(
                    AgentRegistration(
                        name=agent_name,
                        agent_type=type_map.get(config["type"], AgentType.ORCHESTRATOR),
                        owner_user_id=admin_user["id"],
                        operator_org_id=org_id,
                        allowed_scopes=config["allowed_scopes"],
                        max_delegation_depth=5,
                    )
                )
                if result.is_ok:
                    agent = result.value
                    REGISTERED_AGENTS[agent_name] = agent.id
                    registered_agents[agent_name] = {
                        "id": agent.id,
                        "name": agent.name,
                        "type": config["type"],
                        "allowed_scopes": config["allowed_scopes"],
                    }
                    logger.info(f"  -> OK: {agent.id}")
                else:
                    logger.error(f"  -> FAILED: {result.error.message}")
                    registered_agents[agent_name] = {"error": result.error.message}
            except Exception as e:
                logger.error(f"  -> EXCEPTION: {e}")
                registered_agents[agent_name] = {"error": str(e)}

    return {
        "users": registered,
        "agents": registered_agents,
        "status": "ready",
    }


@app.post("/scenarios/{scenario_id}/run")
async def run_scenario(scenario_id: str):
    """Execute a BRD scenario. Handles user-delegated and autonomous flows."""
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario {scenario_id} not found")

    user_email = scenario.get("user_email")
    agent_name = scenario["agent"]
    agent_id = REGISTERED_AGENTS.get(agent_name)

    if not agent_id:
        raise HTTPException(status_code=400, detail=f"Agent '{agent_name}' not registered. Run /demo/setup first.")

    # Autonomous agent (AIP use cases)
    if user_email is None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://localhost:8000/agents/autonomous-run",
                json={
                    "agent_id": agent_id,
                    "user_message": scenario["message"],
                    "tool_inputs": scenario.get("tool_inputs", {}),
                    "resource_context": scenario.get("resource_context", {}),
                },
                timeout=30.0,
            )
            result = resp.json()
            return {
                "scenario_id": scenario_id,
                "scenario": {
                    "title": scenario["title"],
                    "description": scenario["description"],
                    "product": scenario["product"],
                    "expected_outcome": scenario["expected_outcome"],
                    "brd_refs": scenario["brd_refs"],
                    "concepts": scenario["concepts"],
                    "access_type": scenario.get("resource_context", {}).get("access_type"),
                },
                **result,
            }

    # User-delegated flow
    user_reg = REGISTERED_USERS.get(user_email)
    if not user_reg or not user_reg.get("token"):
        # User might be deactivated or cross-tenant
        mock = MOCK_USERS.get(user_email, {})
        if not mock.get("active", True):
            return {
                "scenario_id": scenario_id,
                "scenario": {
                    "title": scenario["title"],
                    "description": scenario["description"],
                    "product": scenario["product"],
                    "expected_outcome": scenario["expected_outcome"],
                    "brd_refs": scenario["brd_refs"],
                    "concepts": scenario["concepts"],
                    "access_type": scenario.get("resource_context", {}).get("access_type"),
                },
                "delegation_ref": f"dlg-{uuid.uuid4().hex[:12]}",
                "outcome": "rejected",
                "reason": "Account is deactivated. Authorization is no longer valid.",
                "user": {"email": user_email, "active": False},
                "aip_response": None,
            }
        raise HTTPException(
            status_code=400,
            detail=f"User '{user_email}' not registered. Run /demo/setup first.",
        )

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/chat/run-agent",
            json={
                "agent_id": agent_id,
                "user_message": scenario["message"],
                "tool_inputs": scenario.get("tool_inputs", {}),
                "resource_context": scenario.get("resource_context", {}),
            },
            headers={"Authorization": f"Bearer {user_reg['token']}"},
            timeout=30.0,
        )

        if resp.status_code == 403:
            error_detail = resp.json().get("detail", "Forbidden")
            return {
                "scenario_id": scenario_id,
                "scenario": {
                    "title": scenario["title"],
                    "description": scenario["description"],
                    "product": scenario["product"],
                    "expected_outcome": scenario["expected_outcome"],
                    "brd_refs": scenario["brd_refs"],
                    "concepts": scenario["concepts"],
                    "access_type": scenario.get("resource_context", {}).get("access_type"),
                },
                "delegation_ref": f"dlg-{uuid.uuid4().hex[:12]}",
                "outcome": "rejected",
                "reason": error_detail,
                "user": {"email": user_email},
                "aip_response": None,
            }

        result = resp.json()
        return {
            "scenario_id": scenario_id,
            "scenario": {
                "title": scenario["title"],
                "description": scenario["description"],
                "product": scenario["product"],
                "expected_outcome": scenario["expected_outcome"],
                "brd_refs": scenario["brd_refs"],
                "concepts": scenario["concepts"],
                "access_type": scenario.get("resource_context", {}).get("access_type"),
            },
            **result,
        }


class InteractiveRunRequest(BaseModel):
    user_email: str
    agent_name: str
    scenario_id: str  # This is now the action_key from ACTION_CATALOG


@app.post("/demo/interactive-run")
async def interactive_run(request: InteractiveRunRequest):
    """Run an action with a specific user. Resolves the correct scenario variant
    based on user role via ACTION_ROLE_OVERRIDES."""

    # Resolve action -> scenario
    action = ACTION_CATALOG.get(request.scenario_id)
    if not action:
        raise HTTPException(status_code=404, detail=f"Action '{request.scenario_id}' not found")

    agent_id = REGISTERED_AGENTS.get(request.agent_name)
    if not agent_id:
        raise HTTPException(status_code=400, detail=f"Agent '{request.agent_name}' not registered")

    user_reg = REGISTERED_USERS.get(request.user_email)
    mock = MOCK_USERS.get(request.user_email, {})

    # Determine user role
    user_role = "member"
    user_tenant = "GLC"
    for uid, info in USER_ROLE_DB.items():
        if info.get("email") == request.user_email:
            user_role = info.get("role", "member")
            user_tenant = info.get("tenant", "GLC")
            break

    # Note: Guest restrictions are enforced at the agent worker level via resource constraints.
    # The delegation token is still created — rejection happens when the worker checks
    # agent_calendar_access and finds the target is not in the whitelist.

    # Check admin_only actions
    if action.get("admin_only") and user_role != "admin":
        return {
            "scenario_id": request.scenario_id,
            "scenario": {
                "title": action["title"],
                "description": action["description"],
                "product": "glchat",
                "concepts": action["concepts"],
                "access_type": None,
            },
            "delegation_ref": f"dlg-{uuid.uuid4().hex[:12]}",
            "outcome": "rejected",
            "reason": f"This action is restricted to Admin users only. Your role ({user_role}) cannot trigger scheduled tasks.",
            "user": {"email": request.user_email, "role": user_role},
            "aip_response": None,
        }

    # Resolve scenario: check role override, fall back to base
    scenario_id = ACTION_ROLE_OVERRIDES.get(
        (request.scenario_id, user_role),
        action["base_scenario"],
    )
    scenario = SCENARIOS.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=500, detail=f"Resolved scenario '{scenario_id}' not found")

    logger.info(f"Interactive run: user={request.user_email} role={user_role} action={request.scenario_id} -> scenario={scenario_id}")

    def make_scenario_meta():
        return {
            "title": action["title"],
            "description": action["description"],
            "message": scenario.get("message", action.get("message", "")),
            "product": scenario.get("product", ""),
            "concepts": action["concepts"],
            "access_type": scenario.get("resource_context", {}).get("access_type"),
            "resolved_scenario": scenario_id,
            "user_role": user_role,
        }

    # Check deactivated
    if not mock.get("active", True):
        return {
            "scenario_id": scenario_id,
            "scenario": make_scenario_meta(),
            "delegation_ref": f"dlg-{uuid.uuid4().hex[:12]}",
            "outcome": "rejected",
            "reason": "Account is deactivated. Authorization is no longer valid.",
            "user": {"email": request.user_email, "role": user_role, "active": False},
            "aip_response": None,
        }

    if not user_reg or not user_reg.get("token"):
        raise HTTPException(status_code=400, detail=f"User '{request.user_email}' not registered or logged in")

    # Check tenant boundary
    agent_config = AGENT_CONFIGS.get(request.agent_name, {})
    agent_tenant = agent_config.get("tenant", "*")

    if agent_tenant != "*" and user_tenant != "NONE" and user_tenant != agent_tenant:
        return {
            "scenario_id": scenario_id,
            "scenario": make_scenario_meta(),
            "delegation_ref": f"dlg-{uuid.uuid4().hex[:12]}",
            "outcome": "rejected",
            "reason": f"Tenant boundary violation. User ({user_tenant}) cannot invoke agent ({agent_tenant}).",
            "user": {"email": request.user_email, "role": user_role, "tenant": user_tenant},
            "aip_response": None,
        }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/chat/run-agent",
            json={
                "agent_id": agent_id,
                "user_message": scenario["message"],
                "tool_inputs": scenario.get("tool_inputs", {}),
                "resource_context": scenario.get("resource_context", {}),
            },
            headers={"Authorization": f"Bearer {user_reg['token']}"},
            timeout=30.0,
        )

        if resp.status_code == 403:
            error_detail = resp.json().get("detail", "Forbidden")
            return {
                "scenario_id": scenario_id,
                "scenario": make_scenario_meta(),
                "delegation_ref": f"dlg-{uuid.uuid4().hex[:12]}",
                "outcome": "rejected",
                "reason": error_detail,
                "user": {"email": request.user_email, "role": user_role},
                "aip_response": None,
            }

        result = resp.json()
        return {
            "scenario_id": scenario_id,
            "scenario": make_scenario_meta(),
            **result,
        }


@app.post("/demo/reset")
async def demo_reset():
    """Reset all in-memory state."""
    USER_ROLE_DB.clear()
    REGISTERED_AGENTS.clear()
    REGISTERED_USERS.clear()
    AUDIT_STORE.clear()
    return {"status": "reset"}


if __name__ == "__main__":
    import uvicorn

    class HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(HealthFilter())
    uvicorn.run(app, host="0.0.0.0", port=8000)
