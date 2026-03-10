"""
AIP Backend — Service 2 (port 8001).

Receives delegation tokens from GLChat BE, validates them, determines which
tools the agent can use based on effective scopes, then routes work through
worker sub-agents before calling GL Connectors.

Architecture role (depth-4 delegation):
    GLChat BE (8000) → **AIP Backend (8001)** → Connectors (8002)
    User (d1) → Orchestrator (d2) → Worker Sub-Agent (d3) → Tool (d4)

Simulates agent "planning": given a user message and available tools,
the orchestrator picks which workers to dispatch, each worker delegates
per-tool to GL Connectors.
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import (
    DelegationScope,
    IAMGateway,
    TaskContext,
)
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.core.types.delegation import DelegationToken
from gl_iam.fastapi import (
    get_current_agent,
    get_delegation_token,
    get_iam_gateway,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLAgentProvider, PostgreSQLConfig

load_dotenv()

logger = logging.getLogger("aip_backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")

CONNECTORS_URL = os.getenv("CONNECTORS_URL", "http://localhost:8002")

# ============================================================================
# Tool Registry — maps scopes to available tools
# ============================================================================
TOOL_REGISTRY: dict[str, dict] = {
    "calendar:read": {
        "tool": "calendar.list_events",
        "description": "List upcoming calendar events",
        "endpoint": "/tools/calendar.list_events",
    },
    "calendar:write": {
        "tool": "calendar.create_event",
        "description": "Create a new calendar event",
        "endpoint": "/tools/calendar.create_event",
    },
    "slack:post": {
        "tool": "slack.post_message",
        "description": "Post a message to Slack",
        "endpoint": "/tools/slack.post_message",
    },
    "notion:read": {
        "tool": "notion.get_page",
        "description": "Read a Notion page",
        "endpoint": "/tools/notion.get_page",
    },
    "gmail:send": {
        "tool": "gmail.send",
        "description": "Send an email via Gmail",
        "endpoint": "/tools/gmail.send",
    },
}

# ============================================================================
# Worker Registry — groups tools by worker sub-agent
# ============================================================================
WORKER_REGISTRY: dict[str, dict] = {
    "calendar-worker": {
        "type": "worker",
        "scopes": ["calendar:read", "calendar:write"],
        "tools": ["calendar.list_events", "calendar.create_event"],
    },
    "comms-worker": {
        "type": "worker",
        "scopes": ["slack:post", "notion:read", "gmail:send"],
        "tools": ["slack.post_message", "notion.get_page", "gmail.send"],
    },
}

# Runtime: populated at startup with registered agent IDs
WORKER_AGENT_IDS: dict[str, str] = {}  # worker_name -> agent_id


def audit_log(event: str, delegation_ref: str, **kwargs):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "aip_backend",
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
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_third_party_provider=False,
        auto_create_tables=True,
        default_org_id=os.getenv("DEFAULT_ORGANIZATION_ID", "default"),
    )
    agent_provider = PostgreSQLAgentProvider(config)
    gateway = IAMGateway.for_agent_auth(
        agent_provider=agent_provider,
        secret_key=os.getenv("SECRET_KEY"),
    )
    set_iam_gateway(gateway)

    yield


app = FastAPI(
    title="AIP Backend — Service 2",
    description="Agent execution: validates delegation, routes tools via worker sub-agents",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================
class AgentRunRequest(BaseModel):
    """Request from GLChat BE to run an agent."""
    user_message: str
    tool_inputs: dict[str, dict] = {}


# ============================================================================
# Helper: resolve available tools from effective scopes
# ============================================================================
def resolve_available_tools(effective_scopes: set[str]) -> list[dict]:
    """Given the effective scopes from the delegation chain, return tools the agent can use."""
    available = []
    for scope, tool_info in TOOL_REGISTRY.items():
        if scope in effective_scopes:
            available.append(tool_info)
    return available


def get_delegation_ref(token: DelegationToken) -> str:
    return token.task.metadata.get("delegation_ref", token.task.id)


async def _ensure_worker_ids():
    """Lazily discover worker sub-agent IDs from the database."""
    if WORKER_AGENT_IDS:
        return
    gateway = get_iam_gateway()
    agents = await gateway.list_agents(owner_user_id=None)
    for agent in agents:
        if agent.name in WORKER_REGISTRY:
            WORKER_AGENT_IDS[agent.name] = agent.id
            logger.info(f"Found worker: {agent.name} -> {agent.id}")


def find_worker_for_tool(tool_name: str) -> str | None:
    """Find which worker handles a given tool."""
    for worker_name, worker_info in WORKER_REGISTRY.items():
        if tool_name in worker_info["tools"]:
            return worker_name
    return None


# ============================================================================
# Simple agent planner — picks tools based on user message keywords
# ============================================================================
KEYWORD_TO_TOOLS = {
    "schedule": ["calendar.list_events", "calendar.create_event"],
    "meeting": ["calendar.list_events", "calendar.create_event"],
    "calendar": ["calendar.list_events", "calendar.create_event"],
    "notify": ["slack.post_message"],
    "slack": ["slack.post_message"],
    "message": ["slack.post_message"],
    "document": ["notion.get_page"],
    "notion": ["notion.get_page"],
    "page": ["notion.get_page"],
    "email": ["gmail.send"],
    "gmail": ["gmail.send"],
}


def plan_tools(user_message: str, available_tools: list[dict]) -> list[dict]:
    """Simulate agent planning: pick tools based on keywords in user message."""
    available_names = {t["tool"] for t in available_tools}
    planned_names = set()

    for keyword, tool_names in KEYWORD_TO_TOOLS.items():
        if keyword in user_message.lower():
            for name in tool_names:
                if name in available_names:
                    planned_names.add(name)

    # If no keywords matched, use all available tools (agent decides to use everything)
    if not planned_names:
        planned_names = available_names

    return [t for t in available_tools if t["tool"] in planned_names]


# ============================================================================
# Endpoints
# ============================================================================
@app.post("/agents/{agent_id}/run")
async def run_agent(
    agent_id: str,
    request: AgentRunRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    token: DelegationToken = Depends(get_delegation_token),
):
    """
    Run an agent with depth-4 delegation:
    d2 (orchestrator) → d3 (worker sub-agent) → d4 (tool connector).
    """
    ref = get_delegation_ref(token)

    # 0. Ensure worker sub-agent IDs are loaded
    await _ensure_worker_ids()

    # 1. Validate agent_id matches token
    if token.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Token agent_id mismatch")

    # 2. Get effective scopes from the delegation chain
    effective_scopes = token.chain.effective_scopes()
    audit_log(
        "delegation_validated",
        ref,
        agent_id=agent_id,
        effective_scopes=sorted(effective_scopes),
    )

    # 3. Resolve available tools
    available_tools = resolve_available_tools(effective_scopes)

    # 4. Simulate agent planning
    planned_tools = plan_tools(request.user_message, available_tools)
    audit_log(
        "agent_planned",
        ref,
        agent_id=agent_id,
        planned_tools=[t["tool"] for t in planned_tools],
    )

    # 5. Depth-4 delegation: orchestrator (d2) → worker (d3) → tool (d4)
    gateway = get_iam_gateway()

    # Map tool names to required scopes
    tool_scope_map = {v["tool"]: k for k, v in TOOL_REGISTRY.items()}

    # Group planned tools by worker
    worker_tools: dict[str, list[dict]] = {}
    for tool_info in planned_tools:
        worker_name = find_worker_for_tool(tool_info["tool"])
        if worker_name:
            worker_tools.setdefault(worker_name, []).append(tool_info)

    results = []
    delegation_chain = []
    execution_log = []

    # Add orchestrator (d2) to the chain
    delegation_chain.append({
        "depth": 2,
        "label": "orchestrator",
        "agent_id": agent_id,
        "scopes": sorted(effective_scopes),
        "token": token.token,
    })
    execution_log.append({
        "step": "d2:orchestrator",
        "status": "validated",
        "agent_id": agent_id,
        "scopes": sorted(effective_scopes),
        "planned_tools": [t["tool"] for t in planned_tools],
    })

    async with httpx.AsyncClient() as client:
        for worker_name, tools in worker_tools.items():
            worker_agent_id = WORKER_AGENT_IDS.get(worker_name)
            if not worker_agent_id:
                for tool_info in tools:
                    results.append({
                        "tool": tool_info["tool"],
                        "status": "error",
                        "error": f"Worker '{worker_name}' not registered",
                    })
                continue

            # d2 → d3: Delegate from orchestrator to worker sub-agent
            worker_scopes = [
                s for s in WORKER_REGISTRY[worker_name]["scopes"]
                if s in effective_scopes
            ]

            if not worker_scopes:
                for tool_info in tools:
                    results.append({
                        "tool": tool_info["tool"],
                        "status": "denied",
                        "error": f"No scopes available for worker '{worker_name}'",
                    })
                continue

            worker_task = TaskContext(
                id=token.task.id,
                purpose=f"Worker dispatch: {worker_name}",
                metadata={"delegation_ref": ref, "worker": worker_name},
            )
            worker_scope = DelegationScope(
                scopes=worker_scopes,
                expires_in_seconds=600,
            )

            worker_result = await gateway.delegate_to_agent(
                principal_token=token.token,
                agent_id=worker_agent_id,
                task=worker_task,
                scope=worker_scope,
            )

            if worker_result.is_err:
                execution_log.append({
                    "step": f"d3:{worker_name}",
                    "status": "delegation_failed",
                    "error": worker_result.error.message,
                })
                for tool_info in tools:
                    results.append({
                        "tool": tool_info["tool"],
                        "status": "delegation_failed",
                        "error": f"d2→d3 delegation failed: {worker_result.error.message}",
                    })
                continue

            worker_token = worker_result.value
            worker_chain_depth = len(worker_token.chain.links)
            execution_log.append({
                "step": f"d3:{worker_name}",
                "status": "delegated",
                "agent_id": worker_agent_id,
                "scopes": worker_scopes,
                "tools": [t["tool"] for t in tools],
            })

            audit_log(
                "worker_delegation_created",
                ref,
                worker=worker_name,
                worker_agent_id=worker_agent_id,
                scopes=worker_scopes,
                chain_depth=worker_chain_depth,
            )

            # Add worker (d3) to the chain
            delegation_chain.append({
                "depth": 3,
                "label": worker_name,
                "agent_id": worker_agent_id,
                "scopes": worker_scopes,
                "token": worker_token.token,
            })

            # d3 → d4: For each tool in this worker, create tool-level delegation
            for tool_info in tools:
                tool_name = tool_info["tool"]
                tool_input = request.tool_inputs.get(tool_name, {})
                required_scope = tool_scope_map.get(tool_name, "")

                sub_task = TaskContext(
                    id=token.task.id,
                    purpose=f"Tool call: {tool_name}",
                    metadata={
                        "delegation_ref": ref,
                        "tool": tool_name,
                        "worker": worker_name,
                    },
                )
                sub_scope = DelegationScope(
                    scopes=[required_scope],
                    expires_in_seconds=300,
                )

                sub_result = await gateway.delegate_to_agent(
                    principal_token=worker_token.token,
                    agent_id=worker_agent_id,
                    task=sub_task,
                    scope=sub_scope,
                )

                if sub_result.is_err:
                    execution_log.append({
                        "step": f"d4:{tool_name}",
                        "status": "delegation_failed",
                        "worker": worker_name,
                        "error": sub_result.error.message,
                    })
                    results.append({
                        "tool": tool_name,
                        "status": "delegation_failed",
                        "error": f"d3→d4 delegation failed: {sub_result.error.message}",
                    })
                    continue

                sub_token = sub_result.value
                chain_depth = len(sub_token.chain.links)

                audit_log(
                    "tool_delegation_created",
                    ref,
                    tool=tool_name,
                    scope=required_scope,
                    worker=worker_name,
                    chain_depth=chain_depth,
                )

                # Add tool (d4) to the chain
                delegation_chain.append({
                    "depth": 4,
                    "label": tool_name,
                    "scope": required_scope,
                    "worker": worker_name,
                    "token": sub_token.token,
                })

                # Call connector with the d4 token
                try:
                    resp = await client.post(
                        f"{CONNECTORS_URL}{tool_info['endpoint']}",
                        json={"input": tool_input},
                        headers={"X-Delegation-Token": sub_token.token},
                        timeout=10.0,
                    )
                    if resp.status_code == 200:
                        result_data = resp.json()
                        result_data["status"] = "executed"
                        results.append(result_data)
                        execution_log.append({
                            "step": f"d4:{tool_name}",
                            "status": "executed",
                            "scope": required_scope,
                            "worker": worker_name,
                        })
                    else:
                        error_msg = resp.json().get("detail", f"HTTP {resp.status_code}")
                        results.append({
                            "tool": tool_name,
                            "status": "denied",
                            "error": error_msg,
                            "status_code": resp.status_code,
                        })
                        execution_log.append({
                            "step": f"d4:{tool_name}",
                            "status": "denied",
                            "scope": required_scope,
                            "worker": worker_name,
                            "error": error_msg,
                        })
                except httpx.RequestError as e:
                    results.append({
                        "tool": tool_name,
                        "status": "error",
                        "error": f"Connection error: {e}",
                    })

    return {
        "agent_id": agent_id,
        "user_message": request.user_message,
        "effective_scopes": sorted(effective_scopes),
        "available_tools": [t["tool"] for t in available_tools],
        "planned_tools": [t["tool"] for t in planned_tools],
        "delegation_chain": delegation_chain,
        "tool_results": results,
        "execution_log": execution_log,
        "delegation_ref": ref,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "aip_backend", "port": 8001}


if __name__ == "__main__":
    import logging
    import uvicorn

    class HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(HealthFilter())

    uvicorn.run(app, host="0.0.0.0", port=8001)
