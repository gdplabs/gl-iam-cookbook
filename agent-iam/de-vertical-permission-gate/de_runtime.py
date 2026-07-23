"""The DE runtime -- what a Digital Employee does before it touches a tool.

Responsibilities, in order:

1. Read what the human has actually granted this agent (``PermissionStore``).
2. Mint a short-lived principal JWT for the human (the DE runs on a cron, so
   there is no live user session to borrow a token from).
3. Exchange it for a delegation token scoped to *this task*, carrying at most
   what the human granted. GL-IAM refuses to mint anything wider.
4. Install that token as the run's delegation context and execute the plan.
   Every gated tool checks the token before doing any work.

Nothing here requires a database. ``delegate_to_agent`` is handed the
``AgentIdentity`` directly -- the same hook AIP uses to keep its own agent
catalog instead of dual-writing into GL-IAM's ``agents`` table -- and token
validation is stateless JWT verification.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from gl_iam import (
    AgentIdentity,
    AgentStatus,
    AgentType,
    AuditEvent,
    DelegationScope,
    IAMGateway,
    TaskContext,
)
from gl_iam.core.gateway import AuditConfig
from gl_iam.providers.native import NativeAgentProvider, NativeConfig

from scope_gate import (
    DelegationContext,
    get_required_scope,
    reset_delegation_context,
    set_delegation_context,
)
from tools import (
    DE_TOOLS,
    google_docs_create_document_tool,
    meemo_get_meeting_summary_tool,
    send_email_tool,
)

USER_ID = "user:sam"
USER_EMAIL = "sam@example.com"
ORG_ID = "org:acme"
AGENT_ID = "agent:pamela-lite"

# Scopes the DE can ever hold, derived from the tools attached to it. This
# mirrors AIP's delegation_token_auth.py, which builds allowed_scopes from an
# agent's attached tool names plus its sub-agent names.
TOOL_SCOPES: list[str] = [s for t in DE_TOOLS if (s := get_required_scope(t)) is not None]

SCOPE_LABELS = {
    "meemo:read": "Read meeting recordings and summaries (Meemo)",
    "google_docs:write": "Create and edit Google Docs",
    "gmail:send": "Send email on your behalf",
}


# ---------------------------------------------------------------------------
# What the human has granted
# ---------------------------------------------------------------------------
@dataclass
class PermissionStore:
    """The human's standing consent for this agent.

    In production this is a table keyed by (user, agent, scope) and is edited
    from a settings screen or straight from chat -- the same shape as the
    permission prompt in a local coding agent. Here it is in-memory so the
    example runs with nothing but ``uv run main.py``.
    """

    granted: set[str] = field(default_factory=set)
    pending: set[str] = field(default_factory=set)

    def grant(self, scope: str) -> None:
        """Allow a scope and clear any pending request for it."""
        self.granted.add(scope)
        self.pending.discard(scope)

    def revoke(self, scope: str) -> None:
        """Withdraw a scope. Takes effect on the next delegation."""
        self.granted.discard(scope)

    def request(self, scopes: set[str]) -> None:
        """File access requests for scopes the agent asked for but lacks."""
        self.pending.update(scopes - self.granted)

    def snapshot(self) -> list[dict[str, Any]]:
        """Render every known scope with its current state, for the console."""
        return [
            {
                "scope": scope,
                "label": SCOPE_LABELS.get(scope, scope),
                "granted": scope in self.granted,
                "pending": scope in self.pending,
            }
            for scope in TOOL_SCOPES
        ]


# ---------------------------------------------------------------------------
# Process-wide demo state
# ---------------------------------------------------------------------------
permissions = PermissionStore(granted={"meemo:read"})
audit_log: list[dict[str, Any]] = []
agent_status: AgentStatus = AgentStatus.ACTIVE

_gateway: IAMGateway | None = None


def _record_audit(event: AuditEvent) -> None:
    """Buffer a GL-IAM audit event so the console can show it live."""
    audit_log.append(
        {
            "event_type": str(event.event_type),
            "severity": str(event.severity),
            "resource_id": event.resource_id,
            "message": event.message,
            "error_code": str(event.error_code) if event.error_code else None,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )


def build_gateway() -> IAMGateway:
    """Build the IAM gateway once, and reuse it."""
    global _gateway
    if _gateway is not None:
        return _gateway

    secret_key = os.getenv("SECRET_KEY", "demo-secret-key-min-32-characters-long!!")
    provider = NativeAgentProvider(
        NativeConfig(
            # No connection is opened: every call this example makes is either
            # stateless JWT work or is handed the AgentIdentity directly.
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/gliam",
            ),
            secret_key=secret_key,
            default_org_id=ORG_ID,
            enable_third_party_provider=False,
        )
    )
    _gateway = IAMGateway(
        agent_provider=provider,
        secret_key=secret_key,
        audit_config=AuditConfig(callback=_record_audit),
    )
    return _gateway


def current_agent() -> AgentIdentity:
    """The DE's identity, with its scope ceiling and current lifecycle status."""
    return AgentIdentity(
        id=AGENT_ID,
        name="Pamela Lite (MoM Digital Employee)",
        agent_type=AgentType.WORKER,
        model="gpt-5.2",
        owner_user_id=USER_ID,
        operator_org_id=ORG_ID,
        status=agent_status,
        max_delegation_depth=3,
        allowed_scopes=TOOL_SCOPES,
    )


