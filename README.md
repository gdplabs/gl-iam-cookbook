# GL-IAM Cookbook

Welcome to the **GL-IAM Cookbook** - your comprehensive collection of sample code and examples for working with the GL-IAM SDK!

## Getting Started

1. **Clone the repository**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook
   ```

2. **Navigate to the specific example folder**

   ```bash
   # FastAPI examples
   cd gl-iam/examples/fastapi-postgresql  # or fastapi-keycloak, fastapi-stackauth

   # Django examples
   cd gl-iam/examples/django-postgresql   # or django-keycloak, django-stackauth
   ```

3. **Follow the README in each subfolder** for specific setup instructions and examples

## Repository Structure

```
gl-iam-cookbook/
├── README.md                        # This file
├── .gitignore                       # Python/UV ignores
└── gl-iam/
    ├── README.md                    # Prerequisites
    └── examples/
        ├── fastapi-postgresql/      # FastAPI + Self-managed user store
        ├── fastapi-keycloak/        # FastAPI + Keycloak integration
        ├── fastapi-stackauth/       # FastAPI + Stack Auth integration
        ├── django-postgresql/       # Django + Self-managed user store
        ├── django-keycloak/         # Django + Keycloak integration
        ├── django-stackauth/        # Django + Stack Auth integration
        ├── bosa-migration/          # BOSA Core Auth migration guide
        ├── aip-server-integration/  # AIP server with GL-IAM
        ├── aip-integration/         # Secure agent APIs (basic)
        ├── aip-integration-advanced/ # Secure agent APIs (advanced)
        ├── rbac-showcase/           # RBAC with multi-provider support
        ├── api-key-hierarchy/       # API key management with SOLID patterns
        ├── third-party-integration/ # Third-party OAuth with GitHub flow
        ├── agent-delegation-fastapi/ # Agent delegation with FastAPI
        ├── agent-delegation-django/  # Agent delegation with Django
        ├── agent-delegation-chain/   # Multi-hop delegation chains
        ├── agent-scope-constraints/  # Resource constraint validators
        ├── agent-lifecycle/          # Agent suspend, revoke & audit
        ├── agent-cross-service/      # Cross-service delegation
        ├── agent-keycloak/           # Agent delegation with Keycloak
        └── agent-stackauth/          # Agent delegation with Stack Auth
```

## Examples

### FastAPI Provider Examples

| Example | Description | Provider |
|---------|-------------|----------|
| [fastapi-postgresql](gl-iam/examples/fastapi-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [fastapi-keycloak](gl-iam/examples/fastapi-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [fastapi-stackauth](gl-iam/examples/fastapi-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |

### Django Provider Examples

| Example | Description | Provider |
|---------|-------------|----------|
| [django-postgresql](gl-iam/examples/django-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [django-keycloak](gl-iam/examples/django-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [django-stackauth](gl-iam/examples/django-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |

Each Django example demonstrates three view patterns:
- **FBV + Decorators**: `@gl_iam_login_required`, `@require_org_member()`
- **CBV + Mixins**: `GLIAMLoginRequiredMixin`, `OrgMemberRequiredMixin`
- **DRF APIView**: `GLIAMAuthentication`, `IsOrgMember` permission

### BOSA Migration Examples

| Example | Description | Features |
|---------|-------------|----------|
| [bosa-migration](gl-iam/examples/bosa-migration/) | Complete BOSA Core Auth migration guide | 3-tier API keys, JWT sessions, third-party integrations |

This example demonstrates migrating from legacy BOSA Core Auth to GL-IAM, including:
- **3-Tier API Key Model**: PLATFORM, ORGANIZATION, PERSONAL keys with scope-based authorization
- **User Management**: Create, authenticate, and manage users with password credentials
- **JWT Sessions**: Token-based authentication with configurable expiration
- **Third-Party Integrations**: Encrypted storage for OAuth tokens and external service credentials

### AIP (AI Agent Platform) Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [aip-server-integration](gl-iam/examples/aip-server-integration/) | Add GL-IAM to existing AIP server | Unified auth (Bearer + API key) |
| [aip-integration](gl-iam/examples/aip-integration/) | Secure agent APIs with GL-IAM (basic) | New agent APIs from scratch |
| [aip-integration-advanced](gl-iam/examples/aip-integration-advanced/) | Advanced GL-IAM patterns for agents | Role-based tools, user-scoped memory |

### RBAC Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [rbac-showcase](gl-iam/examples/rbac-showcase/) | RBAC with Keycloak and StackAuth | Role mapping, hierarchy, SIMI pattern |

### API Key & Integration Examples

| Example | Description | Features |
|---------|-------------|----------|
| [api-key-hierarchy](gl-iam/examples/api-key-hierarchy/) | API key management with SOLID patterns | 3-tier API keys, scope-based authorization |
| [third-party-integration](gl-iam/examples/third-party-integration/) | Full GitHub OAuth flow with pluggable connectors | Encrypted credential storage, multi-account support, token revocation |

### Agent Delegation Examples

| Example | Description | Features |
|---------|-------------|----------|
| [agent-delegation-fastapi](gl-iam/examples/agent-delegation-fastapi/) | Core agent delegation with FastAPI | Register agents, delegate authority, scope-protected endpoints |
| [agent-delegation-django](gl-iam/examples/agent-delegation-django/) | Core agent delegation with Django | FBV decorators, CBV mixins, DRF permission classes |
| [agent-delegation-chain](gl-iam/examples/agent-delegation-chain/) | Multi-hop delegation chains | Scope narrowing, chain inspection, orchestrator→worker |
| [agent-scope-constraints](gl-iam/examples/agent-scope-constraints/) | Resource constraint validators | String equality, set subset, numeric LTE, composite |
| [agent-lifecycle](gl-iam/examples/agent-lifecycle/) | Agent suspend, revoke & audit | Lifecycle management, audit event callback |
| [agent-cross-service](gl-iam/examples/agent-cross-service/) | Cross-service delegation | Two-service setup, minimal agent-only gateway |
| [agent-keycloak](gl-iam/examples/agent-keycloak/) | Agent delegation with Keycloak | Keycloak OIDC + GL-IAM agent delegation |
| [agent-stackauth](gl-iam/examples/agent-stackauth/) | Agent delegation with Stack Auth | StackAuth token bridge, delegation JWT conversion |

## Documentation

- [GL-IAM Gitbook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL SDK Gitbook](https://gdplabs.gitbook.io/sdk)
