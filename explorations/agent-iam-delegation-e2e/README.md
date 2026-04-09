# Agent IAM Delegation — End-to-End Demo

A 3-service demo that simulates the full GLChat → AIP → Connectors delegation flow described in the [Agent IAM Delegation Architecture](https://github.com/GDP-ADMIN/gl-sdk/blob/feature/gl-iam-agent-iam/libs/gl-iam/docs/AGENT_IAM_DELEGATION_ARCHITECTURE.md).

## What This Demonstrates

```
┌──────────────┐    delegation    ┌──────────────┐    delegation    ┌──────────────┐
│  GLChat BE   │ ──── token ────► │ AIP Backend  │ ──── token ────► │ GL Connectors│
│  (port 8000) │                  │  (port 8001) │                  │  (port 8002) │
│              │                  │              │                  │              │
│ • User auth  │                  │ • Token      │                  │ • Per-tool   │
│ • ABAC rules │                  │   validation │                  │   scope check│
│ • Delegation │                  │ • Tool       │                  │ • Mock APIs  │
│   creation   │                  │   planning   │                  │ • Defense in │
│              │                  │              │                  │   depth      │
└──────────────┘                  └──────────────┘                  └──────────────┘
```

| Concept | Where in Demo |
|---|---|
| Stateless JWT (no DB write on token path) | `delegate_to_agent()` in `glchat_be.py` |
| Scope attenuation (child ⊆ parent) | ABAC logic in `glchat_be.py` |
| Same agent, different effective scopes | `demo.sh`: admin vs member vs viewer |
| 3 enforcement points | creation → validation → tool scope |
| Defense in depth | `connectors.py` re-validates token independently |
| Audit trail via `delegation_ref` | JSON logs with shared ref across all 3 services |
| Shared `secret_key`, no shared session DB | `.env.example` — single key, token is JWT |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for PostgreSQL)
- `jq` (for pretty-printing in demo script)

## Quick Start

```bash
# 1. Setup
./setup.sh

# 2. Start PostgreSQL
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=gliam \
  -p 5432:5432 postgres:15

# 3. Start all 3 services (each in a separate terminal)
uv run glchat_be.py      # Terminal 1 — port 8000
uv run aip_backend.py    # Terminal 2 — port 8001
uv run connectors.py     # Terminal 3 — port 8002

# 4. Run the demo
./demo.sh
```

## The 4 Demo Scenarios

### Scenario 1: Alice (admin) → Full Delegation

Alice has role `admin` → ABAC passes all agent scopes through unchanged.

```
Agent ceiling:    [calendar:read, calendar:write, slack:post, notion:read]
Alice's scopes:   [calendar:read, calendar:write, slack:post, notion:read]  ← all pass
Available tools:  calendar.list_events, calendar.create_event, slack.post_message, notion.get_page
```

### Scenario 2: Bob (member) → Intersection

Bob has role `member` → scopes are intersected with member entitlements.

```
Agent ceiling:    [calendar:read, calendar:write, slack:post, notion:read]
Member entitled:  [calendar:read, calendar:write, notion:read]
Bob's scopes:     [calendar:read, calendar:write, notion:read]  ← slack:post removed
Available tools:  calendar.list_events, calendar.create_event, notion.get_page
```

### Scenario 3: Carol (viewer) → Read-Only

Carol has role `viewer` → only `*:read` scopes pass through.

```
Agent ceiling:    [calendar:read, calendar:write, slack:post, notion:read]
Carol's scopes:   [calendar:read, notion:read]  ← only :read suffixes
Available tools:  calendar.list_events, notion.get_page
```

### Scenario 4: Scope Ceiling Enforcement

Even Alice (admin) cannot use `gmail:send` because it's not in the agent's `allowed_scopes`:

```
Agent ceiling:    [calendar:read, calendar:write, slack:post, notion:read]
                  ← gmail:send NOT listed
Result:           gmail:send is never delegated, regardless of user role
```

## Manual Testing (curl)

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8002/health

# Register a user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!", "role": "admin"}'

# Login
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')

# Register an agent
AGENT_ID=$(curl -s -X POST http://localhost:8000/agents/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "my-agent",
    "allowed_scopes": ["calendar:read", "calendar:write", "slack:post", "notion:read"]
  }' | jq -r '.id')

# Trigger the full delegation flow
curl -X POST http://localhost:8000/chat/run-agent \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"user_message\": \"Schedule a meeting and notify the team\"}" | jq
```

## Architecture Details

### Token Flow

```
User (Bearer JWT)                    Agent (X-Delegation-Token JWT)
      │                                        │
      ▼                                        ▼
  GLChat BE                               AIP Backend
  ┌─────────────────┐                   ┌─────────────────┐
  │ 1. Authenticate  │                   │ 4. Validate JWT  │
  │ 2. ABAC filter   │                   │ 5. Plan tools    │
  │ 3. delegate_to_  │──── HTTP ────────►│ 6. Call          │
  │    agent()       │  X-Delegation-    │    connectors    │
  │    (JWT created) │  Token header     │                  │
  └─────────────────┘                   └────────┬─────────┘
                                                  │
                                                  ▼
                                            Connectors
                                        ┌─────────────────┐
                                        │ 7. Validate JWT  │
                                        │ 8. Check scope   │
                                        │ 9. Execute tool  │
                                        └─────────────────┘
```

### Audit Correlation

All 3 services emit structured JSON logs with a shared `delegation_ref`:

```
# Terminal 1 (glchat_be):
{"service": "glchat_be",  "event": "abac_applied",          "delegation_ref": "dlg-a1b2c3d4e5f6", ...}
{"service": "glchat_be",  "event": "delegation_created",    "delegation_ref": "dlg-a1b2c3d4e5f6", ...}

# Terminal 2 (aip_backend):
{"service": "aip_backend", "event": "delegation_validated", "delegation_ref": "dlg-a1b2c3d4e5f6", ...}
{"service": "aip_backend", "event": "agent_planned",        "delegation_ref": "dlg-a1b2c3d4e5f6", ...}

# Terminal 3 (connectors):
{"service": "connectors",  "event": "tool_call_allowed",    "delegation_ref": "dlg-a1b2c3d4e5f6", ...}
```

## File Structure

| File | Role | Port |
|---|---|---|
| `glchat_be.py` | User auth + ABAC + delegation creation | 8000 |
| `aip_backend.py` | Token validation + tool planning + routing | 8001 |
| `connectors.py` | Per-tool scope enforcement + mock APIs | 8002 |
| `demo.sh` | End-to-end curl demo (4 scenarios) | — |
| `setup.sh` | Dependency installation | — |

## Key GL-IAM APIs Used

```python
# GLChat BE — full provider
gateway = IAMGateway.from_fullstack_provider(PostgreSQLProvider(config))
result = await gateway.delegate_to_agent(principal_token, agent_id, task, scope)

# AIP Backend / Connectors — minimal agent-only provider
gateway = IAMGateway.for_agent_auth(PostgreSQLAgentProvider(config), secret_key=...)

# FastAPI dependencies (AIP + Connectors)
agent: AgentIdentity = Depends(get_current_agent)          # X-Delegation-Token
token: DelegationToken = Depends(get_delegation_token)      # full token with chain
_: None = Depends(require_agent_scope("calendar:read"))     # scope enforcement
```
