# Django with Keycloak Provider

This example shows how to use GL-IAM with Keycloak as your identity provider. It demonstrates the SIMI (Single Interface Multiple Implementation) pattern - the same GL-IAM Django views work regardless of which provider you use.

**When to use Keycloak:**
- Enterprise environments with existing Keycloak infrastructure
- Need for advanced identity features (SSO, MFA, federation)
- Requirements for OIDC/SAML protocol support
- Centralized identity management across multiple applications

This example demonstrates **three different Django view patterns** with GL-IAM:

| Pattern | Auth | RBAC |
|---------|------|------|
| FBV + Decorators | `@gl_iam_login_required` | `@require_org_member()` |
| CBV + Mixins | `GLIAMLoginRequiredMixin` | `OrgMemberRequiredMixin` |
| DRF APIView | `GLIAMAuthentication` | `IsOrgMember` permission |

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- Docker and Docker Compose installed
- No external dependencies needed - Keycloak runs entirely in Docker

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/django-keycloak/
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

3. **Configure environment** (optional)

   The setup script already creates `.env` from `.env.example`. To customize:

   ```bash
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
   uv run python manage.py runserver
   ```

   Output:
   ```
   GL-IAM gateway connected to Keycloak at http://localhost:8080
   Starting development server at http://127.0.0.1:8000/
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
curl http://localhost:8000/health/

# Get user profile (all three patterns work identically)
curl http://localhost:8000/api/fbv/me/ -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/cbv/me/ -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/drf/me/ -H "Authorization: Bearer $TOKEN"

# Access member area
curl http://localhost:8000/api/member-area/ -H "Authorization: Bearer $TOKEN"

# Access admin area (will fail for regular user)
curl http://localhost:8000/api/admin-area/ -H "Authorization: Bearer $TOKEN"
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
curl http://localhost:8000/api/admin-area/ -H "Authorization: Bearer $ADMIN_TOKEN"
```

> **Note:** The Resource Owner Password Grant is used here for testing simplicity. In production, use Authorization Code Flow with PKCE.

## Understanding the Code

### Gateway Initialization (apps.py)

Unlike FastAPI's lifespan context manager, Django uses `AppConfig.ready()`:

```python
class ApiConfig(AppConfig):
    def ready(self):
        config = KeycloakConfig(
            server_url=os.getenv("KEYCLOAK_SERVER_URL"),
            realm=os.getenv("KEYCLOAK_REALM"),
            client_id=os.getenv("KEYCLOAK_CLIENT_ID"),
            client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET"),
        )
        provider = KeycloakProvider(config=config)
        gateway = IAMGateway.from_fullstack_provider(provider)
        set_iam_gateway(gateway)
```

### SIMI Pattern (Single Interface Multiple Implementation)

The Django views are identical to other GL-IAM examples:

```python
# Same decorators/mixins - works with any provider
@gl_iam_login_required
@require_org_member()
def member_area_fbv(request):
    return JsonResponse({"message": f"Welcome {request.gl_iam_user.email}!"})
```

Only the provider configuration changes:

| Example | Provider | Configuration |
|---------|----------|---------------|
| django-postgresql | PostgreSQLProvider | `PostgreSQLConfig` |
| **django-keycloak** | KeycloakProvider | `KeycloakConfig` |
| django-stackauth | StackAuthProvider | `StackAuthConfig` |

### Standard Role Mapping

Keycloak realm roles are automatically mapped to GL-IAM standard roles:

| Keycloak Role | GL-IAM Standard Role |
|---------------|---------------------|
| admin | ORG_ADMIN |
| member | ORG_MEMBER |

### Available Endpoints

| Pattern | Endpoint | Access |
|---------|----------|--------|
| Public | `/health/` | Public |
| FBV | `/api/fbv/me/` | Authenticated |
| FBV | `/api/fbv/member-area/` | ORG_MEMBER+ |
| FBV | `/api/fbv/admin-area/` | ORG_ADMIN+ |
| FBV | `/api/fbv/platform-admin/` | PLATFORM_ADMIN |
| CBV | `/api/cbv/me/` | Authenticated |
| CBV | `/api/cbv/member-area/` | ORG_MEMBER+ |
| CBV | `/api/cbv/admin-area/` | ORG_ADMIN+ |
| CBV | `/api/cbv/platform-admin/` | PLATFORM_ADMIN |
| DRF | `/api/drf/me/` | Authenticated |
| DRF | `/api/drf/member-area/` | ORG_MEMBER+ |
| DRF | `/api/drf/admin-area/` | ORG_ADMIN+ |
| DRF | `/api/drf/platform-admin/` | PLATFORM_ADMIN |
| Alias | `/api/me/` | Authenticated |
| Alias | `/api/member-area/` | ORG_MEMBER+ |
| Alias | `/api/admin-area/` | ORG_ADMIN+ |
| Alias | `/api/platform-admin/` | PLATFORM_ADMIN |

## Cleanup

```bash
docker-compose down -v
```

## Reference

This example is based on the [GL-IAM Django with Keycloak Provider tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/django-with-keycloak-provider).
