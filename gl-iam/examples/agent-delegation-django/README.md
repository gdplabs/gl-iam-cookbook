# Agent Delegation with Django

This example demonstrates GL-IAM agent delegation using Django with three integration patterns: Function-Based Views (FBV), Class-Based Views (CBV), and Django REST Framework (DRF).

## Prerequisites

- See [main prerequisites](../../README.md)
- PostgreSQL running locally (or via Docker)

## Getting Started

1. **Clone and navigate**:
   ```bash
   cd gl-iam-cookbook/gl-iam/examples/agent-delegation-django
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
   uv run python manage.py runserver
   ```

## Test the API

### 1. Register and Login

```bash
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "secret123"}' | jq -r '.access_token')
```

### 2. Register Agent and Delegate

```bash
AGENT_ID=$(curl -s -X POST http://localhost:8000/api/fbv/agents/register/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "django-agent", "agent_type": "worker", "allowed_scopes": ["docs:read"]}' | jq -r '.id')

DELEGATION_TOKEN=$(curl -s -X POST http://localhost:8000/api/fbv/delegate/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"agent_id\": \"$AGENT_ID\", \"scopes\": [\"docs:read\"]}" | jq -r '.delegation_token')
```

### 3. Test All Three Patterns

```bash
# FBV (decorators)
curl http://localhost:8000/api/fbv/agent/documents/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

curl http://localhost:8000/api/fbv/agent/chain/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

curl http://localhost:8000/api/fbv/agent/worker-only/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# CBV (mixins)
curl http://localhost:8000/api/cbv/agent/documents/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

curl http://localhost:8000/api/cbv/agent/chain/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

# DRF (authentication + permission classes)
curl http://localhost:8000/api/drf/agent/documents/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

curl http://localhost:8000/api/drf/agent/worker-only/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"

curl http://localhost:8000/api/drf/agent/chain/ \
  -H "X-Delegation-Token: $DELEGATION_TOKEN"
```

## Three Integration Patterns

### Pattern 1: FBV with Decorators

```python
@require_agent_scope("docs:read")
def my_view(request):
    agent = request.gl_iam_agent
    ...
```

### Pattern 2: CBV with Mixins

```python
class MyView(AgentScopeRequiredMixin, View):
    agent_scope = "docs:read"

    def get(self, request):
        agent = request.gl_iam_agent
        ...
```

### Pattern 3: DRF with Auth/Permission Classes

```python
class MyView(APIView):
    authentication_classes = [GLIAMAgentAuthentication]
    permission_classes = [HasAgentScope.with_scope("docs:read")]

    def get(self, request):
        agent = request.user.agent
        ...
```

## Middleware Configuration

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "gl_iam.django.middleware.GLIAMAuthenticationMiddleware",    # User auth
    "gl_iam.django.agent_middleware.GLIAMAgentMiddleware",      # Agent auth
]
```

### Key Concepts

| Concept | FBV | CBV | DRF |
|---------|-----|-----|-----|
| Scope check | `@require_agent_scope("...")` | `AgentScopeRequiredMixin` | `HasAgentScope.with_scope("...")` |
| Type check | `@require_agent_type(AgentType.WORKER)` | N/A | `HasAgentType.with_type(AgentType.WORKER)` |
| Chain check | `@require_delegation_chain` | `DelegationChainRequiredMixin` | `HasDelegationChain` |
| Constraint | `@require_resource_constraint(...)` | N/A | `HasResourceConstraint.with_constraint(...)` |
| Agent access | `request.gl_iam_agent` | `request.gl_iam_agent` | `request.user.agent` |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `gl-iam[django,postgresql]` | GL-IAM with Django and PostgreSQL support |
| `django` | Web framework |
| `djangorestframework` | REST API framework |
