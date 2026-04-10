# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

GL-IAM Cookbook is a collection of production-ready examples demonstrating GL-IAM (GenAI Identity and Access Management) integration with Python web frameworks. All examples follow the **SIMI pattern** (Single Interface Multiple Implementation) - the same application code works with different authentication providers by only changing configuration.

**This is a cookbook repository** - examples are meant to be copied and adapted, not used as a library. Focus on clarity and documentation over production concerns like unit tests.

## Guidelines for Examples

- **No unit tests** - This is a cookbook, not a library. Examples should be self-explanatory
- **Clear documentation** - Each example must have a comprehensive README with step-by-step instructions
- **Well-commented code** - Code should be readable and educational
- **Copy-paste friendly** - Examples should work immediately after following the README steps

### README Structure for Each Example

Each example's README should include:
1. **Overview** - What the example demonstrates
2. **Prerequisites** - Required tools, services, and setup
3. **Quick Start** - Step-by-step commands to run the example
4. **Testing the API** - curl examples for every endpoint
5. **Understanding the Code** - Explanation of key code sections
6. **Next Steps** - Links to related examples or documentation

## Design Principles

- **SOLID Principles** - Follow Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion
- **Object-Oriented Programming** - Use classes, inheritance, and composition appropriately
- **Low-Code API** - Any task should be accomplishable in 5 lines of code or less

Example of the low-code principle:
```python
# Authentication in 2 lines
@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"user": user.email}

# Role-based access in 3 lines
@app.get("/admin")
async def admin(_: None = Depends(require_org_admin()), user: User = Depends(get_current_user)):
    return {"admin": user.email}
```

## Quick Start

```bash
# All examples use UV for dependency management
cd traditional-iam/<example-name>   # or: agent-iam/<example-name>
./setup.sh  # or: uv sync

# FastAPI examples
uv run main.py

# Django examples
uv run python manage.py runserver
```

## Project Structure

```
gl-iam-cookbook/
├── traditional-iam/                   # Human users & services
│   ├── fastapi-postgresql/            # FastAPI + self-managed PostgreSQL
│   ├── fastapi-keycloak/              # FastAPI + Keycloak enterprise SSO
│   ├── fastapi-stackauth/             # FastAPI + Stack Auth
│   ├── django-postgresql/             # Django + self-managed PostgreSQL
│   ├── django-keycloak/               # Django + Keycloak enterprise SSO
│   ├── django-stackauth/              # Django + Stack Auth
│   ├── rbac-showcase/                 # RBAC demo with multi-provider support
│   ├── api-key-hierarchy/             # API key management with SOLID patterns
│   ├── dpop-keycloak/                 # DPoP token binding with Keycloak
│   ├── ldap-keycloak/                 # LDAP/AD authentication via Keycloak
│   ├── saml-keycloak/                 # SAML 2.0 federation via Keycloak
│   ├── sso-token-exchange/            # SSO token exchange flow
│   ├── sso-jwt-bridge/                # SSO JWT bridge pattern
│   ├── third-party-integration/       # Third-party service integration
│   ├── audit-trail-fastapi/           # Audit trail with FastAPI
│   └── bosa-migration/               # BOSA Core Auth → GL-IAM migration
│
├── agent-iam/                         # AI agents & delegation
│   ├── agent-delegation-fastapi/      # Agent delegation with FastAPI
│   ├── agent-delegation-django/       # Agent delegation with Django
│   ├── agent-delegation-chain/        # Agent delegation chain pattern
│   ├── agent-scope-constraints/       # Agent scope constraint patterns
│   ├── agent-lifecycle/               # Agent lifecycle management
│   ├── agent-cross-service/           # Agent cross-service authentication
│   ├── agent-keycloak/                # Agent authentication with Keycloak
│   ├── agent-stackauth/               # Agent authentication with Stack Auth
│   ├── aip-integration/               # AI Agent Platform basic setup
│   ├── aip-integration-advanced/      # AI Agent Platform advanced patterns
│   └── aip-server-integration/        # Add GL-IAM to existing AIP server
│
└── explorations/                      # Experimental prototypes
    ├── agent-iam-dashboard/           # Agent IAM dashboard
    ├── agent-iam-delegation-e2e/      # Agent IAM delegation end-to-end demo
    ├── keycloak-dpop-mtls-lab/        # DPoP + mTLS concepts lab with Keycloak
    └── token-refresh-for-long-running-agents/
```

## Architecture Patterns

### Gateway Initialization

**FastAPI** - Use lifespan context manager:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    config = PostgreSQLConfig(database_url=settings.DATABASE_URL)
    provider = PostgreSQLProvider(config)
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway)
    yield
    await provider.close()

app = FastAPI(lifespan=lifespan)
```

**Django** - Use AppConfig.ready():
```python
class ApiConfig(AppConfig):
    def ready(self):
        if "runserver" not in sys.argv:
            return
        provider = PostgreSQLProvider(config)
        gateway = IAMGateway.from_fullstack_provider(provider)
        set_iam_gateway(gateway)