def set_agent_status(status: AgentStatus) -> None:
    """Flip the agent's lifecycle status (kill switch demo)."""
    global agent_status
    agent_status = status


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
async def run_de_task(task_id: str, escalate: bool = False) -> dict[str, Any]:
    """Run the DE's 'write up the meeting minutes' job under delegation.

    Args:
        task_id: Identifier binding the delegation chain to this task.
        escalate: When True, ask for every tool scope regardless of what the
            human granted. GL-IAM refuses to mint the token -- this is the
            enforcement that happens *before* any tool is reached.

    Returns:
        A timeline of what happened, for the console.
    """
    gateway = build_gateway()

    requested = set(TOOL_SCOPES) if escalate else set(permissions.granted)
    task = TaskContext(
        id=task_id,
        purpose="Write up the minutes for the GL IAM weekly sync and email them",
        metadata={"digital_employee": "pamela-lite"},
    )

    principal = gateway.mint_principal_jwt(
        sub=USER_ID,
        ttl_seconds=300,
        extra_claims={"email": USER_EMAIL},
    )
    if principal.is_err:
        return {"minted": False, "error": principal.error.message, "steps": []}

    delegation = await gateway.delegate_to_agent(
        principal_token=principal.value,
        agent_id=AGENT_ID,
        task=task,
        # What this run asks to hold...
        scope=DelegationScope(scopes=sorted(requested), expires_in_seconds=300),
        # ...capped by what the human actually granted.
        principal_scope=DelegationScope(scopes=sorted(permissions.granted)),
        agent=current_agent(),
    )

    if delegation.is_err:
        return {
            "minted": False,
            "error_code": str(delegation.error.code),
            "error": delegation.error.message,
            "steps": [],
            "granted_scopes": sorted(permissions.granted),
            "requested_scopes": sorted(requested),
        }

    context = DelegationContext(token=delegation.value)
    ctx_token = set_delegation_context(context)
    try:
        steps = await _execute_plan(context)
    finally:
        reset_delegation_context(ctx_token)

    permissions.request(context.requested_scopes)

    return {
        "minted": True,
        "task_id": task_id,
        "root_principal": delegation.value.chain.root_principal.principal_id,
        "chain": [
            {"principal_id": link.principal_id, "type": str(link.principal_type), "scopes": link.scope.scopes}
            for link in delegation.value.chain.links
        ],
        "effective_scopes": context.effective_scopes,
        "expires_at": delegation.value.expires_at.isoformat(),
        "steps": steps,
        "decisions": [d.to_dict() for d in context.decisions],
        "granted_scopes": sorted(permissions.granted),
        "requested_scopes": sorted(requested),
    }


async def _execute_plan(context: DelegationContext) -> list[dict[str, Any]]:
    """The DE's fixed plan: read the meeting, write the doc, email it.

    The plan is deterministic rather than LLM-driven so the demo shows the
    authorization behaviour and nothing else. Each step calls a real gated
    tool, so a denial here is a real denial.
    """
    steps: list[dict[str, Any]] = []

    async def step(label: str, tool: Any, payload: dict[str, Any]) -> dict[str, Any]:
        """Run one gated tool and pair its output with the gate's decision."""
        result = await tool.ainvoke(payload)
        decision = context.decisions[-1] if context.decisions else None
        steps.append(
            {
                "step": label,
                "tool": tool.name,
                "result": result,
                "decision": decision.to_dict() if decision else None,
            }
        )
        return result

    summary = await step(
        "Read meeting summary",
        meemo_get_meeting_summary_tool,
        {"meeting_id": "meemo-2026-07-21-acme-iam"},
    )

    doc = await step(
        "Create Google Doc",
        google_docs_create_document_tool,
        {
            "title": "[MoM] GL IAM Weekly Sync",
            "body": summary.get("summary", "") if summary.get("status") == "ok" else "",
        },
    )

    await step(
        "Email the minutes",
        send_email_tool,
        {
            "recipients": ["nadia@example.com", "alex@example.com"],
            "subject": "[MoM] GL IAM Weekly Sync",
            "body": doc.get("url", "") if doc.get("status") == "ok" else "",
        },
    )

    return steps


__all__ = [
    "AGENT_ID",
    "SCOPE_LABELS",
    "TOOL_SCOPES",
    "USER_ID",
    "audit_log",
    "build_gateway",
    "current_agent",
    "permissions",
    "run_de_task",
    "set_agent_status",
]
