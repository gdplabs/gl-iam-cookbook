# Django with Stack Auth Provider

This example shows how to use GL-IAM with Stack Auth as your identity provider. It demonstrates the SIMI (Single Interface Multiple Implementation) pattern - the same GL-IAM Django views work regardless of which provider you use.

**When to use Stack Auth:**
- Modern SaaS applications needing quick authentication setup
- Projects that want a managed authentication solution
- Applications requiring social login providers (Google, GitHub, etc.)
- Startups and teams preferring simplicity over self-hosting

This example demonstrates **three different Django view patterns** with GL-IAM:

| Pattern | Auth | RBAC |
|---------|------|------|
| FBV + Decorators | `@gl_iam_login_required` | `@require_org_member()` |
| CBV + Mixins | `GLIAMLoginRequiredMixin` | `OrgMemberRequiredMixin` |
| DRF APIView | `GLIAMAuthentication` | `IsOrgMember` permission |

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- A Stack Auth project (self-hosted or cloud-hosted)
- Stack Auth credentials (project ID, publishable key, secret key)

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/django-stackauth/
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
   # Edit .env with your Stack Auth settings
   ```

   You'll need to set:
   - `STACKAUTH_BASE_URL` - Your Stack Auth server URL
   - `STACKAUTH_PROJECT_ID` - Your project ID
   - `STACKAUTH_PUBLISHABLE_CLIENT_KEY` - Your publishable key (pk_...)
   - `STACKAUTH_SECRET_SERVER_KEY` - Your secret server key (ssk_...)

4. **Run the server**

   ```bash
   uv run python manage.py runserver
   ```

   Output:
   ```
   GL-IAM gateway connected to Stack Auth at http://localhost:8102
   Starting development server at http://127.0.0.1:8000/
   ```

## Test the API

To test the API, you'll need a valid Stack Auth access token. You can obtain one through:
- Stack Auth's hosted login page
- Stack Auth SDK in your frontend application
- Stack Auth's test endpoints (for development)

```bash
# Set your token (obtained from Stack Auth)
TOKEN="your-stack-auth-access-token"

# Health check (public)
curl http://localhost:8000/health/

# Get user profile (all three patterns work identically)
curl http://localhost:8000/api/fbv/me/ -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/cbv/me/ -H "Authorization: Bearer $TOKEN"
curl http://localhost:8000/api/drf/me/ -H "Authorization: Bearer $TOKEN"

# Access member area
curl http://localhost:8000/api/member-area/ -H "Authorization: Bearer $TOKEN"

# Access admin area (requires ORG_ADMIN role)
curl http://localhost:8000/api/admin-area/ -H "Authorization: Bearer $TOKEN"
```

## Understanding the Code

### Gateway Initialization (apps.py)

Unlike FastAPI's lifespan context manager, Django uses `AppConfig.ready()`:

```python
class ApiConfig(AppConfig):
    def ready(self):
        config = StackAuthConfig(
            base_url=os.getenv("STACKAUTH_BASE_URL"),
            project_id=os.getenv("STACKAUTH_PROJECT_ID"),
            publishable_client_key=os.getenv("STACKAUTH_PUBLISHABLE_CLIENT_KEY"),
            secret_server_key=os.getenv("STACKAUTH_SECRET_SERVER_KEY"),
        )
        provider = StackAuthProvider(config)
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
| django-postgresql | PostgreSQLProvider | `PostgreSQLUserStoreConfig` |
| django-keycloak | KeycloakProvider | `KeycloakConfig` |
| **django-stackauth** | StackAuthProvider | `StackAuthConfig` |

### Token Flow

```
Frontend -> Stack Auth Login -> Access Token
                                |
Backend -> StackAuthProvider validates token -> GL-IAM User object
                                                |
                                          Role/Permission checks
```

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

## Reference

This example is based on the [GL-IAM Django with Stack Auth Provider tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/django-with-stackauth-provider).
