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
        ├── aip-server-integration/  # AIP server with GL-IAM
        ├── aip-integration/         # Secure agent APIs (basic)
        └── aip-integration-advanced/ # Secure agent APIs (advanced)
```

## Examples

### FastAPI Provider Examples

| Example | Description | Provider |
|---------|-------------|----------|
| [fastapi-postgresql](gl-iam/examples/fastapi-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [fastapi-keycloak](gl-iam/examples/fastapi-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [fastapi-stackauth](gl-iam/examples/fastapi-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |

### AIP (AI Agent Platform) Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [aip-server-integration](gl-iam/examples/aip-server-integration/) | Add GL-IAM to existing AIP server | Unified auth (Bearer + API key) |
| [aip-integration](gl-iam/examples/aip-integration/) | Secure agent APIs with GL-IAM (basic) | New agent APIs from scratch |
| [aip-integration-advanced](gl-iam/examples/aip-integration-advanced/) | Advanced GL-IAM patterns for agents | Role-based tools, user-scoped memory |

## Documentation

- [GL-IAM Gitbook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL SDK Gitbook](https://gdplabs.gitbook.io/sdk)
