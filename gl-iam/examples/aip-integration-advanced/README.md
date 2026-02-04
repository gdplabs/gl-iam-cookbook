# AIP Integration (Advanced)

This example demonstrates **advanced GL-IAM patterns** for securing AI agents with the AIP SDK. It builds on the [basic AIP Integration](../aip-integration/) example.

## What You'll Learn

| GL-IAM Feature | GL AIP SDK Pattern | Security Benefit |
|----------------|-------------------|------------------|
| `User.id`, `User.organization_id` | Runtime Configuration | Per-tenant data isolation |
| `User.has_standard_role()` | Role-Based Tool Filtering | Restrict tools by access level |
| `get_current_user`, `require_org_member()` | Endpoint Authorization | API-level access control |
| `User.roles`, `User.permissions` | Instruction Injection | Context-aware agent behavior |

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- Completed [AIP Integration](../aip-integration/) basic tutorial
- PostgreSQL database running locally
- (Optional) Access to GL AIP SDK (`glaip-sdk` package) for full agent features

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/aip-integration-advanced/
   ```

2. **Install dependencies**

   **For Unix-based systems (Linux, macOS):**
   ```bash
   ./setup.sh
   ```

   **For Windows:**
   ```cmd
   setup.bat
   ```

   Or manually: `uv sync`

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Start PostgreSQL** (if not running)

   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=gliam \
     -p 5432:5432 \
     postgres:15
   ```

5. **Run the server**

   ```bash
   uv run main.py
   ```

## Test the API

```bash
# Register a user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'

# Login to get token
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')

# Chat with advanced features
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What can you help me with?"}'
```

## Advanced Patterns

### Pattern 1: GL-IAM User Context in Tool Configuration

Tools need user/tenant context for proper data isolation:

```python
def build_tool_config_from_gliam_user(user: User) -> dict:
    if user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        access_level = "platform_admin"
    elif user.has_standard_role(StandardRole.ORG_ADMIN):
        access_level = "admin"
    else:
        access_level = "member"

    return {
        "tool_configs": {
            "secure_database_query": {
                "user_id": user.id,
                "tenant_id": user.organization_id or "default",
                "access_level": access_level,
            }
        }
    }
```

### Pattern 2: GL-IAM User-Scoped Memory

Memory operations must be scoped to the authenticated user:

```python
# Use GL-IAM User.id as session_id for memory scoping
result = agent.run(
    request.message,
    session_id=user.id,  # <-- GL-IAM: User.id scopes memory per user
)
```

### Pattern 3: Role-Based Tool Filtering

Filter available tools based on GL-IAM roles:

```python
def get_tools_for_user(user: User, all_tools: list) -> list:
    if user.has_standard_role(StandardRole.ORG_ADMIN):
        return all_tools  # Admins get all tools
    # Filter out admin-only tools for non-admin users
    return [t for t in all_tools if not t.name.startswith("admin_")]
```

### Pattern 4: Role-Based Agent Configuration

Configure different agent capabilities based on roles:

```python
def get_agent_config_for_user(user: User) -> dict:
    if user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        return {"planning": True, "timeout_seconds": 1800}
    if user.has_standard_role(StandardRole.ORG_ADMIN):
        return {"planning": True, "timeout_seconds": 600}
    return {"planning": False, "timeout_seconds": 120}
```

## GL-IAM Integration Summary

| GL-IAM Component | Usage in This Example |
|------------------|----------------------|
| `User` | Core user type with `id`, `email`, `organization_id`, `roles`, `permissions` |
| `StandardRole` | Cross-provider roles: `ORG_MEMBER`, `ORG_ADMIN`, `PLATFORM_ADMIN` |
| `user.has_standard_role()` | Check roles with hierarchy (admin implies member) |
| `user.has_permission()` | Fine-grained permission checks |
| `get_current_user` | FastAPI dependency for authentication |
| `require_org_member()` | FastAPI dependency requiring ORG_MEMBER+ |
| `require_org_admin()` | FastAPI dependency requiring ORG_ADMIN+ |
| `set_iam_gateway()` | Configure GL-IAM for FastAPI application |
