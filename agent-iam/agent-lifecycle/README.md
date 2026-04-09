# Agent Lifecycle Management

This example demonstrates the full agent lifecycle in GL-IAM: registration, suspension, reactivation, revocation, and audit event capture.

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-lifecycle
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
  -d '{"email": "alice@example.com", "password": "secret123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}' | jq -r '.access_token')
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

| Event | Triggered When |
|-------|---------------|
| `AGENT_REGISTERED` | Agent is created |
| `AGENT_SUSPENDED` | Agent is suspended |
| `AGENT_REACTIVATED` | Agent is reactivated |
| `AGENT_REVOKED` | Agent is permanently revoked |
| `DELEGATION_CREATED` | Delegation token is issued |
| `DELEGATION_DENIED` | Delegation attempt is rejected |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,postgresql]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
