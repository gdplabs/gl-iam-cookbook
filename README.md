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
   cd gl-iam/examples/fastapi-postgresql  # or fastapi-keycloak, fastapi-stackauth
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
        ├── fastapi-postgresql/      # Self-managed user store
        ├── fastapi-keycloak/        # Keycloak integration
        ├── fastapi-stackauth/       # Stack Auth integration
        ├── bosa-migration/          # BOSA Core Auth migration guide
        ├── aip-server-integration/  # AIP server with GL-IAM
        ├── aip-integration/         # Secure agent APIs (basic)
        ├── aip-integration-advanced/ # Secure agent APIs (advanced)
        └── rbac-showcase/           # RBAC with multi-provider support
```

## Examples

### FastAPI Provider Examples

| Example | Description | Provider |
|---------|-------------|----------|
| [fastapi-postgresql](gl-iam/examples/fastapi-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [fastapi-keycloak](gl-iam/examples/fastapi-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [fastapi-stackauth](gl-iam/examples/fastapi-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |

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

## Documentation

- [GL-IAM Gitbook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL SDK Gitbook](https://gdplabs.gitbook.io/sdk)
