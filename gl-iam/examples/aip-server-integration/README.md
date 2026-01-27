# AIP Server Integration

This example shows how to integrate GL-IAM into an existing AI Agent Platform (AIP) server, adding user-based authentication alongside the existing API key system while maintaining backward compatibility.

**When to use this pattern:**
- You have an existing AIP server using API key authentication
- You want to add user-based JWT authentication without breaking existing clients
- You need unified identity that works with both Bearer tokens and API keys

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- PostgreSQL database running locally
- Understanding of FastAPI dependency injection

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/aip-server-integration/
   ```

2. **Set UV authentication and install dependencies**

   **For Unix-based systems (Linux, macOS):**
   ```bash
   ./setup.sh
   ```

   **For Windows:**
   ```cmd
   setup.bat
   ```

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Start PostgreSQL** (if not running)

   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=aip \
     -p 5432:5432 \
     postgres:15
   ```

5. **Run the server**

   ```bash
   uv run main.py
   ```

## Architecture

### Before GL-IAM

```
Request with X-API-Key
        |
        v
+-----------------------------+
| verify_api_key()            |
| 1. Check master key (env)   |
| 2. Check account keys (DB)  |
+-----------------------------+
        |
        v
    UUID | None
    (Account ID or None for master)
```

### After GL-IAM (This Example)

```
Request with X-API-Key OR Bearer Token
        |
        v
+-----------------------------------------------+
|             GL-IAM Gateway                     |
|  +--------------+     +--------------+        |
|  | API Key Auth | OR  | Bearer Auth  |        |
|  | (X-API-Key)  |     | (JWT/Session)|        |
|  +--------------+     +--------------+        |
|         |                     |               |
|         v                     v               |
|  +---------------------------------------+    |
|  |         Unified Identity              |    |
|  |  - User ID                            |    |
|  |  - Account/Organization ID            |    |
|  |  - Roles (StandardRole)               |    |
|  +---------------------------------------+    |
+-----------------------------------------------+
```

## Test the API

### Test with Legacy API Key (Backward Compatible)

```bash
# Should still work with X-API-Key
curl -X GET http://localhost:8000/agents \
  -H "X-API-Key: test-api-key"
```

### Test with GL-IAM Bearer Token

```bash
# Register a user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "display_name": "Test User"}'

# Login to get token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')

# Use token with Bearer auth
curl -X GET http://localhost:8000/agents \
  -H "Authorization: Bearer $TOKEN"
```

## Understanding the Code

### Unified Authentication

The `get_unified_identity()` function supports both authentication methods:

```python
async def get_unified_identity(
    bearer_token: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    api_key: str | None = Security(api_key_scheme),
) -> User | UUID | None:
    # Priority:
    # 1. Bearer token (GL-IAM session) -> Returns User object
    # 2. X-API-Key (legacy) -> Returns UUID (account_id) or None
```

### Role Mapping

| Legacy Concept | GL-IAM Role | Description |
|----------------|-------------|-------------|
| Master API Key | `PLATFORM_ADMIN` | Full platform access |
| Account Owner | `ORG_ADMIN` | Organization/account admin |
| Account Member | `ORG_MEMBER` | Basic organization access |

### Key Components

| Component | Purpose |
|-----------|---------|
| `get_unified_identity()` | Get identity from either Bearer or API key |
| `get_account_id_from_identity()` | Extract account ID for data scoping |
| `require_org_member()` | GL-IAM RBAC or legacy API key check |
| `require_org_admin()` | GL-IAM RBAC or master API key check |

## Reference

This example is based on the [GL-IAM AIP Server Integration tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/aip-server-integration).
