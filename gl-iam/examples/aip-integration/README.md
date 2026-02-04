# AIP Integration

This example shows how to secure AI Agent APIs using GL-IAM for authentication and authorization when building custom agent APIs with the GL AIP SDK. It uses the PostgreSQL provider for simplicity.

**When to use this pattern:**
- Building new AI agent APIs from scratch
- Need user-based authentication for agent endpoints
- Want role-based access control for AI capabilities

> **Note:** Looking to add GL-IAM to an existing AIP backend server? See [aip-server-integration](../aip-server-integration/) instead.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- PostgreSQL database running locally
- (Optional) Access to GL AIP SDK (`glaip-sdk` package) for full agent features

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/aip-integration/
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
# Health check (no auth required)
curl http://localhost:8000/health

# Register a user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "display_name": "Test User"}'

# Login to get token
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')

# Chat with agent (requires Bearer token)
curl -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is it?"}'
```

## GL-IAM Code Summary

The GL-IAM integration consists of these key elements:

| Line | GL-IAM Code | Purpose |
|------|-------------|---------|
| Imports | `from gl_iam import IAMGateway, StandardRole, User` | Core GL-IAM types |
| Imports | `from gl_iam.fastapi import get_current_user, require_org_member, set_iam_gateway` | FastAPI dependencies |
| Imports | `from gl_iam.providers.postgresql import PostgreSQLProvider, PostgreSQLUserStoreConfig` | PostgreSQL provider |
| Setup | `set_iam_gateway(gateway, ...)` | Initialize GL-IAM for FastAPI |
| Endpoint | `user: User = Depends(get_current_user)` | Get authenticated user |
| Endpoint | `Depends(require_org_member())` | Require ORG_MEMBER role |
| Logic | `user.has_standard_role(StandardRole.ORG_ADMIN)` | Check user role |
| Logic | `user.id`, `user.email`, `user.display_name` | Access user properties |

## Key Integration Points

1. **User Context in Agent**: The agent receives user information (name, access level) in its system instruction
2. **Role-Based Protection**: `require_org_member()` ensures only authenticated organization members can access the chat endpoint
3. **Standard Roles**: Use `has_standard_role()` to check user access levels (ORG_MEMBER, ORG_ADMIN, PLATFORM_ADMIN)
