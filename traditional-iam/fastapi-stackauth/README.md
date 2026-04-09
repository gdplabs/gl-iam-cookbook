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
      - `$admin` (self-hosted) or `team_admin` (cloud) - Administrator role (maps to GL-IAM ORG_ADMIN)
      - `$member` (self-hosted) or `team_member` (cloud) - Member role (maps to GL-IAM ORG_MEMBER)

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

## Important: Team Selection Required for Role Mapping

**Users must have a selected team for GL-IAM to read their roles.**

This is the most common issue when working with Stack Auth and GL-IAM. See the flow below:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     How GL-IAM Reads Stack Auth Roles                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. User authenticates with Stack Auth (via frontend SDK)                  │
│     ↓                                                                       │
│  2. User gets access token                                                  │
│     ↓                                                                       │
│  3. User calls /me with Bearer token                                        │
│     ↓                                                                       │
│  4. GL-IAM validates token with Stack Auth                                  │
│     ↓                                                                       │
│  5. GL-IAM reads: user.selected_team_id → team → permissions               │
│     ↓                                                                       │
│  6. Permissions mapped to roles: $admin → ORG_ADMIN, $member → ORG_MEMBER  │
│                                                                             │
│  ⚠️ If user.selected_team_id is NULL, NO roles will be returned!            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How to Ensure Users Have a Selected Team

**Option A: Enable Auto-Create Team on Signup (Recommended)**

In Stack Auth Dashboard → Project Settings, enable:
- **"Auto-create team when user signs up"**

This automatically:
1. Creates a personal team for each new user
2. Adds the user to their team
3. Sets the team as `selected_team`
4. Grants `$admin` permission to the user

**Option B: Manual Team Selection After Adding to Team**

If you manually add a user to a team via the Stack Auth dashboard:

1. Admin creates a team in Stack Auth dashboard
2. Admin adds user to the team
3. Admin assigns permissions (`$admin` or `$member`)
4. **User must select the team** - This is the critical step!

The user can select a team via:
- Stack Auth frontend SDK: User chooses team from team switcher
- Stack Auth API: Call `PATCH /api/v1/users/{user_id}` with `{ "selected_team_id": "team-id" }`

**Option C: Auto-Select Team via Server API During Registration**

If you're creating users via Stack Auth Server API, automatically set their selected team:

```bash
# After creating user and adding to team:
curl -X PATCH "https://your-stack-auth.com/api/v1/users/{user_id}" \
  -H "x-stack-access-type: server" \
  -H "x-stack-project-id: your-project-id" \
  -H "x-stack-secret-server-key: your-secret-key" \
  -H "Content-Type: application/json" \
  -d '{"selected_team_id": "your-team-id"}'
```

### Verifying User Has Selected Team

Check the user's data in Stack Auth:

```bash
# Get user info
curl -H "Authorization: Bearer $TOKEN" \
  "$STACKAUTH_BASE_URL/api/v1/users/me"
```

Look for:
- `selected_team_id`: Should be a valid team UUID (not `null`)
- `selected_team`: Should contain team object (not `null`)

If `selected_team_id` is `null`, the user has no role context and GL-IAM will return empty roles.

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

# Access member area (requires team_member permission)
curl http://localhost:8000/member-area \
  -H "Authorization: Bearer $TOKEN"

# Access admin area (requires team_admin permission)
curl http://localhost:8000/admin-area \
  -H "Authorization: Bearer $TOKEN"
```

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
| fastapi-postgresql | PostgreSQLProvider | `PostgreSQLConfig` |
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
| `$admin` / `team_admin` | `admin` | ORG_ADMIN |
| `$member` / `team_member` | `member` | ORG_MEMBER |

> **Important**: Self-hosted Stack Auth uses `$admin` and `$member` permission IDs, while Stack Auth Cloud uses `team_admin` and `team_member`. GL-IAM handles both formats.

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
| Permission (`$admin`, `$member`) | Role |
| User | User |
| Access Token | Auth Token |