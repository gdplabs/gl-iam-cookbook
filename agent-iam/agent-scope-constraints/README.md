# Resource Constraint Validators

This example demonstrates GL-IAM's resource constraint system for fine-grained access control beyond scopes. Constraints allow you to restrict agents to specific tenants, regions, budgets, and more.

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-scope-constraints
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

### 1. Register, Login, and Setup Agent

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}' | jq -r '.access_token')

AGENT_ID=$(curl -s -X POST http://localhost:8000/setup \
  -H "Authorization: Bearer $TOKEN" | jq -r '.agent_id')
```

### 2. Delegate with Constraints

```bash
DELEGATION=$(curl -s -X POST http://localhost:8000/delegate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\", \"docs:write\"],
    \"resource_constraints\": {
      \"tenant_id\": \"acme\",
      \"regions\": [\"us-east-1\", \"eu-west-1\"],
      \"budget\": 100
    }
  }")

echo $DELEGATION
PARENT_TOKEN=$(echo $DELEGATION | jq -r '.delegation_token')
```

### 3. Narrow Constraints (Success)

```bash
# Sub-delegate with narrower constraints -> succeeds
curl -s -X POST http://localhost:8000/delegate/narrow \
  -H "Content-Type: application/json" \
  -d "{
    \"parent_token\": \"$PARENT_TOKEN\",
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\"],
    \"resource_constraints\": {
      \"tenant_id\": \"acme\",
      \"regions\": [\"us-east-1\"],
      \"budget\": 50
    }
  }" | jq
```

### 4. Scope Escalation (Denied)

```bash
# Try to escalate scopes -> denied
curl -s -X POST http://localhost:8000/delegate/escalate \
  -H "Content-Type: application/json" \
  -d "{
    \"parent_token\": \"$PARENT_TOKEN\",
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\", \"docs:delete\"],
    \"resource_constraints\": {\"tenant_id\": \"acme\"}
  }" | jq
```

### 5. Constraint Violation (Denied)

```bash
# Try to widen budget constraint -> denied
curl -s -X POST http://localhost:8000/delegate/constraint-violation \
  -H "Content-Type: application/json" \
  -d "{
    \"parent_token\": \"$PARENT_TOKEN\",
    \"agent_id\": \"$AGENT_ID\",
    \"scopes\": [\"docs:read\"],
    \"resource_constraints\": {
      \"tenant_id\": \"acme\",
      \"budget\": 200
    }
  }" | jq
```

### 6. Access Protected Resource

```bash
curl http://localhost:8000/protected \
  -H "X-Delegation-Token: $PARENT_TOKEN"
```

## Understanding Constraint Validators

| Validator | Rule | Example |
|-----------|------|---------|
| `string_equality_validator` | Child value must equal parent | `tenant_id: "acme"` must stay `"acme"` |
| `set_subset_validator` | Child set must be subset of parent | `regions: ["us-east-1"]` is subset of `["us-east-1", "eu-west-1"]` |
| `numeric_lte_validator` | Child number must be <= parent | `budget: 50` is <= `100` |
| `composite_validator` | Combines multiple validators | Applies all of the above |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,postgresql]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
