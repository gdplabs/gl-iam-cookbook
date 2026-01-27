# FastAPI with Keycloak Provider

This example shows how to use GL-IAM with Keycloak as your identity provider. It demonstrates the SIMI (Single Interface Multiple Implementation) pattern - the same GL-IAM FastAPI dependencies work regardless of which provider you use.

**When to use Keycloak:**
- Enterprise environments with existing Keycloak infrastructure
- Need for advanced identity features (SSO, MFA, federation)
- Requirements for OIDC/SAML protocol support
- Centralized identity management across multiple applications

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- Docker and Docker Compose installed
- No external dependencies needed - Keycloak runs entirely in Docker

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/fastapi-keycloak/
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

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your settings (defaults work with docker-compose)
   ```

4. **Start Keycloak**

   ```bash
   docker-compose up -d
   ```

   Wait for Keycloak to be healthy (may take 30-60 seconds on first start):

   ```bash
   docker-compose logs -f keycloak
   ```

   Look for: `Keycloak ... started`

   You can access the admin console at http://localhost:8080/admin with credentials `admin` / `admin`.

5. **Run the server**

   ```bash
   uv run main.py
   ```

   Output:
   ```
   Connected to Keycloak at http://localhost:8080
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

## Demo Users

The pre-configured realm includes these test users:

| Email | Password | Roles |
|-------|----------|-------|
| user@example.com | user123 | member |
| admin@example.com | admin123 | admin, member |

## Test the API

```bash
# Get token using Resource Owner Password Grant (for testing)
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-demo/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=glchat-backend" \
  -d "client_secret=glchat-backend-secret" \
  -d "grant_type=password" \
  -d "username=user@example.com" \
  -d "password=user123" | jq -r '.access_token')

echo $TOKEN

# Health check (public)
curl http://localhost:8000/health

# Get user profile (authenticated)
curl http://localhost:8000/me \
  -H "Authorization: Bearer $TOKEN"

# Access member area
curl http://localhost:8000/member-area \
  -H "Authorization: Bearer $TOKEN"

# Access admin area (will fail for regular user)
curl http://localhost:8000/admin-area \
  -H "Authorization: Bearer $TOKEN"
```

### Test with Admin User

```bash
# Get admin token
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-demo/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=glchat-backend" \
  -d "client_secret=glchat-backend-secret" \
  -d "grant_type=password" \
  -d "username=admin@example.com" \
  -d "password=admin123" | jq -r '.access_token')

# Access admin area (should succeed)
curl http://localhost:8000/admin-area \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

> **Note:** The Resource Owner Password Grant is used here for testing simplicity. In production, use Authorization Code Flow with PKCE.

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
| **fastapi-keycloak** | KeycloakProvider | `KeycloakConfig` |
| fastapi-stackauth | StackAuthProvider | `StackAuthConfig` |

### Token Flow

```
Frontend -> Keycloak Login -> Access Token
                              |
Backend -> KeycloakProvider validates token -> GL-IAM User object
                                               |
                                        Role/Permission checks
```

### Standard Role Mapping

Keycloak realm roles are automatically mapped to GL-IAM standard roles:

| Keycloak Role | GL-IAM Standard Role |
|---------------|---------------------|
| admin | ORG_ADMIN |
| member | ORG_MEMBER |

## Cleanup

```bash
docker-compose down -v
```

## Reference

This example is based on the [GL-IAM FastAPI with Keycloak Provider tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/fastapi-with-keycloak-provider).
