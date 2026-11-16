# FastAPI with Hexclave Provider

> **Error handling v1.2:** This example requires `gl-iam>=0.3.25,<0.4.0`
> from PyPI and Python 3.12 or 3.13. SDK failures use canonical
> `error_code`/`message` fields and recovery guidance. Read the
> [migration and installation notes](../../ERROR_HANDLING.md) before running it.

This example shows how to use GL-IAM with [Hexclave](https://hexclave.com/) (formerly Stack Auth) as your identity provider. It demonstrates the SIMI (Single Interface Multiple Implementation) pattern - the same GL-IAM FastAPI dependencies work regardless of which provider you use.

> **Naming note:** Hexclave is the new name of Stack Auth. The GL-IAM provider keeps its Stack Auth name: install `gl-iam[fastapi,stackauth]` and use `StackAuthProvider` / `StackAuthConfig`.

**When to use Hexclave:**
- Modern applications with straightforward auth requirements
- Quick setup with managed authentication
- Projects needing user-friendly authentication UI out of the box
- Teams wanting minimal infrastructure to manage

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- A Hexclave project ([Cloud](https://app.hexclave.com/) or [self-hosted](https://docs.hexclave.com))
- Hexclave API keys (Project ID, Publishable Client Key, Secret Server Key)

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/gdplabs/gl-iam-cookbook.git
   cd gl-iam-cookbook/traditional-iam/fastapi-hexclave/
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

3. **Set up Hexclave**

   **Option A: Hexclave Cloud**

   1. Go to the [Hexclave Dashboard](https://app.hexclave.com/) and create a new project
   2. Note your **Project ID**, **Publishable Client Key**, and **Secret Server Key**
   3. Go to **Team Settings** → turn on **"Create a personal team for each user on sign-up"**

   **Option B: Self-Hosted**

   **Prerequisites for self-hosting:**
   - Node.js v20+
   - pnpm v9+
   - Docker
   - 24GB+ RAM recommended for development

   ```bash
   git clone https://github.com/hexclave/hexclave.git && cd hexclave
   pnpm install && pnpm build:packages && pnpm codegen
   pnpm restart-deps && pnpm dev
   ```

   Once running:
   - Dashboard: `http://localhost:8100`
   - API: `http://localhost:8102`

   The `internal` project has team auto-creation pre-enabled. Use these credentials:
   ```
   Project ID: internal
   Publishable Client Key: this-publishable-client-key-is-for-local-development-only
   Secret Server Key: this-secret-server-key-is-for-local-development-only
   ```

   > For production deployment, see the [Hexclave documentation](https://docs.hexclave.com).

4. **Configure environment**

   The setup script already creates `.env` from `.env.example`. Edit it with your Hexclave settings:

   **For Hexclave Cloud:**
   ```bash
   HEXCLAVE_API_URL=https://api.hexclave.com
   HEXCLAVE_PROJECT_ID=your-project-id
   HEXCLAVE_PUBLISHABLE_CLIENT_KEY=pck_your_key
   HEXCLAVE_SECRET_SERVER_KEY=ssk_your_key
   ```

   **For Self-Hosted (development):**
   ```bash
   HEXCLAVE_API_URL=http://localhost:8102
   HEXCLAVE_PROJECT_ID=internal
   HEXCLAVE_PUBLISHABLE_CLIENT_KEY=this-publishable-client-key-is-for-local-development-only
   HEXCLAVE_SECRET_SERVER_KEY=this-secret-server-key-is-for-local-development-only
   ```

5. **Run the server**

   ```bash
   uv run main.py
   ```

   Output:
   ```
   Connected to Hexclave at http://localhost:8102
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

## Getting Access Tokens

**Sign up a user** (replace the URL with `https://api.hexclave.com` for Hexclave Cloud):

```bash
# Load your .env values into the shell
export $(grep -v '^#' .env | xargs)

curl -s -X POST $HEXCLAVE_API_URL/api/v1/auth/password/sign-up \
  -H "Content-Type: application/json" \
  -H "x-stack-access-type: client" \
  -H "x-stack-project-id: $HEXCLAVE_PROJECT_ID" \
  -H "x-stack-publishable-client-key: $HEXCLAVE_PUBLISHABLE_CLIENT_KEY" \
  -d '{"email": "test@example.com", "password": "SecurePass123", "verification_callback_url": "http://localhost:3000/verify"}'
```

Copy the `access_token` from the response.

**Token expired?** Access tokens are short-lived. Sign in again with the included `get_token.py` script:

```bash
# Interactive mode (prompts for email/password)
uv run get_token.py

# With arguments
uv run get_token.py --email test@example.com --password SecurePass123
```

Or call the sign-in endpoint directly:

```bash
curl -s -X POST $HEXCLAVE_API_URL/api/v1/auth/password/sign-in \
  -H "Content-Type: application/json" \
  -H "x-stack-access-type: client" \
  -H "x-stack-project-id: $HEXCLAVE_PROJECT_ID" \
  -H "x-stack-publishable-client-key: $HEXCLAVE_PUBLISHABLE_CLIENT_KEY" \
  -d '{"email": "test@example.com", "password": "SecurePass123"}'
```

**From a React/Next.js frontend:**

```typescript
import { useUser } from "@hexclave/next";

function MyComponent() {
  const user = useUser();

  async function callAPI() {
    const token = await user.getAccessToken();
    const res = await fetch("http://localhost:8000/me", {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  }
}
```

## Test the API

```bash
TOKEN="<paste access_token here>"

# Health check (public)
curl http://localhost:8000/health
# {"status":"healthy","provider":"hexclave"}

# Get user profile (authenticated)
curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# {"id":"...","email":"test@example.com","display_name":null,"roles":["admin"]}

# Member area (requires team_member or team_admin)
curl http://localhost:8000/member-area -H "Authorization: Bearer $TOKEN"
# {"message":"Welcome test@example.com!","access_level":"member"}

# Admin area (requires team_admin)
curl http://localhost:8000/admin-area -H "Authorization: Bearer $TOKEN"
# {"message":"Welcome Admin test@example.com!","access_level":"admin"}
```

## How Roles Work

GL-IAM maps Hexclave **team permissions** to standard roles:

| Hexclave      | GL-IAM       | Passes                                        |
| ------------- | ------------ | --------------------------------------------- |
| `team_admin`  | `ORG_ADMIN`  | `require_org_member()`, `require_org_admin()` |
| `team_member` | `ORG_MEMBER` | `require_org_member()`                        |

When "Create a personal team for each user on sign-up" is enabled, each user gets a personal team with `team_admin` on sign-up — so roles work automatically.

GL-IAM reads roles from the user's **selected team** (`user.selected_team_id → team → permissions`). If the user has no selected team, no roles are returned.

### Troubleshooting: `/me` returns empty roles

If `/me` returns `"roles": []` and `/member-area` returns 403, your user has no team. This happens when "Create a personal team for each user on sign-up" is not enabled in your Hexclave project.

**Fix — Option A:** Enable it in the Hexclave dashboard → **Team Settings**.

**Fix — Option B:** Create a team manually:

```bash
# Load your .env values into the shell
export $(grep -v '^#' .env | xargs)

USER_ID="<user_id from sign-up response>"

# Create team with user as creator (auto-grants team_admin)
TEAM_ID=$(curl -s -X POST $HEXCLAVE_API_URL/api/v1/teams \
  -H "Content-Type: application/json" \
  -H "x-stack-access-type: server" \
  -H "x-stack-project-id: $HEXCLAVE_PROJECT_ID" \
  -H "x-stack-secret-server-key: $HEXCLAVE_SECRET_SERVER_KEY" \
  -d "{\"display_name\": \"Default Team\", \"creator_user_id\": \"$USER_ID\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Set user's active team
curl -s -X PATCH "$HEXCLAVE_API_URL/api/v1/users/$USER_ID" \
  -H "Content-Type: application/json" \
  -H "x-stack-access-type: server" \
  -H "x-stack-project-id: $HEXCLAVE_PROJECT_ID" \
  -H "x-stack-secret-server-key: $HEXCLAVE_SECRET_SERVER_KEY" \
  -d "{\"selected_team_id\": \"$TEAM_ID\"}"
```

Then sign in again to get a fresh token.

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
| fastapi-postgresql | NativeProvider | `NativeConfig` |
| fastapi-keycloak | KeycloakProvider | `KeycloakConfig` |
| **fastapi-hexclave** (Hexclave) | StackAuthProvider | `StackAuthConfig` |

### Provider Setup

```python
config = StackAuthConfig(
    error_policy="typed",
    base_url=os.getenv("HEXCLAVE_API_URL", "http://localhost:8102"),
    project_id=os.getenv("HEXCLAVE_PROJECT_ID"),
    publishable_client_key=os.getenv("HEXCLAVE_PUBLISHABLE_CLIENT_KEY"),
    secret_server_key=os.getenv("HEXCLAVE_SECRET_SERVER_KEY"),
)
provider = StackAuthProvider(config)
gateway = IAMGateway.from_fullstack_provider(provider)
set_iam_gateway(gateway, default_organization_id=os.getenv("HEXCLAVE_PROJECT_ID"))
```

1. `StackAuthProvider` connects GL-IAM to your Hexclave project (the provider keeps its Stack Auth name)
2. `IAMGateway.from_fullstack_provider()` creates a unified auth gateway
3. `get_current_user` validates the Hexclave token and returns a `User`
4. `require_org_member()` enforces that the user has the `ORG_MEMBER` role (or higher)

### Token Flow

```
Frontend -> Hexclave SDK -> Access Token
                            |
Backend -> StackAuthProvider validates token -> GL-IAM User object
                                                |
                                         Role/Permission checks
```

### Configuration Reference

| Parameter | Env var | Required | Description |
|-----------|---------|----------|-------------|
| `base_url` | `HEXCLAVE_API_URL` | No | Hexclave API URL (default: `http://localhost:8102`) |
| `project_id` | `HEXCLAVE_PROJECT_ID` | Yes | Your Hexclave project identifier |
| `publishable_client_key` | `HEXCLAVE_PUBLISHABLE_CLIENT_KEY` | Yes | Public key for client-side access |
| `secret_server_key` | `HEXCLAVE_SECRET_SERVER_KEY` | No* | Secret key for server-side token validation |
| `timeout` | — | No | HTTP request timeout in seconds (default: 30) |

*`secret_server_key` is required for server-side token validation in production.

### Hexclave Concepts to GL-IAM Mapping

| Hexclave | GL-IAM |
|----------|--------|
| Team | Organization |
| Selected Team | User's active organization context |
| Permission (`team_admin`, `team_member`) | Role |
| User | User |
| Access Token | Auth Token |

## Next Steps

- [fastapi-hexclave-google-signin](../fastapi-hexclave-google-signin/) - Sign in with Google via Hexclave
- [rbac-showcase](../rbac-showcase/) - RBAC demo with multi-provider support
- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
