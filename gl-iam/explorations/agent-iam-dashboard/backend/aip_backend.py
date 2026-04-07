"""
AIP Backend — Service 2 (port 8001).

Extended from the E2E demo with:
- DE/AIP tool and worker registries
- Resource context forwarding to connectors
- Approval-required response handling
- CORS + audit endpoints
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

from gl_iam import DelegationScope, IAMGateway, TaskContext
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.core.types.delegation import DelegationToken
from gl_iam.fastapi import (
    get_current_agent,
    get_delegation_token,
    get_iam_gateway,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLAgentProvider, PostgreSQLConfig

from shared import add_audit_routes, add_cors, audit_log

load_dotenv()

logger = logging.getLogger("aip_backend")
logging.basicConfig(level=logging.INFO, format="%(message)s")

CONNECTORS_URL = os.getenv("CONNECTORS_URL", "http://localhost:8002")

# =============================================================================
# Tool Registry — maps scopes to available tools (extended with DE/AIP)
# =============================================================================
TOOL_REGISTRY: dict[str, dict] = {
    # GLChat tools
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
    # DE tools
    "meemo:write": {
        "tool": "meemo.create_mom",
        "description": "Create MoM on Meemo",
        "endpoint": "/tools/meemo.create_mom",
    },
    "meemo:read": {
        "tool": "meemo.read_mom",
        "description": "Read MoM from Meemo",
        "endpoint": "/tools/meemo.read_mom",
    },
    "gdoc:write": {
        "tool": "gdoc.create",
        "description": "Create a Google Doc",
        "endpoint": "/tools/gdoc.create",
    },
    "gdoc:read": {
        "tool": "gdoc.read",
        "description": "Read a Google Doc",
        "endpoint": "/tools/gdoc.read",
    },
    "gdoc:share": {
        "tool": "gdoc.share",
        "description": "Share a Google Doc",
        "endpoint": "/tools/gdoc.share",
    },
    "invoice:send": {
        "tool": "invoice.send",
        "description": "Send an invoice",
        "endpoint": "/tools/invoice.send",
    },
}

# =============================================================================
# Worker Registry — groups tools by worker sub-agent (extended)
# =============================================================================
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
    "meemo-worker": {
        "type": "worker",
        "scopes": ["meemo:read", "meemo:write"],
        "tools": ["meemo.create_mom", "meemo.read_mom"],
    },
    "gdoc-worker": {
        "type": "worker",
        "scopes": ["gdoc:read", "gdoc:write", "gdoc:share"],
        "tools": ["gdoc.create", "gdoc.read", "gdoc.share"],
    },
    "invoice-worker": {
        "type": "worker",
        "scopes": ["invoice:send", "gmail:send"],
        "tools": ["invoice.send", "gmail.send"],
    },
}

WORKER_AGENT_IDS: dict[str, str] = {}

KEYWORD_TO_TOOLS = {
    # GLChat
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
    # DE
    "mom": ["meemo.create_mom", "meemo.read_mom"],
    "minutes": ["meemo.create_mom", "meemo.read_mom"],
    "meemo": ["meemo.create_mom", "meemo.read_mom"],
    "create": ["meemo.create_mom", "gdoc.create"],
    "share": ["gdoc.share", "gmail.send"],
    "summarize": ["meemo.read_mom", "gdoc.read"],
    "summary": ["meemo.read_mom", "gdoc.read"],
    "access": ["meemo.read_mom", "gdoc.read"],
    "invoice": ["invoice.send"],
    # AIP
    "report": ["gdoc.read", "gdoc.create", "gdoc.write", "gmail.send"],
    "weekly": ["gdoc.read", "gdoc.create", "gmail.send"],
    "draft": ["gdoc.create", "gmail.send"],
    "send": ["gmail.send"],
}


def resolve_available_tools(effective_scopes: set[str]) -> list[dict]:
    available = []
    for scope, tool_info in TOOL_REGISTRY.items():
        if scope in effective_scopes:
            available.append(tool_info)
    return available


def get_delegation_ref(token: DelegationToken) -> str:
    return token.task.metadata.get("delegation_ref", token.task.id)


async def _ensure_worker_ids():
    if WORKER_AGENT_IDS:
        return
    gateway = get_iam_gateway()
    agents = await gateway.list_agents(owner_user_id=None)
    for agent in agents:
        if agent.name in WORKER_REGISTRY:
            WORKER_AGENT_IDS[agent.name] = agent.id
            logger.info(f"Found worker: {agent.name} -> {agent.id}")


def find_worker_for_tool(tool_name: str) -> str | None:
    for worker_name, worker_info in WORKER_REGISTRY.items():
        if tool_name in worker_info["tools"]:
            return worker_name
    return None


def plan_tools(
    user_message: str, available_tools: list[dict], effective_scopes: set[str],
) -> tuple[list[dict], list[dict]]:
    available_names = {t["tool"] for t in available_tools}
    planned_names: set[str] = set()
    desired_names: set[str] = set()

    for keyword, tool_names in KEYWORD_TO_TOOLS.items():
        if keyword in user_message.lower():
            for name in tool_names:
                desired_names.add(name)
                if name in available_names:
                    planned_names.add(name)

    if not desired_names:
        planned_names = available_names
        desired_names = {t["tool"] for t in TOOL_REGISTRY.values()}

    tool_to_scope = {v["tool"]: k for k, v in TOOL_REGISTRY.items()}
    blocked = [
        {"tool": name, "missing_scope": tool_to_scope.get(name, "unknown")}
        for name in sorted(desired_names - available_names)
    ]

    planned = [t for t in available_tools if t["tool"] in planned_names]
    return planned, blocked


# =============================================================================
# Application Setup
# =============================================================================
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
    title="AIP Backend - Agent IAM Dashboard",
    description="Agent execution with delegation validation and tool routing",
    lifespan=lifespan,
)
add_cors(app)
add_audit_routes(app)


class AgentRunRequest(BaseModel):
    user_message: str
    tool_inputs: dict[str, dict] = {}
    resource_context: dict = {}


# =============================================================================
# Main Endpoint
# =============================================================================
@app.post("/agents/{agent_id}/run")
async def run_agent(
    agent_id: str,
    request: AgentRunRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    await _ensure_worker_ids()

    if token.agent_id != agent_id:
        raise HTTPException(status_code=403, detail="Token agent_id mismatch")

    effective_scopes = token.chain.effective_scopes()
    audit_log(
        "aip_backend", "delegation_validated", ref,
        agent_id=agent_id, effective_scopes=sorted(effective_scopes),
    )

    available_tools = resolve_available_tools(effective_scopes)
    planned_tools, blocked_tools = plan_tools(
        request.user_message, available_tools, effective_scopes,
    )
    audit_log(
        "aip_backend", "agent_planned", ref,
        agent_id=agent_id,
        planned_tools=[t["tool"] for t in planned_tools],
        blocked_tools=[t["tool"] for t in blocked_tools],
    )

    gateway = get_iam_gateway()
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

    # d2: orchestrator
    delegation_chain.append({
        "depth": 2,
        "label": "orchestrator",
        "agent_id": agent_id,
        "scopes": sorted(effective_scopes),
        "token": token.token,
    })
    d2_parent_scopes = sorted(token.chain.links[0].scope.scopes) if token.chain.links else []
    execution_log.append({
        "step": "d2:orchestrator",
        "status": "validated",
        "agent_id": agent_id,
        "parent_scopes": d2_parent_scopes,
        "requested_scopes": sorted(effective_scopes),
        "scopes": sorted(effective_scopes),
        "rejected_scopes": sorted(s for s in d2_parent_scopes if s not in effective_scopes),
        "planned_tools": [t["tool"] for t in planned_tools],
        "blocked_tools": blocked_tools,
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

            # Forward user_role from parent token for credential routing checks
            parent_user_role = token.task.metadata.get("user_role", "")

            worker_task = TaskContext(
                id=token.task.id,
                purpose=f"Worker dispatch: {worker_name}",
                metadata={
                    "delegation_ref": ref,
                    "worker": worker_name,
                    "resource_context": request.resource_context,
                    "user_role": parent_user_role,
                },
            )
            worker_scope = DelegationScope(scopes=worker_scopes, expires_in_seconds=600)

            worker_result = await gateway.delegate_to_agent(
                principal_token=token.token,
                agent_id=worker_agent_id,
                task=worker_task,
                scope=worker_scope,
            )

            worker_ceiling = WORKER_REGISTRY[worker_name]["scopes"]

            if worker_result.is_err:
                execution_log.append({
                    "step": f"d3:{worker_name}",
                    "status": "delegation_failed",
                    "parent_scopes": sorted(effective_scopes),
                    "agent_ceiling": sorted(worker_ceiling),
                    "requested_scopes": sorted(worker_ceiling),
                    "scopes": worker_scopes,
                    "rejected_scopes": sorted(s for s in worker_ceiling if s not in worker_scopes),
                    "error": worker_result.error.message,
                })
                for tool_info in tools:
                    results.append({
                        "tool": tool_info["tool"],
                        "status": "delegation_failed",
                        "error": f"d2->d3 delegation failed: {worker_result.error.message}",
                    })
                continue

            worker_token = worker_result.value

            denied_at_worker = sorted(s for s in effective_scopes if s not in worker_scopes)
            execution_log.append({
                "step": f"d3:{worker_name}",
                "status": "delegated",
                "agent_id": worker_agent_id,
                "parent_scopes": sorted(effective_scopes),
                "agent_ceiling": sorted(worker_ceiling),
                "requested_scopes": sorted(worker_ceiling),
                "scopes": worker_scopes,
                "rejected_scopes": sorted(s for s in worker_ceiling if s not in worker_scopes),
                "denied_scopes": denied_at_worker,
                "tools": [t["tool"] for t in tools],
            })

            audit_log(
                "aip_backend", "worker_delegation_created", ref,
                worker=worker_name, worker_agent_id=worker_agent_id,
                scopes=worker_scopes, chain_depth=len(worker_token.chain.links),
            )

            delegation_chain.append({
                "depth": 3,
                "label": worker_name,
                "agent_id": worker_agent_id,
                "scopes": worker_scopes,
                "token": worker_token.token,
            })

            # d3 -> d4: Per-tool delegation
            for tool_info in tools:
                tool_name = tool_info["tool"]
                tool_input = request.tool_inputs.get(tool_name, {})
                required_scope = tool_scope_map.get(tool_name, "")

                # Merge resource_context (which includes _user_role) into tool input
                merged_input = {
                    **tool_input,
                    **request.resource_context,
                }

                sub_task = TaskContext(
                    id=token.task.id,
                    purpose=f"Tool call: {tool_name}",
                    metadata={
                        "delegation_ref": ref,
                        "tool": tool_name,
                        "worker": worker_name,
                        "resource_context": request.resource_context,
                        "user_role": parent_user_role,
                    },
                )
                sub_scope = DelegationScope(scopes=[required_scope], expires_in_seconds=300)

                sub_result = await gateway.delegate_to_agent(
                    principal_token=worker_token.token,
                    agent_id=worker_agent_id,
                    task=sub_task,
                    scope=sub_scope,
                )

                if sub_result.is_err:
                    d4_parent = worker_scopes
                    execution_log.append({
                        "step": f"d4:{tool_name}",
                        "status": "delegation_failed",
                        "parent_scopes": sorted(d4_parent),
                        "agent_ceiling": sorted(worker_ceiling),
                        "requested_scopes": [required_scope],
                        "scope": required_scope,
                        "rejected_scopes": sorted(s for s in d4_parent if s != required_scope),
                        "worker": worker_name,
                        "error": sub_result.error.message,
                    })
                    results.append({
                        "tool": tool_name,
                        "status": "delegation_failed",
                        "error": f"d3->d4 delegation failed: {sub_result.error.message}",
                    })
                    continue

                sub_token = sub_result.value
                audit_log(
                    "aip_backend", "tool_delegation_created", ref,
                    tool=tool_name, scope=required_scope, worker=worker_name,
                    chain_depth=len(sub_token.chain.links),
                )

                delegation_chain.append({
                    "depth": 4,
                    "label": tool_name,
                    "scope": required_scope,
                    "worker": worker_name,
                    "token": sub_token.token,
                })

                # Call connector
                try:
                    resp = await client.post(
                        f"{CONNECTORS_URL}{tool_info['endpoint']}",
                        json={"input": merged_input},
                        headers={"X-Delegation-Token": sub_token.token},
                        timeout=10.0,
                    )
                    d4_parent = worker_scopes
                    d4_rejected = sorted(s for s in d4_parent if s != required_scope)

                    if resp.status_code == 200:
                        result_data = resp.json()
                        result_data["status"] = result_data.get("status", "executed")
                        results.append(result_data)
                        execution_log.append({
                            "step": f"d4:{tool_name}",
                            "status": result_data.get("status", "executed"),
                            "parent_scopes": sorted(d4_parent),
                            "agent_ceiling": sorted(worker_ceiling),
                            "requested_scopes": [required_scope],
                            "scope": required_scope,
                            "rejected_scopes": d4_rejected,
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
                            "parent_scopes": sorted(d4_parent),
                            "agent_ceiling": sorted(worker_ceiling),
                            "requested_scopes": [required_scope],
                            "scope": required_scope,
                            "rejected_scopes": d4_rejected,
                            "worker": worker_name,
                            "error": error_msg,
                        })
                except httpx.RequestError as e:
                    results.append({
                        "tool": tool_name,
                        "status": "error",
                        "error": f"Connection error: {e}",
                    })

    # Determine overall outcome
    statuses = [r.get("status") for r in results]
    if all(s == "executed" for s in statuses):
        outcome = "success"
    elif all(s in ("denied", "delegation_failed", "error") for s in statuses):
        outcome = "rejected"
    elif any(s == "executed" for s in statuses):
        outcome = "partial_success"
    else:
        outcome = "rejected"

    # Check for warnings in results
    warnings = [r.get("warnings", []) for r in results if r.get("warnings")]
    if warnings and outcome == "success":
        outcome = "success_with_warning"

    return {
        "agent_id": agent_id,
        "user_message": request.user_message,
        "effective_scopes": sorted(effective_scopes),
        "available_tools": [t["tool"] for t in available_tools],
        "planned_tools": [t["tool"] for t in planned_tools],
        "blocked_tools": blocked_tools,
        "delegation_chain": delegation_chain,
        "tool_results": results,
        "execution_log": execution_log,
        "delegation_ref": ref,
        "outcome": outcome,
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "aip_backend", "port": 8001}


if __name__ == "__main__":
    import uvicorn

    class HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(HealthFilter())
    uvicorn.run(app, host="0.0.0.0", port=8001)
