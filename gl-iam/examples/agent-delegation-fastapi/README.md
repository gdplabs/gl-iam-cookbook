# Agent Delegation with FastAPI

This example demonstrates the core GL-IAM agent delegation system using FastAPI and PostgreSQL. It shows how to register AI agents, delegate authority via tokens, and protect endpoints with agent scope requirements.

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-delegation-fastapi
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

### 1. Health Check

```bash
curl http://localhost:8000/health
```

### 2. Register a User

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}'
```

### 3. Login

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}' | jq -r '.access_token')

echo "User token: $TOKEN"
```

### 4. Register an Agent

```bash
AGENT=$(curl -s -X POST http://localhost:8000/agents/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "doc-reader-agent",
    "agent_type": "worker",
    "allowed_scopes": ["docs:read", "docs:list"]
  }')

echo $AGENT
AGENT_ID=$(echo $AGENT | jq -r '.id')
```

### 5. Delegate Authority to Agent

```bash
DELEGATION=$(curl -s -X POST http://localhost:8000/agents/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"task_id\": \"task-001\",
    \"task_purpose\": \"Read quarterly documents\",
    \"scopes\": [\"docs:read\"],
    \"expires_in_seconds\": 3600
  }")

echo $DELEGATION
DELEGATION_TOKEN=$(echo $DELEGATION | jq -r '.delegation_token')
```

### 6. Use Delegation Token (Agent Endpoints)

```bash
# Get agent identity
curl http://localhost:8000/agent/me \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# Access scoped documents (requires docs:read)
curl http://localhost:8000/agent/documents \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# Get task info
curl http://localhost:8000/agent/task \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# Inspect delegation chain
curl http://localhost:8000/agent/chain \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"
```

### 7. List User's Agents

```bash
curl http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN"
```

## Understanding the Code

### Agent Delegation Flow

```
User (Bearer Token)              Agent (X-Delegation-Token)
       |                                    |
  POST /agents/register  ──>  Creates agent with allowed scopes
  POST /agents/delegate  ──>  Creates delegation token
       |                                    |
       |              ┌─────────────────────┘
       |              v
  GET /agent/me       ──>  Returns agent identity
  GET /agent/documents ──>  Scope-protected endpoint
  GET /agent/task      ──>  Task context from token
  GET /agent/chain     ──>  Delegation chain info
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Agent Registration** | Creates an agent with a type, owner, and allowed scopes |
| **Delegation Token** | JWT token granting an agent specific scopes for a task |
| **Agent Scope** | Fine-grained permission (e.g., `docs:read`, `docs:write`) |
| **Delegation Chain** | Tracks the authority path from user to agent |
| **Task Context** | Metadata about why the delegation was created |

### Agent Types

| Type | Description |
|------|-------------|
| `orchestrator` | Coordinates other agents |
| `worker` | Performs specific tasks |
| `tool` | Provides tool/function capabilities |
| `autonomous` | Operates independently |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,postgresql]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
