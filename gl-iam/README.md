# GL-IAM Examples

Welcome to the **GL-IAM Examples** - sample code for integrating GL-IAM authentication and authorization into your applications.

## Prerequisites

1. **Python 3.11+** - Can be [installed via UV](https://docs.astral.sh/uv/guides/install-python/).
2. **UV** - Please check https://docs.astral.sh/uv/ on how to install it.
3. **gcloud CLI** - Please see https://cloud.google.com/sdk/docs/install on how to install it.
   - Once installed, please login using `gcloud auth login`.

## Getting Started

Check each subfolder in [examples](./examples/) folder for specific setup instructions:

| Example | Description | Use Case |
|---------|-------------|----------|
| [fastapi-postgresql](examples/fastapi-postgresql/) | Self-managed user store | Full control over user data, simple deployments |
| [fastapi-keycloak](examples/fastapi-keycloak/) | Keycloak integration | Enterprise SSO, OIDC/SAML, federation |
| [fastapi-stackauth](examples/fastapi-stackauth/) | Stack Auth integration | Modern auth, minimal infrastructure |

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
