"""
GL Connectors — Service 3 (port 8002).

The innermost service in the delegation chain. Each tool endpoint enforces
its required scope via `require_agent_scope()`. The delegation token is
validated independently (defense in depth — stateless JWT verification).

Architecture role:
    GLChat BE (8000) → AIP Backend (8001) → **Connectors (8002)**

No outbound calls — this is the leaf service.
"""

import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import IAMGateway
from gl_iam.core.types.agent import AgentIdentity
from gl_iam.core.types.delegation import DelegationToken
from gl_iam.fastapi import (
    get_current_agent,
    get_delegation_token,
    require_agent_scope,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLAgentProvider, PostgreSQLConfig

load_dotenv()

# Structured JSON logger for audit correlation
logger = logging.getLogger("connectors")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def audit_log(event: str, delegation_ref: str, **kwargs):
    """Emit structured JSON audit log with delegation_ref for correlation."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "connectors",
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
    """Minimal agent-only gateway — validates delegation tokens via shared secret."""
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
    title="GL Connectors — Service 3",
    description="Tool execution with per-scope enforcement",
    lifespan=lifespan,
)


# ============================================================================
# Request/Response Models
# ============================================================================
class ToolRequest(BaseModel):
    """Request body for tool execution."""
    input: dict = {}


# ============================================================================
# Helper: extract delegation_ref from token's task context
# ============================================================================
def get_delegation_ref(token: DelegationToken) -> str:
    """Extract delegation_ref from task metadata, or use task.id as fallback."""
    return token.task.metadata.get("delegation_ref", token.task.id)


# ============================================================================
# Tool Endpoints — each enforces its required scope
# ============================================================================
@app.post("/tools/calendar.list_events")
async def calendar_list_events(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("calendar:read")),
    token: DelegationToken = Depends(get_delegation_token),
):
    """List calendar events. Requires scope: calendar:read."""
    ref = get_delegation_ref(token)
    audit_log("tool_call_allowed", ref, tool="calendar.list_events", agent_id=agent.id)

    return {
        "tool": "calendar.list_events",
        "result": [
            {"id": "evt-1", "title": "Sprint Planning", "time": "2026-03-10T09:00:00Z"},
            {"id": "evt-2", "title": "Design Review", "time": "2026-03-10T14:00:00Z"},
            {"id": "evt-3", "title": "1:1 with Manager", "time": "2026-03-11T10:00:00Z"},
        ],
    }


@app.post("/tools/calendar.create_event")
async def calendar_create_event(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("calendar:write")),
    token: DelegationToken = Depends(get_delegation_token),
):
    """Create a calendar event. Requires scope: calendar:write."""
    ref = get_delegation_ref(token)
    audit_log("tool_call_allowed", ref, tool="calendar.create_event", agent_id=agent.id)

    title = request.input.get("title", "New Meeting")
    time = request.input.get("time", "2026-03-12T15:00:00Z")
    return {
        "tool": "calendar.create_event",
        "result": {"id": f"evt-{uuid.uuid4().hex[:6]}", "title": title, "time": time, "status": "created"},
    }


@app.post("/tools/slack.post_message")
async def slack_post_message(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("slack:post")),
    token: DelegationToken = Depends(get_delegation_token),
):
    """Post a Slack message. Requires scope: slack:post."""
    ref = get_delegation_ref(token)
    audit_log("tool_call_allowed", ref, tool="slack.post_message", agent_id=agent.id)

    channel = request.input.get("channel", "#general")
    text = request.input.get("text", "Hello from agent!")
    return {
        "tool": "slack.post_message",
        "result": {"channel": channel, "text": text, "ts": "1710000000.000001", "status": "sent"},
    }


@app.post("/tools/notion.get_page")
async def notion_get_page(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("notion:read")),
    token: DelegationToken = Depends(get_delegation_token),
):
    """Get a Notion page. Requires scope: notion:read."""
    ref = get_delegation_ref(token)
    audit_log("tool_call_allowed", ref, tool="notion.get_page", agent_id=agent.id)

    page_id = request.input.get("page_id", "page-abc-123")
    return {
        "tool": "notion.get_page",
        "result": {"id": page_id, "title": "Project Roadmap", "content": "Q1 goals: ship delegation SDK..."},
    }


@app.post("/tools/gmail.send")
async def gmail_send(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("gmail:send")),
    token: DelegationToken = Depends(get_delegation_token),
):
    """Send an email via Gmail. Requires scope: gmail:send.

    This tool is intentionally NOT in the scheduling-agent's allowed_scopes,
    so it will always be denied — demonstrating scope ceiling enforcement.
    """
    ref = get_delegation_ref(token)
    audit_log("tool_call_allowed", ref, tool="gmail.send", agent_id=agent.id)

    return {
        "tool": "gmail.send",
        "result": {"to": request.input.get("to", ""), "status": "sent"},
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "connectors", "port": 8002}


if __name__ == "__main__":
    import uvicorn

    class HealthFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    logging.getLogger("uvicorn.access").addFilter(HealthFilter())

    uvicorn.run(app, host="0.0.0.0", port=8002)
