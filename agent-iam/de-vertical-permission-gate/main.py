"""DE Vertical Permission Gate -- GL-IAM scope enforcement inside a Digital Employee.

Demonstrates that a DE vertical can enforce "tool X requires scope Y" today,
using GL-IAM delegation tokens, without any change to AIP or DE Core.

Run it:

    uv run main.py        # then open http://localhost:8000

No database and no Docker required.
"""

from __future__ import annotations

import itertools
import os
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from gl_iam import AgentStatus
from pydantic import BaseModel

from de_runtime import (
    AGENT_ID,
    TOOL_SCOPES,
    USER_EMAIL,
    audit_log,
    current_agent,
    permissions,
    run_de_task,
    set_agent_status,
)
from scope_gate import get_required_scope
from tools import DE_TOOLS

load_dotenv()

STATIC_DIR = Path(__file__).parent / "static"
_task_counter = itertools.count(1)
_last_run: dict[str, Any] = {}

app = FastAPI(
    title="DE Vertical Permission Gate",
    description="GL-IAM agent scope enforcement from the Digital Employee layer",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ScopeRequest(BaseModel):
    """Request body carrying a single scope."""

    scope: str


class RunRequest(BaseModel):
    """Request body for a DE run."""

    escalate: bool = False


@app.get("/")
async def console() -> FileResponse:
    """Serve the permission console."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@app.get("/api/state")
async def state() -> dict[str, Any]:
    """Everything the console renders: agent, tools, grants, audit, last run."""
    agent = current_agent()
    return {
        "user": {"id": agent.owner_user_id, "email": USER_EMAIL},
        "agent": {
            "id": agent.id,
            "name": agent.name,
            "status": agent.status.value,
            "allowed_scopes": agent.allowed_scopes,
            "max_delegation_depth": agent.max_delegation_depth,
        },
        "tools": [
            {
                "name": tool.name,
                "description": tool.description,
                "required_scope": get_required_scope(tool),
                "granted": get_required_scope(tool) in permissions.granted,
            }
            for tool in DE_TOOLS
        ],
        "permissions": permissions.snapshot(),
        "audit": audit_log[-40:],
        "last_run": _last_run,
    }


@app.post("/api/permissions/grant")
async def grant(request: ScopeRequest) -> dict[str, Any]:
    """Grant a scope to the agent."""
    if request.scope not in TOOL_SCOPES:
        raise HTTPException(status_code=400, detail=f"Unknown scope '{request.scope}'.")
    permissions.grant(request.scope)
    return {"granted": sorted(permissions.granted)}


@app.post("/api/permissions/revoke")
async def revoke(request: ScopeRequest) -> dict[str, Any]:
    """Revoke a scope. The next delegation cannot carry it."""
    permissions.revoke(request.scope)
    return {"granted": sorted(permissions.granted)}


@app.post("/api/agent/status")
async def agent_kill_switch(active: bool = True) -> dict[str, str]:
    """Flip the agent between ACTIVE and REVOKED (kill switch)."""
    set_agent_status(AgentStatus.ACTIVE if active else AgentStatus.REVOKED)
    return {"agent_id": AGENT_ID, "status": current_agent().status.value}


@app.post("/api/run")
async def run(request: RunRequest) -> dict[str, Any]:
    """Run the DE's minutes job under a fresh delegation token."""
    global _last_run
    task_id = f"mom-{next(_task_counter):04d}"
    _last_run = await run_de_task(task_id=task_id, escalate=request.escalate)
    return _last_run


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
