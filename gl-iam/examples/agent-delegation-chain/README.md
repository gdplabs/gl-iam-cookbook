# Multi-Hop Delegation Chains

This example demonstrates how delegation authority flows through multiple hops in GL-IAM. A user delegates to an orchestrator, which sub-delegates to a worker, with scopes narrowing at each hop.

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-delegation-chain
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

### 2. Setup Orchestrator and Worker

```bash
SETUP=$(curl -s -X POST http://localhost:8000/setup \
  -H "Authorization: Bearer $TOKEN")

echo $SETUP
ORCHESTRATOR_ID=$(echo $SETUP | jq -r '.orchestrator_id')
WORKER_ID=$(echo $SETUP | jq -r '.worker_id')
```

### 3. Delegate User -> Orchestrator (Hop 1)

```bash
HOP1=$(curl -s -X POST "http://localhost:8000/delegate/orchestrator?orchestrator_id=$ORCHESTRATOR_ID" \
  -H "Authorization: Bearer $TOKEN")

echo "Hop 1 - depth: $(echo $HOP1 | jq '.chain_depth'), scopes: $(echo $HOP1 | jq '.effective_scopes')"
ORCH_TOKEN=$(echo $HOP1 | jq -r '.token')
```

### 4. Delegate Orchestrator -> Worker (Hop 2)

```bash
HOP2=$(curl -s -X POST "http://localhost:8000/delegate/worker?worker_id=$WORKER_ID&orchestrator_token=$ORCH_TOKEN")

echo "Hop 2 - depth: $(echo $HOP2 | jq '.chain_depth'), scopes: $(echo $HOP2 | jq '.effective_scopes')"
WORKER_TOKEN=$(echo $HOP2 | jq -r '.token')
```

### 5. Inspect the Chain

```bash
# Inspect orchestrator's chain (depth 1)
curl -s "http://localhost:8000/chain/inspect?token=$ORCH_TOKEN" | jq

# Inspect worker's chain (depth 2, narrower scopes)
curl -s "http://localhost:8000/chain/inspect?token=$WORKER_TOKEN" | jq
```

## Understanding Scope Narrowing

```
User (all permissions)
  └── Orchestrator (docs:read, docs:write, analytics:read) ← max_actions=100
        └── Worker (docs:read) ← max_actions=10

Effective scopes at each hop:
  Hop 1: {docs:read, docs:write, analytics:read}
  Hop 2: {docs:read}  ← intersection narrows the scope
```

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Chain Depth** | Number of delegation hops (User→Orchestrator = 1, User→Orch→Worker = 2) |
| **Scope Narrowing** | Each hop can only grant a subset of the parent's scopes |
| **Root Principal** | The original authority (the user who started the chain) |
| **Leaf Principal** | The final agent in the chain (the one performing work) |
| **Effective Scopes** | Intersection of all scopes across the chain |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[fastapi,postgresql]` | GL-IAM with FastAPI and PostgreSQL support |
| `fastapi` | Web framework |
| `uvicorn` | ASGI server |
