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

2. **Set UV authentication and install dependencies**

   **For Unix-based systems (Linux, macOS):**
   ```bash
   ./setup.sh
   ```

   **For Windows:**
   ```cmd
   setup.bat
   ```

   > Alternatively, set the following env vars manually:
   > ```bash
   > export UV_INDEX_GEN_AI_INTERNAL_USERNAME=oauth2accesstoken
   > export UV_INDEX_GEN_AI_INTERNAL_PASSWORD="$(gcloud auth print-access-token)"
   > uv lock
   > uv sync
   > ```

3. **Set up Stack Auth**

   **Option A: Stack Auth Cloud**

   1. Go to [Stack Auth Dashboard](https://app.stack-auth.com/)
   2. Create a new project
   3. Note your Project ID, Publishable Key, and Secret Server Key

   **Option B: Self-Hosted**

   If using the self-hosted Stack Auth instance:

   ```bash
   cd stack-auth
   pnpm install
   pnpm build:packages
   pnpm restart-deps    # Start Docker containers
   pnpm dev             # Start dev server at http://localhost:8100
   ```

   The Stack Auth API runs at `http://localhost:8102` by default.

4. **Configure Team Permissions**

   In the Stack Auth dashboard:

   1. Navigate to **Team Settings** > **Permissions**
   2. Create the following permissions (these become roles):
      - `$admin` - Administrator permission
      - `$member` - Member permission (usually default)

   > Stack Auth uses `$`-prefixed permissions as roles.

5. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your Stack Auth settings
   ```

   For Stack Auth Cloud:
   ```bash
   STACKAUTH_BASE_URL=https://api.stack-auth.com
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

**Option A: Use Stack Auth Dashboard**

1. Navigate to your user in the Stack Auth dashboard
2. Generate a test access token

**Option B: Use Stack Auth Frontend SDK**

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

# Access admin area (requires $admin permission)
curl http://localhost:8000/admin-area \
  -H "Authorization: Bearer $TOKEN"
```

Expected output for `/me`:

```json
{
  "id": "user-123",
  "email": "user@example.com",
  "display_name": "Test User",
  "roles": ["member"]
}
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

Stack Auth uses `$`-prefixed permissions which are mapped to GL-IAM standard roles:

| Stack Auth Permission | GL-IAM Standard Role |
|-----------------------|---------------------|
| `$admin` | ORG_ADMIN |
| `$member` | ORG_MEMBER |

> The `$` prefix is stripped when mapping to GL-IAM roles. So `$admin` becomes `admin` in the user's roles list, and is recognized as `ORG_ADMIN` by GL-IAM.

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
| Permission (`$admin`, `$member`) | Role |
| User | User |
| Access Token | Auth Token |

## Reference

This example is based on the [GL-IAM FastAPI with Stack Auth Provider tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/fastapi-with-stackauth-provider).
