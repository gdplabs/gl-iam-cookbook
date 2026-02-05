# FastAPI with Stack Auth Provider

This example shows how to use GL-IAM with [Stack Auth](https://stack-auth.com/) as your identity provider. It demonstrates the SIMI (Single Interface Multiple Implementation) pattern - the same GL-IAM FastAPI dependencies work regardless of which provider you use.

**When to use Stack Auth:**
- Modern applications with straightforward auth requirements
- Quick setup with managed authentication
- Projects needing user-friendly authentication UI out of the box
- Teams wanting minimal infrastructure to manage

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- A Stack Auth project (cloud or self-hosted instance)
- Stack Auth API keys (project ID, publishable key, secret server key)

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/fastapi-stackauth/
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

3. **Set up Stack Auth**

   **Option A: Stack Auth Cloud**

   1. Go to [Stack Auth Dashboard](https://app.stack-auth.com/)
   2. Create a new project
   3. Note your Project ID, Publishable Key, and Secret Server Key

   **Option B: Self-Hosted**

   If using a self-hosted Stack Auth instance:

   **Prerequisites for self-hosting:**
   - Node.js v20+
   - pnpm v9+
   - Docker
   - 24GB+ RAM recommended for development

   **Setup steps:**

   ```bash
   # Clone the Stack Auth repository
   git clone https://github.com/stack-auth/stack-auth.git
   cd stack-auth

   # Install dependencies
   pnpm install

   # Build packages and generate code
   pnpm build:packages
   pnpm codegen

   # Start Docker containers (PostgreSQL, Inbucket, etc.)
   pnpm restart-deps

   # Start the development server
   pnpm dev
   ```

   Once running:
   - Dashboard: `http://localhost:8100`
   - API: `http://localhost:8102`

   **Default development API keys** (created by `pnpm restart-deps`):
   ```bash
   STACKAUTH_PROJECT_ID=internal
   STACKAUTH_PUBLISHABLE_CLIENT_KEY=this-publishable-client-key-is-for-local-development-only
   STACKAUTH_SECRET_SERVER_KEY=this-secret-server-key-is-for-local-development-only
   ```

   > For production deployment, see the [Stack Auth documentation](https://docs.stack-auth.com).

4. **Configure Team and User**

   In the Stack Auth dashboard:

   1. **Create a Team**: Navigate to **Teams** and create a new team (e.g., "Test Team")
   2. **Add User to Team**: Add your user to the team
   3. **Assign Role**: Assign the user a role in the team:
      - `team_admin` - Administrator role (maps to GL-IAM `admin`)
      - `team_member` - Member role (maps to GL-IAM `member`)

   > **Important**: Users must have a **selected team** for roles to work. The user's active team context determines their permissions. When adding a user to a team, they automatically get `team_member` permission.

5. **Configure environment**

   The setup script already creates `.env` from `.env.example`. Edit it with your Stack Auth settings:

   **For Stack Auth Cloud:**
   ```bash
   STACKAUTH_BASE_URL=https://api.stack-auth.com
   STACKAUTH_PROJECT_ID=your-project-id
   STACKAUTH_PUBLISHABLE_CLIENT_KEY=pck_your_publishable_key
   STACKAUTH_SECRET_SERVER_KEY=ssk_your_secret_key
   ```

   **For Self-Hosted (development):**
   ```bash
   STACKAUTH_BASE_URL=http://localhost:8102
   STACKAUTH_PROJECT_ID=internal
   STACKAUTH_PUBLISHABLE_CLIENT_KEY=this-publishable-client-key-is-for-local-development-only
   STACKAUTH_SECRET_SERVER_KEY=this-secret-server-key-is-for-local-development-only
   ```

6. **Run the server**

   ```bash
   uv run main.py
   ```

   Output:
   ```
   Connected to Stack Auth at http://localhost:8102
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

## Getting Access Tokens

Stack Auth tokens are typically obtained through the frontend SDK. For testing:

**Option A: CLI Script (Recommended for Testing)**

> **Note**: You must first create a user in the Stack Auth dashboard (Users → Add User) with password authentication enabled.

Use the included `get_token.py` script to quickly get an access token:

```bash
# Interactive mode (prompts for email/password)
uv run get_token.py

# With arguments
uv run get_token.py --email user@example.com --password yourpassword

# Or set environment variables
export TEST_USER_EMAIL=user@example.com
export TEST_USER_PASSWORD=yourpassword
uv run get_token.py
```

Output:
```
Authenticating user@example.com...

============================================================
ACCESS TOKEN (copy this for curl commands):
============================================================
eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9...
============================================================

Usage:
  export TOKEN="eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9..."
  curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
```

**Option B: Use Stack Auth Dashboard**

1. Navigate to your user in the Stack Auth dashboard
2. Generate a test access token

**Option C: Use Stack Auth Frontend SDK**

In your frontend application:

```typescript
import { useUser } from "@stackframe/stack";

function MyComponent() {
  const user = useUser();

  // Get access token for API calls
  const token = await user.getAuthJson();
  console.log(token.accessToken);
}
```

## Test the API

```bash
# Set your access token
TOKEN="your-stack-auth-access-token"

# Health check (public)
curl http://localhost:8000/health

# Get user profile (authenticated)
curl http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN"

# Access member area
curl http://localhost:8000/member-area \
  -H "Authorization: Bearer $TOKEN"

# Access admin area (requires team_admin permission)
curl http://localhost:8000/admin-area \
  -H "Authorization: Bearer $TOKEN"
```

Expected output for `/me`:

```json
{
  "id": "user-123",
  "email": "user@example.com",
  "display_name": "Test User",
  "roles": ["admin", "member"]
}
```

> **Note**: The `roles` array depends on the permissions assigned to the user in their selected team. Users with `team_admin` permission will have `["admin", "member"]`, while users with only `team_member` will have `["member"]`.

## Understanding the Code

### SIMI Pattern (Single Interface Multiple Implementation)

The FastAPI dependencies are identical to other GL-IAM examples:

```python
# Same dependencies - works with any provider
user: User = Depends(get_current_user)
_: None = Depends(require_org_member())
_: None = Depends(require_org_admin())
```

Only the provider configuration changes:

| Example | Provider | Configuration |
|---------|----------|---------------|
| fastapi-postgresql | PostgreSQLProvider | `PostgreSQLUserStoreConfig` |
| fastapi-keycloak | KeycloakProvider | `KeycloakConfig` |
| **fastapi-stackauth** | StackAuthProvider | `StackAuthConfig` |

### Token Flow

```
Frontend -> Stack Auth SDK -> Access Token
                              |
Backend -> StackAuthProvider validates token -> GL-IAM User object
                                                |
                                         Role/Permission checks
```

### Standard Role Mapping

Stack Auth permissions are mapped to GL-IAM standard roles:

| Stack Auth Permission | GL-IAM Role | GL-IAM Standard Role |
|-----------------------|-------------|---------------------|
| `team_admin` | `admin` | ORG_ADMIN |
| `team_member` | `member` | ORG_MEMBER |

> Both Stack Auth Cloud and self-hosted use the same permission names (`team_admin`, `team_member`).

### Configuration Reference

| Parameter | Required | Description |
|-----------|----------|-------------|
| `base_url` | No | Stack Auth API URL (default: `http://localhost:8102`) |
| `project_id` | Yes | Your Stack Auth project identifier |
| `publishable_client_key` | Yes | Public key for client-side access |
| `secret_server_key` | No* | Secret key for server-side token validation |
| `timeout` | No | HTTP request timeout in seconds (default: 30) |

*`secret_server_key` is required for server-side token validation in production.

### Stack Auth Concepts to GL-IAM Mapping

| Stack Auth | GL-IAM |
|------------|--------|
| Team | Organization |
| Selected Team | User's active organization context |
| Permission (`team_admin`, `team_member`) | Role |
| User | User |
| Access Token | Auth Token |

