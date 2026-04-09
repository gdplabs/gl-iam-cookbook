# Cross-Service Agent Delegation

This example demonstrates how delegation tokens work across service boundaries. Service A handles user auth and creates delegation tokens; Service B validates those tokens and provides protected resources.

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-cross-service
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

4. **Run both services** (in separate terminals):
   ```bash
   # Terminal 1: Service A (port 8000)
   uv run service_a.py

   # Terminal 2: Service B (port 8001)
   uv run service_b.py
   ```

## Test the API

### 1. Register and Login on Service A

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}' | jq -r '.access_token')
```

### 2. Register Agent on Service A

```bash
AGENT_ID=$(curl -s -X POST http://localhost:8000/agents/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "cross-service-agent",
    "allowed_scopes": ["docs:read", "docs:write"]
  }' | jq -r '.id')

echo "Agent ID: $AGENT_ID"
```

### 3. Create Delegation Token on Service A

```bash
DELEGATION_TOKEN=$(curl -s -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\"],
    \"task_purpose\": \"Read documents from Service B\"
  }" | jq -r '.delegation_token')

echo "Delegation token: $DELEGATION_TOKEN"
```

### 4. Use Token with Service B

```bash
# Access protected documents on Service B
curl -s http://localhost:8001/documents \
  -H "X-Delegation-Token: $DELEGATION_TOKEN" | jq

# Get agent info on Service B
curl -s http://localhost:8001/agent/info \
  -H "X-Delegation-Token: $DELEGATION_TOKEN" | jq

# View delegation chain on Service B
curl -s http://localhost:8001/chain \
  -H "X-Delegation-Token: $DELEGATION_TOKEN" | jq
```

## Architecture

```
Service A (port 8000)                    Service B (port 8001)
┌─────────────────────┐                 ┌─────────────────────┐
│ Full Gateway        │                 │ Minimal Gateway     │
│ - User auth         │                 │ - Agent auth only   │
│ - Agent registration│   Delegation    │ - Token validation  │
│ - Token creation    │ ──── Token ───> │ - Scope enforcement │
│                     │                 │                     │
│ PostgreSQLProvider  │                 │ PostgreSQLAgent     │
│ (full stack)        │                 │ Provider (minimal)  │
└─────────────────────┘                 └─────────────────────┘
         │                                       │
         └──────── Shared PostgreSQL DB ─────────┘
         └──────── Shared SECRET_KEY ────────────┘
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Service A** | Full gateway with `from_fullstack_provider()` for user auth + agent management |
| **Service B** | Minimal gateway with `for_agent_auth()` for token validation only |
| **Shared Secret** | Both services must use the same `SECRET_KEY` for JWT validation |
| **Shared Database** | Both services connect to the same PostgreSQL for agent state |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,postgresql]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