```

### Role Hierarchy

Roles follow a hierarchy where higher roles inherit lower role permissions:
- `PLATFORM_ADMIN` > `ORG_ADMIN` > `ORG_MEMBER`

Authorization dependencies respect this hierarchy:
- `require_org_member()` - Allows ORG_MEMBER, ORG_ADMIN, PLATFORM_ADMIN
- `require_org_admin()` - Allows ORG_ADMIN, PLATFORM_ADMIN
- `require_platform_admin()` - PLATFORM_ADMIN only

### SIMI Pattern (Provider Switching)

The same endpoint code works with any provider - only configuration changes:

```python
# SAME CODE - works with PostgreSQL, Keycloak, StackAuth
@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"user": user.email}

# Provider is configured at startup, not in endpoint code
```

## Framework-Specific Patterns

### FastAPI Dependencies

| Dependency | Purpose |
|-----------|---------|
| `get_current_user` | Validates Bearer token, returns User |
| `require_org_member()` | Ensures ORG_MEMBER+ role |
| `require_org_admin()` | Ensures ORG_ADMIN+ role |
| `require_platform_admin()` | Ensures PLATFORM_ADMIN role |
| `get_iam_gateway()` | Access IAMGateway for direct operations |

### Django View Patterns

Three supported patterns (all examples demonstrate all three):

**FBV with decorators:**
```python
@gl_iam_login_required
@require_org_member()
def protected(request):
    return JsonResponse({"user": request.gl_iam_user.email})
```

**CBV with mixins:**
```python
class ProtectedView(GLIAMLoginRequiredMixin, OrgMemberRequiredMixin, View):
    def get(self, request):
        return JsonResponse({"user": request.gl_iam_user.email})
```

**DRF APIView:**
```python
class ProtectedView(APIView):
    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsOrgMember]
```

## Development Commands

### Running Examples

```bash
# FastAPI
cd traditional-iam/fastapi-postgresql
uv sync
uv run main.py  # http://localhost:8000

# Django
cd traditional-iam/django-postgresql
uv sync
uv run python manage.py runserver  # http://localhost:8000
```

### Prerequisites

```bash
# PostgreSQL (required for *-postgresql examples)
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=gliam \
  -p 5432:5432 postgres:15

# Keycloak (required for *-keycloak examples)
cd traditional-iam/rbac-showcase  # or any keycloak example
docker-compose up -d
```

### Testing Endpoints

```bash
# Health check (no auth)
curl http://localhost:8000/health

# Register
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "display_name": "Test User"}'

# Login (get token)
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}' | jq -r '.access_token')

# Protected endpoint
curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
```

## Configuration

### Environment Variables

Standard variables across examples (`.env.example`):
```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/gliam
SECRET_KEY=your-secret-key-min-32-characters-long
DEFAULT_ORGANIZATION_ID=org-123
```

Provider-specific (rbac-showcase):
```
PROVIDER_TYPE=keycloak|stackauth

# Keycloak
KEYCLOAK_SERVER_URL=http://localhost:8080
KEYCLOAK_REALM=gl-iam-demo
KEYCLOAK_CLIENT_ID=glchat-backend
KEYCLOAK_CLIENT_SECRET=glchat-backend-secret

# Stack Auth
STACKAUTH_BASE_URL=http://localhost:8102
STACKAUTH_PROJECT_ID=your-project-id
STACKAUTH_PUBLISHABLE_CLIENT_KEY=pk_...
STACKAUTH_SECRET_SERVER_KEY=ssk_...
```

## GL-IAM SDK

The GL-IAM SDK is sourced from the gl-sdk repository:

```toml
# pyproject.toml
[tool.uv.sources]
gl-iam = { git = "https://github.com/GDP-ADMIN/gl-sdk.git", subdirectory = "libs/gl-iam", branch = "feature/gl-iam-sdk" }
```

Features used per example:
- `gl-iam[fastapi,postgresql]` - FastAPI + PostgreSQL provider
- `gl-iam[django,postgresql]` - Django + PostgreSQL provider
- `gl-iam[fastapi,keycloak]` - FastAPI + Keycloak provider
- `gl-iam[fastapi,stackauth]` - FastAPI + Stack Auth provider

## Code Organization

Each example follows a consistent structure:

**FastAPI:**
```
example-name/
├── main.py           # FastAPI app + endpoints
├── pyproject.toml    # Dependencies
├── .env.example      # Environment template
├── setup.sh          # Setup script
└── README.md         # Documentation with curl examples
```

**Django:**
```
example-name/
├── manage.py
├── gliam_demo/
│   ├── settings.py   # Django config
│   ├── urls.py       # URL routing
│   └── api/
│       ├── apps.py   # Gateway initialization
│       └── views.py  # View implementations
├── pyproject.toml
├── .env.example
├── setup.sh
└── README.md
```

## Documentation

- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL-SDK GitBook](https://gdplabs.gitbook.io/sdk)
- Each example has a README.md with getting started, testing instructions, and code explanations
