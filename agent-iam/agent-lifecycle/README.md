# Agent Lifecycle Management

This example demonstrates the full agent lifecycle in GL-IAM: registration, suspension, reactivation, revocation, and audit event capture.

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/agent-iam/agent-lifecycle
   ```

2. **Run setup**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   On Windows: `setup.bat`

3. **Start PostgreSQL** (if not running):
   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=gliam \
     -p 5432:5432 postgres:15
   ```

4. **Run the server**:
   ```bash
   uv run main.py
   ```

## Test the API

### 1. Register and Login

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!"}'

TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')
```

### 2. Register an Agent

```bash
AGENT_ID=$(curl -s -X POST http://localhost:8000/agents/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "lifecycle-agent", "allowed_scopes": ["docs:read"]}' | jq -r '.id')

echo "Agent ID: $AGENT_ID"
```

### 3. Delegate (Success - Agent is Active)

```bash
curl -s -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"scopes\": [\"docs:read\"]}" | jq
```

### 4. Suspend Agent

```bash
curl -s -X POST "http://localhost:8000/agents/$AGENT_ID/suspend" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 5. Delegate (Fails - Agent is Suspended)

```bash
curl -s -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"scopes\": [\"docs:read\"]}" | jq
```

### 6. Reactivate Agent (Provider-Level)

```bash
curl -s -X POST "http://localhost:8000/agents/$AGENT_ID/reactivate" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 7. Delegate (Success - Agent is Active Again)

```bash
curl -s -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"scopes\": [\"docs:read\"]}" | jq
```

### 8. Revoke Agent (Permanent)

```bash
curl -s -X POST "http://localhost:8000/agents/$AGENT_ID/revoke" \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 9. Delegate (Fails - Agent is Revoked)

```bash
curl -s -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"scopes\": [\"docs:read\"]}" | jq
```

### 10. View Audit Log

```bash
curl -s http://localhost:8000/audit-log \
  -H "Authorization: Bearer $TOKEN" | jq
```

### 11. List Agents (Include Revoked)

```bash
curl -s "http://localhost:8000/agents?include_revoked=true" \
  -H "Authorization: Bearer $TOKEN" | jq
```

## Understanding the Lifecycle

```
ACTIVE ──suspend──> SUSPENDED ──reactivate──> ACTIVE
  │                                             │
  └──revoke──> REVOKED <──────revoke────────────┘
                  (permanent, cannot reactivate)
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Suspend** | Temporarily disables an agent; can be reactivated |
| **Reactivate** | Re-enables a suspended agent (provider-level only) |
| **Revoke** | Permanently disables an agent; cannot be undone |
| **Audit Callback** | Captures all lifecycle events for compliance |

### Audit Event Types

On the current SDK (`main`), only some lifecycle operations actually emit an
audit event through `IAMGateway`. Verified by running the full lifecycle below
and inspecting `/audit-log`:

| Event | Fires on main? | Notes |
|-------|-----------------|-------|
| `AGENT_REGISTERED` | Yes | Emitted by `gateway.register_agent()` on success. |
| `AGENT_SUSPENDED` | **No** | `gateway.suspend_agent()` updates the agent's status but does not call `_emit_audit_event`. The status change happens; no event is logged. |
| `AGENT_REACTIVATED` | **No** | `reactivate_agent()` is not exposed on `IAMGateway` at all -- only on the provider (`gateway.agent_provider.reactivate_agent(...)`, see the `/agents/{id}/reactivate` handler below). Calling it directly bypasses the gateway's audit wiring entirely. |
| `AGENT_REVOKED` | Yes | Emitted by `gateway.revoke_agent()` on success. |
| `DELEGATION_CREATED` | Yes | Emitted by `gateway.delegate_to_agent()` on a successful delegation. |
| `DELEGATION_DENIED` | **Does not exist as an event type.** | There is no `DELEGATION_DENIED` enum value in the SDK. `delegate_to_agent()` only maps specific error codes (`SCOPE_ESCALATION_DENIED`, `DELEGATION_DEPTH_EXCEEDED`, `RESOURCE_CONSTRAINT_VIOLATION`) to their own dedicated event types. A denial caused by a suspended/revoked/not-found agent (the cases this example demonstrates) falls through to the **same** `DELEGATION_CREATED` event type, just with `severity="warning"` -- so a denied delegation and a successful one currently look identical in `event_type`, distinguishable only by `severity`. |

In short: register/revoke/successful-delegate are audited; suspend and
reactivate are silent; and "denied delegation" is a `DELEGATION_CREATED`
event with `severity=warning`, not a distinct event type. This is SDK
behavior (`gl_iam/core/gateway.py`), not something this example's code can
paper over -- treat the table above as the accurate contract, not the
aspirational one.

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,native]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
