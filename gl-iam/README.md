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

### Django Provider Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [django-postgresql](examples/django-postgresql/) | Self-managed user store | Full control, includes register/login |
| [django-keycloak](examples/django-keycloak/) | Keycloak integration | Enterprise SSO, OIDC/SAML, federation |
| [django-stackauth](examples/django-stackauth/) | Stack Auth integration | Modern auth, minimal infrastructure |

Each Django example demonstrates three view patterns:
- **FBV + Decorators**: `@gl_iam_login_required`, `@require_org_member()`
- **CBV + Mixins**: `GLIAMLoginRequiredMixin`, `OrgMemberRequiredMixin`
- **DRF APIView**: `GLIAMAuthentication`, `IsOrgMember` permission

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

### API Key & Integration Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [api-key-hierarchy](examples/api-key-hierarchy/) | API key management with SOLID patterns | 3-tier API keys, scope-based authorization |
| [third-party-integration](examples/third-party-integration/) | Full GitHub OAuth flow with pluggable connectors | Encrypted storage, multi-account, token revocation |

## SIMI Pattern

All examples demonstrate the **Single Interface Multiple Implementation (SIMI)** pattern. The same GL-IAM dependencies work regardless of which provider you use:

**FastAPI:**
```python
from gl_iam.fastapi import get_current_user, require_org_member

@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"user": user.email}
```

**Django (FBV):**
```python
from gl_iam.django import gl_iam_login_required, require_org_member

@gl_iam_login_required
@require_org_member()
def protected(request):
    return JsonResponse({"user": request.gl_iam_user.email})
```

**Django (DRF):**
```python
from gl_iam.django.drf import GLIAMAuthentication, IsOrgMember

class ProtectedView(APIView):
    authentication_classes = [GLIAMAuthentication]
    permission_classes = [IsOrgMember]

    def get(self, request):
        return Response({"user": request.gl_iam_user.email})
```

Only the provider configuration changes between examples.
