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

### 6. Reactivate Agent

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
| **Reactivate** | Re-enables a suspended agent through `IAMGateway` |
| **Revoke** | Permanently disables an agent; cannot be undone |
| **Audit Callback** | Captures all lifecycle events for compliance |

### Audit Event Types

The lifecycle flow emits the following audit records across the example's
supported `gl-iam` 0.3.x range. Verify event names against the installed
runtime when changing that dependency range.

| Event | Fires? | Notes |
|-------|-----------------|-------|
| `AGENT_REGISTERED` | Yes | Emitted by `gateway.register_agent()` on success. |
| `AGENT_SUSPENDED` | Yes | The lifecycle flow persists `agent_suspended` when `gateway.suspend_agent()` succeeds. |
| `AGENT_REACTIVATED` | Yes | Emitted by `gateway.reactivate_agent()` on success. |
| `AGENT_REVOKED` | Yes | Emitted by `gateway.revoke_agent()` on success. |
| `DELEGATION_CREATED` | Yes | Emitted by `gateway.delegate_to_agent()` on a successful delegation. |
| `DELEGATION_DENIED` | Yes | The lifecycle flow persists `delegation_denied` when a suspended or revoked agent is denied a delegation. |

In short: registration, suspension, reactivation, revocation, successful
delegation, and denied delegation are audited by the gateway flow.

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,native]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
