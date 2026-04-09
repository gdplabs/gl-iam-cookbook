# Audit Trail with FastAPI — Production Setup

A production-ready audit trail example demonstrating:

- **Multi-handler composition**: `ConsoleAuditHandler` + `DatabaseAuditHandler` via `CompositeAuditHandler`
- **Request context propagation**: Automatic `ip_address` and `user_agent` on every audit event
- **Diverse audit events**: Register, login, logout, password change, permission denied
- **Queryable audit log**: Filter by event_type, user_id, severity, and date range

## Prerequisites

- Python 3.11+
- [UV](https://docs.astral.sh/uv/) (package manager)
- PostgreSQL 15+ running locally

## Quick Start

```bash
# 1. Start PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=gliam \
  -p 5432:5432 postgres:15

# 2. Setup and run
./setup.sh
uv run main.py
```

The server starts at http://localhost:8000.

## Testing the API

### 1. Register a User

```bash
curl -s -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!", "display_name": "Alice"}'
```

Check terminal — you'll see audit events:
```
INFO:gl_iam.audit:audit_event: user_created
```

### 2. Login (Success)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN
```

Terminal shows: `audit_event: login_success`

### 3. Login (Failure — Wrong Password)

```bash
curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "wrong"}'
```

Terminal shows: `audit_event: login_error` with severity `warning`.

### 4. Access Admin (Permission Denied)

```bash
curl -s http://localhost:8000/admin \
  -H "Authorization: Bearer $TOKEN"
```

If user is not an admin, triggers `permission_denied` audit event.

### 5. Change Password

```bash
curl -s -X POST http://localhost:8000/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "SecurePass123!", "new_password": "NewSecure456!"}'
```

### 6. Query Audit Log (All Events)

```bash
curl -s "http://localhost:8000/audit-log" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 7. Query with Filters

```bash
# Only login failures
curl -s "http://localhost:8000/audit-log?event_type=login_error" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Only warnings and errors
curl -s "http://localhost:8000/audit-log?severity=warning" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Events for a specific user
curl -s "http://localhost:8000/audit-log?user_id=USER_ID_HERE" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Events in a date range
curl -s "http://localhost:8000/audit-log?from_date=2026-04-06T00:00:00&to_date=2026-04-07T00:00:00" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Pagination
curl -s "http://localhost:8000/audit-log?limit=10&offset=0" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 8. Logout

```bash
curl -s -X POST http://localhost:8000/logout \
  -H "Authorization: Bearer $TOKEN"
```

## Understanding the Code

### Handler Composition

The example uses `CompositeAuditHandler` to route events to both console and database simultaneously:

```python
console_handler = ConsoleAuditHandler()
db_handler = provider.create_audit_handler()  # DatabaseAuditHandler
composite = CompositeAuditHandler([console_handler, db_handler])
```

If one handler fails, the other still receives events — errors are isolated.

### Why Not `from_fullstack_provider()`?

`IAMGateway.from_fullstack_provider()` is a convenience factory, but it does **not** accept `audit_handlers`. To wire audit handlers, use the explicit constructor:

```python
gateway = IAMGateway(
    auth_provider=provider,
    user_store=provider,
    session_provider=provider,
    organization_provider=provider,
    audit_handlers=[composite],
)
```

### Request Context Middleware

The middleware calls `set_audit_context()` once per request. All audit events emitted during that request automatically inherit `ip_address` and `user_agent` — no need to pass them manually to gateway methods.

```python
@app.middleware("http")
async def audit_context_middleware(request, call_next):
    set_audit_context(
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent"),
    )
    try:
        return await call_next(request)
    finally:
        clear_audit_context()
```

### Querying Audit Events

The SDK persists events via `DatabaseAuditHandler` but does not provide a query API. The `/audit-log` endpoint shows how to query `AuditEventModel` directly with SQLAlchemy filters:

```python
from gl_iam.providers.postgresql import AuditEventModel

query = select(AuditEventModel).order_by(AuditEventModel.timestamp.desc())
if event_type:
    query = query.where(AuditEventModel.event_type == event_type)
```

### Database Configuration

Enable audit logging in `PostgreSQLConfig`:

```python
config = PostgreSQLConfig(
    database_url=DATABASE_URL,
    enable_audit_log=True,       # Required (default: False)
    # audit_batch_size=50,       # Events buffered before flush (default: 50)
    # audit_flush_interval_seconds=5.0,  # Max buffer time (default: 5s)
)
```

The `DatabaseAuditHandler` writes events asynchronously in batches for zero latency impact on auth operations.

## Advanced

### Adding OpenTelemetry

Add trace correlation with 3 lines (see commented section in `main.py`):

```python
from gl_iam import OpenTelemetryAuditHandler

otel_handler = OpenTelemetryAuditHandler()
composite = CompositeAuditHandler([console_handler, db_handler, otel_handler])
```

Install: `pip install opentelemetry-api opentelemetry-sdk`

### Custom Handlers

Build your own handler by subclassing `AuditHandler` (see commented `WebhookAuditHandler` in `main.py`).

### Production Considerations

- **Log retention**: Partition the `audit_events` table by month and drop old partitions
- **Log rotation**: Route `gl_iam.audit` logger to a file handler with rotation
- **SIEM integration**: Use a custom `AuditHandler` to forward events to Splunk, Datadog, etc.
- **Alerting**: Filter on `severity=error` or `severity=critical` in a custom handler

## Next Steps

- [Audit Trail GitBook tutorials](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/identity-and-access-management/audit-trail)
- [Agent Lifecycle example](../agent-lifecycle/) — agent audit events with ConsoleAuditHandler
- [Event Reference](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/identity-and-access-management/audit-trail/event-reference) — complete list of 60+ event types
