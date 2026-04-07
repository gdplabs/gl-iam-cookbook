"""
GL Connectors — Service 3 (port 8002).

Extended from the E2E demo with:
- DE tools: meemo.create_mom, meemo.read_mom, gdoc.create, gdoc.read, gdoc.share
- AIP tools: uses gdoc.read/create + gmail.send
- Feature-level tool: invoice.send
- Resource-level decisions using mock_data
- Structured outcomes: success, partial_success, rejected, approval_required
- CORS + audit endpoints
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
from gl_iam import ConsoleAuditHandler
from gl_iam.providers.postgresql import PostgreSQLAgentProvider, PostgreSQLConfig, DatabaseAuditHandler

from mock_data import (
    CALENDARS,
    DIRECTORY,
    INVOICES,
    MEEMO_ACCOUNTS,
    MOMS,
    TENANTS,
    USERS,
    WEEKLY_REPORTS,
)
from shared import add_audit_routes, add_cors, audit_log

load_dotenv()

logger = logging.getLogger("connectors")
logging.basicConfig(level=logging.INFO, format="%(message)s")


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
    from gl_iam import CallbackAuditHandler
    from shared import make_sdk_event_capturer
    gateway._audit_handlers = [ConsoleAuditHandler(logger_name="gl_iam.audit"), CallbackAuditHandler(make_sdk_event_capturer("connectors"))]
    set_iam_gateway(gateway)
    yield


app = FastAPI(
    title="GL Connectors - Agent IAM Dashboard",
    description="Tool execution with per-scope enforcement and resource-level decisions",
    lifespan=lifespan,
)
add_cors(app)
add_audit_routes(app)


class ToolRequest(BaseModel):
    input: dict = {}


def get_delegation_ref(token: DelegationToken) -> str:
    return token.task.metadata.get("delegation_ref", token.task.id)


def get_resource_context(token: DelegationToken) -> dict:
    """Extract resource_context from delegation token metadata."""
    return token.task.metadata.get("resource_context", {})


def check_user_oauth_required(request_input: dict, tool_name: str) -> str | None:
    """Check if this tool requires User OAuth but the user is a guest (no OAuth).

    Returns an error message if rejected, None if OK.

    Credential routing rule: tools with access_type="user" require User OAuth.
    Guest users (role=viewer) have no User OAuth token,
    so their personal resource access (own calendar, own docs) is rejected.
    """
    access_type = request_input.get("access_type", "user")
    user_role = request_input.get("_user_role", "")

    # If access_type is "agent", the agent's own OAuth is used — always OK
    if access_type == "agent":
        return None

    # If access_type is "user", check if this is a guest/viewer user
    # Guest users have no User OAuth token — they can't access personal resources
    if user_role == "viewer":
        return (
            f"This action requires your personal OAuth credentials to access your own resources, "
            f"but you are not logged in. Please log in to use {tool_name}."
        )

    return None


# =============================================================================
# GLChat Tools (existing)
# =============================================================================
@app.post("/tools/calendar.list_events")
async def calendar_list_events(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("calendar:read")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    target = request.input.get("target_calendar", "onlee@gdplabs.id")

    # GL Connector is a transport layer — it calls the 3P API and returns the result.
    # Policy enforcement (resource constraints) is handled at the agent/worker level.
    # The connector only surfaces 3P API errors.
    audit_log("connectors", "tool_call_allowed", ref, tool="calendar.list_events", agent_id=agent.id)
    events = CALENDARS.get(target, [
        {"id": "evt-1", "title": "Sprint Planning", "time": "2026-04-07T09:00:00Z"},
        {"id": "evt-2", "title": "Design Review", "time": "2026-04-07T14:00:00Z"},
        {"id": "evt-3", "title": "1:1 with Manager", "time": "2026-04-08T10:00:00Z"},
    ])

    return {"tool": "calendar.list_events", "status": "executed", "result": events}


@app.post("/tools/calendar.create_event")
async def calendar_create_event(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("calendar:write")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)

    # GL Connector is a transport layer — policy enforcement is at the agent/worker level.
    audit_log("connectors", "tool_call_allowed", ref, tool="calendar.create_event", agent_id=agent.id)

    title = request.input.get("title", "New Meeting")
    time = request.input.get("time", "2026-04-11T15:00:00Z")
    return {
        "tool": "calendar.create_event",
        "status": "executed",
        "result": {
            "id": f"evt-{uuid.uuid4().hex[:6]}",
            "title": title,
            "time": time,
            "status": "created",
        },
    }


@app.post("/tools/slack.post_message")
async def slack_post_message(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("slack:post")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    audit_log("connectors", "tool_call_allowed", ref, tool="slack.post_message", agent_id=agent.id)

    channel = request.input.get("channel", "#general")
    text = request.input.get("text", "Hello from agent!")
    return {
        "tool": "slack.post_message",
        "status": "executed",
        "result": {"channel": channel, "text": text, "ts": "1710000000.000001", "status": "sent"},
    }


@app.post("/tools/notion.get_page")
async def notion_get_page(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("notion:read")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    audit_log("connectors", "tool_call_allowed", ref, tool="notion.get_page", agent_id=agent.id)

    page_id = request.input.get("page_id", "page-abc-123")
    return {
        "tool": "notion.get_page",
        "status": "executed",
        "result": {"id": page_id, "title": "Project Roadmap", "content": "Q1 goals: ship delegation SDK..."},
    }


@app.post("/tools/gmail.send")
async def gmail_send(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("gmail:send")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    to = request.input.get("to", "")
    report_email = request.input.get("report_email", "")

    # Check if recipient email is active (UC-AIP-02.2)
    target_email = to or report_email
    if target_email:
        report = WEEKLY_REPORTS.get(target_email)
        if report and not report.get("email_active", True):
            audit_log("connectors", "tool_call_warning", ref,
                      tool="gmail.send", warning="email_bounced", to=target_email)
            return {
                "tool": "gmail.send",
                "status": "executed",
                "result": {"to": target_email, "status": "sent"},
                "warnings": [f"Email to {target_email} may bounce - account may be inactive"],
            }

    audit_log("connectors", "tool_call_allowed", ref, tool="gmail.send", agent_id=agent.id)
    return {
        "tool": "gmail.send",
        "status": "executed",
        "result": {"to": to, "status": "sent"},
    }


# =============================================================================
# DE Tools (new)
# =============================================================================
@app.post("/tools/meemo.create_mom")
async def meemo_create_mom(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("meemo:write")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    meeting_id = request.input.get("meeting_id", "meet-001")
    organiser_email = request.input.get("organiser_email", "")

    # Check if organiser has a Meemo account (UC-DE-01.1 vs UC-DE-01.2)
    if organiser_email and organiser_email not in MEEMO_ACCOUNTS:
        audit_log("connectors", "tool_call_partial", ref,
                  tool="meemo.create_mom", reason="meemo_account_not_found",
                  organiser=organiser_email)
        return {
            "tool": "meemo.create_mom",
            "status": "partial_success",
            "result": {
                "meeting_id": meeting_id,
                "meemo_status": "failed",
                "reason": f"Meemo account for {organiser_email} does not exist",
            },
            "warnings": [f"Meemo account not found for {organiser_email}"],
        }

    audit_log("connectors", "tool_call_allowed", ref,
              tool="meemo.create_mom", agent_id=agent.id, meeting_id=meeting_id)
    return {
        "tool": "meemo.create_mom",
        "status": "executed",
        "result": {
            "id": f"mom-{uuid.uuid4().hex[:6]}",
            "meeting_id": meeting_id,
            "status": "created",
        },
    }


@app.post("/tools/meemo.read_mom")
async def meemo_read_mom(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("meemo:read")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    mom_id = request.input.get("mom_id", "mom-001")
    requester_email = request.input.get("requester_email", "")

    mom = MOMS.get(mom_id)
    if not mom:
        raise HTTPException(status_code=404, detail=f"MoM {mom_id} not found")

    # Check draft status (UC-DE-03.3)
    if mom.get("status") == "draft":
        audit_log("connectors", "tool_call_denied", ref,
                  tool="meemo.read_mom", reason="draft_not_shared")
        raise HTTPException(
            status_code=403,
            detail="MoM is still in draft status and has not been shared yet",
        )

    # Check sensitive field request (UC-DE-03.4)
    if request.input.get("request_type") == "attendee_emails":
        audit_log("connectors", "tool_call_denied", ref,
                  tool="meemo.read_mom", reason="sensitive_data")
        raise HTTPException(
            status_code=403,
            detail="Email addresses are sensitive data and cannot be exposed",
        )

    # Check if requester is an attendee or super user
    if requester_email:
        user_info = USERS.get(requester_email, {})
        is_attendee = requester_email in mom.get("attendees", [])
        is_super_user = user_info.get("is_super_user", False)

        if not is_attendee and not is_super_user:
            # Check access_type from resource_context
            access_type = request.input.get("access_type", "user")
            if access_type != "agent":
                audit_log("connectors", "tool_call_denied", ref,
                          tool="meemo.read_mom", reason="not_attendee",
                          requester=requester_email)
                raise HTTPException(
                    status_code=403,
                    detail=f"User {requester_email} is not an attendee and does not have elevated access",
                )

        access_method = "super_user" if is_super_user and not is_attendee else "attendee"
        audit_log("connectors", "tool_call_allowed", ref,
                  tool="meemo.read_mom", agent_id=agent.id,
                  access_method=access_method)
    else:
        audit_log("connectors", "tool_call_allowed", ref,
                  tool="meemo.read_mom", agent_id=agent.id)

    return {
        "tool": "meemo.read_mom",
        "status": "executed",
        "result": {
            "id": mom_id,
            "title": mom["title"],
            "content": mom["content"],
            "status": mom["status"],
        },
    }


@app.post("/tools/gdoc.create")
async def gdoc_create(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("gdoc:write")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    audit_log("connectors", "tool_call_allowed", ref, tool="gdoc.create", agent_id=agent.id)

    title = request.input.get("title", "New Document")
    return {
        "tool": "gdoc.create",
        "status": "executed",
        "result": {
            "id": f"doc-{uuid.uuid4().hex[:6]}",
            "title": title,
            "status": "created",
        },
    }


@app.post("/tools/gdoc.read")
async def gdoc_read(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("gdoc:read")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    report_email = request.input.get("report_email", "")

    # For weekly report scenarios
    if report_email:
        report = WEEKLY_REPORTS.get(report_email)
        if report:
            content = report["content"] if report["filled"] else "[Report not yet filled by employee]"
            audit_log("connectors", "tool_call_allowed", ref,
                      tool="gdoc.read", agent_id=agent.id, report_filled=report["filled"])
            return {
                "tool": "gdoc.read",
                "status": "executed",
                "result": {
                    "report_email": report_email,
                    "filled": report["filled"],
                    "content": content,
                },
            }

    audit_log("connectors", "tool_call_allowed", ref, tool="gdoc.read", agent_id=agent.id)
    return {
        "tool": "gdoc.read",
        "status": "executed",
        "result": {"content": "Document content here..."},
    }


@app.post("/tools/gdoc.share")
async def gdoc_share(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("gdoc:share")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    mom_id = request.input.get("mom_id")
    mom_title = request.input.get("mom_title")
    requester_email = request.input.get("requester_email", "")
    recipients = request.input.get("recipients", [])

    # Check ambiguous title (UC-DE-02.3)
    if mom_title and not mom_id:
        matching = [m for m in MOMS.values() if m["title"] == mom_title]
        if len(matching) > 1:
            audit_log("connectors", "tool_call_approval_required", ref,
                      tool="gdoc.share", reason="ambiguous_title", title=mom_title)
            return {
                "tool": "gdoc.share",
                "status": "approval_required",
                "result": {
                    "reason": f"Multiple documents match title '{mom_title}'",
                    "matches": [
                        {"id": k, "title": v["title"], "meeting_id": v["meeting_id"]}
                        for k, v in MOMS.items() if v["title"] == mom_title
                    ],
                },
            }

    # Check resource ownership (UC-DE-02.2)
    if mom_id and requester_email:
        mom = MOMS.get(mom_id)
        if mom and mom.get("organiser") != requester_email:
            is_attendee = requester_email in mom.get("attendees", [])
            if is_attendee:
                audit_log("connectors", "tool_call_denied", ref,
                          tool="gdoc.share", reason="not_organiser",
                          requester=requester_email)
                raise HTTPException(
                    status_code=403,
                    detail=f"Only the meeting organiser can share the MoM. {requester_email} is an attendee, not the organiser.",
                )

    # Check external recipients (UC-DE-02.4)
    tenant_domain = "gdplabs.id"
    internal_recipients = []
    blocked_recipients = []
    for r in recipients:
        if r.endswith(f"@{tenant_domain}"):
            internal_recipients.append(r)
        else:
            blocked_recipients.append(r)

    if blocked_recipients:
        audit_log("connectors", "tool_call_partial", ref,
                  tool="gdoc.share", reason="external_recipients_blocked",
                  blocked=blocked_recipients)
        return {
            "tool": "gdoc.share",
            "status": "partial_success",
            "result": {
                "shared_with": internal_recipients,
                "blocked": blocked_recipients,
                "reason": "External recipients are not permitted",
            },
            "warnings": [f"Blocked external recipients: {', '.join(blocked_recipients)}"],
        }

    audit_log("connectors", "tool_call_allowed", ref, tool="gdoc.share", agent_id=agent.id)
    return {
        "tool": "gdoc.share",
        "status": "executed",
        "result": {
            "shared_with": recipients or ["all attendees"],
            "status": "shared",
        },
    }


@app.post("/tools/invoice.send")
async def invoice_send(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("invoice:send")),
    token: DelegationToken = Depends(get_delegation_token),
):
    ref = get_delegation_ref(token)
    invoice_id = request.input.get("invoice_id", "inv-aws-2026-04")

    invoice = INVOICES.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")

    audit_log("connectors", "tool_call_allowed", ref,
              tool="invoice.send", agent_id=agent.id, invoice_id=invoice_id)
    return {
        "tool": "invoice.send",
        "status": "executed",
        "result": {
            "invoice_id": invoice_id,
            "vendor": invoice["vendor"],
            "period": invoice["period"],
            "amount": invoice["amount"],
            "status": "sent",
        },
    }


# =============================================================================
# Directory Tool — name to email resolution (always Agent OAuth)
# =============================================================================
@app.post("/tools/directory.lookup")
async def directory_lookup(
    request: ToolRequest,
    agent: AgentIdentity = Depends(get_current_agent),
    _: None = Depends(require_agent_scope("directory:lookup")),
    token: DelegationToken = Depends(get_delegation_token),
):
    """Look up a person's email address by name. Always uses Agent OAuth
    (org directory is agent-level access, not user-level)."""
    ref = get_delegation_ref(token)
    name = request.input.get("name", "").strip().lower()

    if not name:
        raise HTTPException(status_code=400, detail="Name parameter is required")

    entry = DIRECTORY.get(name)
    if not entry:
        audit_log("connectors", "tool_call_allowed", ref,
                  tool="directory.lookup", agent_id=agent.id, name=name, found=False)
        return {
            "tool": "directory.lookup",
            "status": "executed",
            "result": {"found": False, "name": name, "message": f"No user found matching '{name}'"},
        }

    audit_log("connectors", "tool_call_allowed", ref,
              tool="directory.lookup", agent_id=agent.id, name=name,
              resolved_email=entry["email"])
    return {
        "tool": "directory.lookup",
        "status": "executed",
        "result": {
            "found": True,
            "name": name,
            "email": entry["email"],
            "display_name": entry["display_name"],
            "org": entry["org"],
            "role": entry["role"],
        },
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
