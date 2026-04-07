"""
Shared utilities for Agent IAM Dashboard backend services.

Provides:
- In-memory audit store for app-level events
- SDK audit events query (from PostgreSQL audit_events table)
- Common audit logging helpers
- CORS setup
"""

import json
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

# =============================================================================
# In-Memory Audit Store (app-level events)
# =============================================================================
AUDIT_STORE: list[dict] = []


SDK_AUDIT_STORE: list[dict] = []


def capture_sdk_event(event) -> None:
    """Callback for GL-IAM SDK audit events. Stores in SDK_AUDIT_STORE."""
    details = event.details if hasattr(event, "details") else {}
    entry = {
        "timestamp": event.timestamp.isoformat() if hasattr(event.timestamp, "isoformat") else str(event.timestamp),
        "source": "sdk",
        "service": "gl-iam",
        "event": event.event_type.value if hasattr(event.event_type, "value") else str(event.event_type),
        "severity": event.severity.value if hasattr(event.severity, "value") else str(event.severity),
        "user_id": event.user_id,
        "organization_id": event.organization_id,
        "resource_id": event.resource_id,
        "error_code": event.error_code,
        "message": event.message,
        "delegation_ref": details.get("delegation_ref", details.get("task_id", "")) if isinstance(details, dict) else "",
        "details": details if isinstance(details, dict) else {},
    }
    SDK_AUDIT_STORE.append(entry)


def audit_log(service: str, event: str, delegation_ref: str, **kwargs) -> dict:
    """Log a structured audit event and store in memory."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "app",
        "service": service,
        "event": event,
        "delegation_ref": delegation_ref,
        **kwargs,
    }
    AUDIT_STORE.append(entry)
    logger.info(json.dumps(entry))
    return entry


def get_sdk_audit_events_from_db(limit: int = 200) -> list[dict]:
    """Query GL-IAM SDK audit events from PostgreSQL gl_iam.audit_events table."""
    db_url = os.getenv("DATABASE_URL", "").replace("+asyncpg", "+psycopg2")
    if not db_url:
        return []
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            result = conn.execute(
                text("""
                    SELECT id, event_type, severity, timestamp, user_id,
                           organization_id, provider_type, resource_id,
                           details_json, error_code, message, trace_id, span_id
                    FROM gl_iam.audit_events
                    ORDER BY timestamp DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            )
            events = []
            for row in result:
                details = {}
                if row.details_json:
                    try:
                        details = json.loads(row.details_json)
                    except (json.JSONDecodeError, TypeError):
                        pass
                events.append({
                    "id": row.id,
                    "timestamp": row.timestamp.isoformat() if row.timestamp else "",
                    "source": "sdk",
                    "service": "gl-iam",
                    "event": row.event_type,
                    "severity": row.severity,
                    "user_id": row.user_id,
                    "organization_id": row.organization_id,
                    "resource_id": row.resource_id,
                    "error_code": row.error_code,
                    "message": row.message,
                    "trace_id": row.trace_id,
                    "delegation_ref": details.get("delegation_ref", details.get("task_id", "")),
                    "details": details,
                })
            return events
    except Exception as e:
        logger.warning(f"Failed to query SDK audit events: {e}")
        return []


def add_audit_routes(app: FastAPI):
    """Add /audit/events and /audit/sdk-events endpoints."""

    @app.get("/audit/events")
    async def get_app_audit_events(
        delegation_ref: str | None = None,
        service: str | None = None,
        event: str | None = None,
    ):
        """App-level audit events (in-memory)."""
        results = AUDIT_STORE
        if delegation_ref:
            results = [e for e in results if e.get("delegation_ref") == delegation_ref]
        if service:
            results = [e for e in results if e.get("service") == service]
        if event:
            results = [e for e in results if e.get("event") == event]
        return results

    @app.get("/audit/sdk-events")
    async def get_sdk_events(limit: int = 200):
        """GL-IAM SDK audit events — tries PostgreSQL first, falls back to in-memory."""
        db_events = get_sdk_audit_events_from_db(limit)
        if db_events:
            return db_events
        return SDK_AUDIT_STORE[-limit:]

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
