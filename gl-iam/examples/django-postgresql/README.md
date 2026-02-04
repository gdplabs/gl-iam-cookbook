# Django with PostgreSQL Provider

Add authentication and authorization to your Django application using GL-IAM with a self-managed PostgreSQL user store.

This example demonstrates **three different Django view patterns** with GL-IAM:

| Pattern | Auth | RBAC |
|---------|------|------|
| FBV + Decorators | `@gl_iam_login_required` | `@require_org_member()` |
| CBV + Mixins | `GLIAMLoginRequiredMixin` | `OrgMemberRequiredMixin` |
| DRF APIView | `GLIAMAuthentication` | `IsOrgMember` permission |

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- PostgreSQL database running locally

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/django-postgresql/
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
   uv run python manage.py runserver
   ```

   Output:
   ```
   GL-IAM gateway initialized with PostgreSQL provider
   Starting development server at http://127.0.0.1:8000/
   ```

## Test the API

```bash
# 1. Health check (public)
curl http://localhost:8000/health/

# 2. Register a new user (automatically assigned ORG_MEMBER role)
curl -X POST http://localhost:8000/api/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "display_name": "Test User"}'

# 3. Login to get access token
TOKEN=$(curl -s -X POST http://localhost:8000/api/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')

echo $TOKEN

# 4. Access protected endpoints (all three patterns work identically)

# FBV pattern
curl http://localhost:8000/api/fbv/me/ \
  -H "Authorization: Bearer $TOKEN"

# CBV pattern
curl http://localhost:8000/api/cbv/me/ \
  -H "Authorization: Bearer $TOKEN"

# DRF pattern
curl http://localhost:8000/api/drf/me/ \
  -H "Authorization: Bearer $TOKEN"

# 5. Access member-only endpoint (works - user has ORG_MEMBER role)
curl http://localhost:8000/api/member-area/ \
  -H "Authorization: Bearer $TOKEN"

# 6. Access admin endpoint (fails - user only has ORG_MEMBER role)
curl http://localhost:8000/api/admin-area/ \
  -H "Authorization: Bearer $TOKEN"
# Expected: 403 Forbidden
```

## Assigning Admin Role

New users are registered with `ORG_MEMBER` role by default. To test admin endpoints, you need to upgrade a user to `ORG_ADMIN`.

**Option A: Via SQL (recommended for testing)**

```bash
# Connect to PostgreSQL
docker exec -it postgres psql -U postgres -d gliam

# Find your user ID
SELECT id, email FROM users;

# Assign ORG_ADMIN role (replace USER_ID and ORG_ID with actual values)
INSERT INTO user_roles (user_id, role, organization_id)
VALUES ('USER_ID', 'admin', 'ORG_ID')
ON CONFLICT (user_id, role, organization_id) DO NOTHING;

# Verify
SELECT * FROM user_roles WHERE user_id = 'USER_ID';
```

> **Note**: After assigning a new role, the user must log in again to get a new token with updated roles.

**Option B: Via API (if you add an admin endpoint)**

You can add an admin endpoint to assign roles programmatically. See the `assign_role` method in `gateway.user_store`.

## Understanding the Code

### Gateway Initialization (apps.py)

Unlike FastAPI's lifespan context manager, Django uses `AppConfig.ready()`:

```python
class ApiConfig(AppConfig):
    def ready(self):
        config = PostgreSQLUserStoreConfig(
            database_url=os.getenv("DATABASE_URL"),
            secret_key=os.getenv("SECRET_KEY"),
            enable_auth_hosting=True,
            auto_create_tables=True,
        )
        provider = PostgreSQLProvider(config)
        gateway = IAMGateway.from_fullstack_provider(provider)
        set_iam_gateway(gateway)
```

### Three View Patterns

**1. Function-Based Views with Decorators:**
```python
@gl_iam_login_required
@require_org_member()
def member_area_fbv(request):
    user = request.gl_iam_user
    return JsonResponse({"message": f"Welcome {user.email}!"})
```

**2. Class-Based Views with Mixins:**
```python
class MemberAreaCBV(OrgMemberRequiredMixin, View):
    def get(self, request):
        user = request.gl_iam_user
        return JsonResponse({"message": f"Welcome {user.email}!"})
```

**3. DRF APIView:**
```python
class MemberAreaAPIView(APIView):
    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsOrgMember]

    def get(self, request):
        user = request.gl_iam_user
        return Response({"message": f"Welcome {user.email}!"})
```

### Role Hierarchy

GL-IAM uses a role hierarchy where higher roles include lower role permissions:

| Dependency | Allows |
|------------|--------|
| `require_org_member()` / `IsOrgMember` | ORG_MEMBER, ORG_ADMIN, PLATFORM_ADMIN |
| `require_org_admin()` / `IsOrgAdmin` | ORG_ADMIN, PLATFORM_ADMIN |
| `require_platform_admin()` / `IsPlatformAdmin` | PLATFORM_ADMIN only |

### Available Endpoints

| Pattern | Endpoint | Access |
|---------|----------|--------|
| Public | `/health/` | Public |
| Public | `/api/register/` | Public |
| Public | `/api/login/` | Public |
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

This example is based on the [GL-IAM Django with PostgreSQL Provider tutorial](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/django-with-postgresql-provider).
