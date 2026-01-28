# FastAPI with PostgreSQL Provider

Add authentication and authorization to your FastAPI application using GL-IAM with a self-managed PostgreSQL user store.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- PostgreSQL database running locally

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/fastapi-postgresql/
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

   Output:
   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

## Test the API

```bash
# 1. Health check (public)
curl http://localhost:8000/health

# 2. Register a new user
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "display_name": "Test User"}'

# 3. Login to get access token
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}'

# 4. Access protected endpoint with token
curl http://localhost:8000/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 5. Access member-only endpoint
curl http://localhost:8000/member-only \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Understanding the Code

### Authentication Flow

```
Register -> Create User -> Set Password -> Assign Role
Login -> Authenticate -> Get Token
Request -> Validate Token -> Get User -> Check Role -> Allow/Deny
```

### Role Hierarchy

GL-IAM uses a role hierarchy where higher roles include lower role permissions:

| Dependency | Allows |
|------------|--------|
| `require_org_member()` | ORG_MEMBER, ORG_ADMIN, PLATFORM_ADMIN |
| `require_org_admin()` | ORG_ADMIN, PLATFORM_ADMIN |
| `require_platform_admin()` | PLATFORM_ADMIN only |

### Key Dependencies

| Dependency | Purpose |
|------------|---------|
| `get_current_user` | Validates token and returns User object |
| `require_org_member()` | Ensures user has at least ORG_MEMBER role |
| `require_org_admin()` | Ensures user has at least ORG_ADMIN role |
| `require_platform_admin()` | Ensures user has PLATFORM_ADMIN role |
| `get_iam_gateway()` | Gets the IAMGateway instance for direct operations |

## Reference

This example is based on the [GL-IAM FastAPI with PostgreSQL Provider tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/fastapi-with-postgresql-provider).
