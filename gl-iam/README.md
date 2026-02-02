# GL-IAM Examples

Welcome to the **GL-IAM Examples** - sample code for integrating GL-IAM authentication and authorization into your applications.

## Prerequisites

1. **Python 3.11+** - Can be [installed via UV](https://docs.astral.sh/uv/guides/install-python/).
2. **UV** - Please check https://docs.astral.sh/uv/ on how to install it.
3. **Docker** - Required for running PostgreSQL/Keycloak containers.

## Getting Started

Check each subfolder in [examples](./examples/) folder for specific setup instructions:

### FastAPI Provider Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [fastapi-postgresql](examples/fastapi-postgresql/) | Self-managed user store | Full control over user data, simple deployments |
| [fastapi-keycloak](examples/fastapi-keycloak/) | Keycloak integration | Enterprise SSO, OIDC/SAML, federation |
| [fastapi-stackauth](examples/fastapi-stackauth/) | Stack Auth integration | Modern auth, minimal infrastructure |

### AIP (AI Agent Platform) Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [aip-server-integration](examples/aip-server-integration/) | Add GL-IAM to existing AIP server | Unified auth (Bearer + API key), backward compatible |
| [aip-integration](examples/aip-integration/) | Secure agent APIs (basic) | New agent APIs from scratch |
| [aip-integration-advanced](examples/aip-integration-advanced/) | Advanced GL-IAM patterns | Role-based tools, user-scoped memory, RBAC config |

### RBAC Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [rbac-showcase](examples/rbac-showcase/) | Multi-provider RBAC demo | Role mapping, hierarchy, provider comparison |

## SIMI Pattern

All examples demonstrate the **Single Interface Multiple Implementation (SIMI)** pattern. The same GL-IAM FastAPI dependencies work regardless of which provider you use:

```python
# Same code works with any provider
from gl_iam.fastapi import get_current_user, require_org_admin

@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"user": user.email}
```

Only the provider configuration changes between examples.
