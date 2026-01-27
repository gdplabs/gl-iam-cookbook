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
├── README.md                    # This file
├── .gitignore                   # Python/UV ignores
└── gl-iam/
    ├── README.md                # Prerequisites
    └── examples/
        ├── fastapi-postgresql/  # Self-managed user store
        ├── fastapi-keycloak/    # Keycloak integration
        └── fastapi-stackauth/   # Stack Auth integration
```

## Examples

| Example | Description | Provider |
|---------|-------------|----------|
| [fastapi-postgresql](gl-iam/examples/fastapi-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [fastapi-keycloak](gl-iam/examples/fastapi-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [fastapi-stackauth](gl-iam/examples/fastapi-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |

## Documentation

- [GL-IAM Documentation](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL SDK Documentation](https://gdplabs.gitbook.io/sdk)
