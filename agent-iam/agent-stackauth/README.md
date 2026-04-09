# Agent Delegation with Stack Auth

This example demonstrates GL-IAM agent delegation using Stack Auth for user authentication. It includes a unique feature: bridging Stack Auth opaque tokens to GL-IAM delegation JWTs via `create_delegation_token_from_stackauth()`.

## Prerequisites

- See [main prerequisites](../../README.md)
- Stack Auth instance running (see [stack-auth setup](https://docs.stack-auth.com))
- PostgreSQL running locally (for agent tables)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-stackauth
   ```

2. **Run setup**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   On Windows: `setup.bat`

3. **Configure Stack Auth** credentials in `.env`

4. **Start PostgreSQL** (if not running):
   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=gliam \
     -p 5432:5432 postgres:15
   ```

5. **Run the server**:
   ```bash
   uv run main.py
   ```

## Test the API

### 1. Get Stack Auth Token

```bash
TOKEN=$(uv run get_token.py --email user@example.com --password secret123)
echo "Token: $TOKEN"
```

### 2. Verify User

```bash
curl http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Register Agent

```bash
AGENT_ID=$(curl -s -X POST http://localhost:8000/agents/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stackauth-agent",
    "agent_type": "worker",
    "allowed_scopes": ["docs:read", "docs:write"]
  }' | jq -r '.id')

echo "Agent ID: $AGENT_ID"
```

### 4. Delegate to Agent

```bash
DELEGATION_TOKEN=$(curl -s -X POST http://localhost:8000/agents/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\"],
    \"task_purpose\": \"Read documents via Stack Auth\"
  }" | jq -r '.delegation_token')

echo "Delegation token: $DELEGATION_TOKEN"
```

### 5. Bridge Stack Auth Token (Unique Feature)

```bash
# Convert a Stack Auth opaque token directly to a GL-IAM delegation JWT
BRIDGED=$(curl -s -X POST http://localhost:8000/agents/delegate-from-stackauth \
  -H "Content-Type: application/json" \
  -d "{
    \"stackauth_access_token\": \"$TOKEN\",
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\"],
    \"task_purpose\": \"Bridged from Stack Auth\"
  }")

echo $BRIDGED
BRIDGED_TOKEN=$(echo $BRIDGED | jq -r '.delegation_token')
```

### 6. Use Agent Endpoints

```bash
# Agent identity
curl http://localhost:8000/agent/me \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# Scope-protected documents
curl http://localhost:8000/agent/documents \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# Delegation chain
curl http://localhost:8000/agent/chain \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"
```

## Stack Auth Token Bridge

The `create_delegation_token_from_stackauth()` method is a unique feature that converts Stack Auth opaque tokens into GL-IAM delegation JWTs:

```
Stack Auth Token (opaque)     GL-IAM Delegation Token (JWT)
┌──────────────────────┐      ┌──────────────────────┐
│ eyJ...opaque...token │ ──>  │ eyJ...jwt...with...  │
│                      │      │ agent_id, scopes,    │
│ (Stack Auth format)  │      │ chain, task context  │
└──────────────────────┘      └──────────────────────┘
```

This is useful when you have existing Stack Auth tokens and want to delegate to GL-IAM agents without re-authenticating.

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,stackauth]` | GL-IAM with FastAPI and Stack Auth support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
| `httpx` | HTTP client (for get_token.py) |
