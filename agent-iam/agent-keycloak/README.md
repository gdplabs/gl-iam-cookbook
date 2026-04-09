# Agent Delegation with Keycloak

This example demonstrates GL-IAM agent delegation using Keycloak for user authentication. Users authenticate via Keycloak's OpenID Connect flow, then register agents and create delegation tokens.

## Prerequisites

- See [main prerequisites](../../README.md)
- Docker and Docker Compose (for Keycloak and PostgreSQL)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-keycloak
   ```

2. **Run setup**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```
   On Windows: `setup.bat`

3. **Start Keycloak and PostgreSQL**:
   ```bash
   docker-compose up -d
   ```

4. **Wait for Keycloak** to be ready at http://localhost:8080 (admin/admin)

5. **Run the server**:
   ```bash
   uv run main.py
   ```

## Test the API

### 1. Get Keycloak Token

```bash
KC_TOKEN=$(curl -s -X POST \
  http://localhost:8080/realms/gl-iam-demo/protocol/openid-connect/token \
  -d "grant_type=password" \
  -d "client_id=glchat-backend" \
  -d "client_secret=glchat-backend-secret" \
  -d "username=user@example.com" \
  -d "password=user123" | jq -r '.access_token')

echo "Keycloak token: $KC_TOKEN"
```

### 2. Verify User

```bash
curl http://localhost:8000/me \
  -H "Authorization: Bearer $KC_TOKEN"
```

### 3. Register Agent

```bash
AGENT_ID=$(curl -s -X POST http://localhost:8000/agents/register \
  -H "Authorization: Bearer $KC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "keycloak-agent",
    "agent_type": "worker",
    "allowed_scopes": ["docs:read", "docs:write"]
  }' | jq -r '.id')

echo "Agent ID: $AGENT_ID"
```

### 4. Delegate to Agent

```bash
DELEGATION_TOKEN=$(curl -s -X POST http://localhost:8000/agents/delegate \
  -H "Authorization: Bearer $KC_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\"],
    \"task_purpose\": \"Read Keycloak-managed documents\"
  }" | jq -r '.delegation_token')

echo "Delegation token: $DELEGATION_TOKEN"
```

### 5. Use Agent Endpoints

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

### 6. List Agents

```bash
curl http://localhost:8000/agents \
  -H "Authorization: Bearer $KC_TOKEN"
```

## Architecture

```
Keycloak (port 8080)          FastAPI App (port 8000)
┌──────────────────┐          ┌─────────────────────┐
│ User Auth        │          │ KeycloakProvider     │
│ - OpenID Connect │ ──JWT──> │ - Token validation   │
│ - User management│          │ - Agent registration │
│ - Role mapping   │          │ - Delegation tokens  │
└──────────────────┘          └─────────────────────┘
                                       │
                              ┌────────┴────────┐
                              │   PostgreSQL     │
                              │ (Agent tables)   │
                              └─────────────────┘
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Keycloak Token** | OIDC JWT token for user authentication |
| **Delegation Token** | GL-IAM JWT token for agent authorization |
| **Agent Mapping** | Agents are linked to Keycloak user IDs |
| **Shared DB** | Agent state stored in PostgreSQL alongside Keycloak |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,keycloak]` | GL-IAM with FastAPI and Keycloak support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
