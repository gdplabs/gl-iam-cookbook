"""
Shared utilities for Agent IAM Dashboard backend services.

Provides:
- In-memory audit store with REST endpoints
- Common audit logging helpers
- CORS setup
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

# =============================================================================
# In-Memory Audit Store
# =============================================================================
AUDIT_STORE: list[dict] = []


def audit_log(service: str, event: str, delegation_ref: str, **kwargs) -> dict:
    """Log a structured audit event and store in memory."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": service,
        "event": event,
        "delegation_ref": delegation_ref,
        **kwargs,
    }
    AUDIT_STORE.append(entry)
    logger.info(json.dumps(entry))
    return entry


def add_audit_routes(app: FastAPI):
    """Add /audit/events endpoints to a FastAPI app."""

    @app.get("/audit/events")
    async def get_audit_events(
        delegation_ref: str | None = None,
        service: str | None = None,
        event: str | None = None,
    ):
        results = AUDIT_STORE
        if delegation_ref:
            results = [e for e in results if e.get("delegation_ref") == delegation_ref]
        if service:
            results = [e for e in results if e.get("service") == service]
        if event:
            results = [e for e in results if e.get("event") == event]
        return results

    @app.delete("/audit/events")
    async def clear_audit_events():
        AUDIT_STORE.clear()
        return {"status": "cleared"}


def add_cors(app: FastAPI):
    """Add CORS middleware allowing dashboard frontend."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
