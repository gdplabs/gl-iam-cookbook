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

### Agent Delegation Examples

| Example | Description | Use Case |
|---------|-------------|----------|
| [agent-delegation-fastapi](examples/agent-delegation-fastapi/) | Core agent delegation with FastAPI | Register agents, delegate authority, scope-protected endpoints |
| [agent-delegation-django](examples/agent-delegation-django/) | Core agent delegation with Django | FBV, CBV, and DRF patterns for agent endpoints |
| [agent-delegation-chain](examples/agent-delegation-chain/) | Multi-hop delegation chains | Scope narrowing, chain inspection, orchestrator→worker delegation |
| [agent-scope-constraints](examples/agent-scope-constraints/) | Resource constraint validators | String equality, set subset, numeric LTE constraints |
| [agent-lifecycle](examples/agent-lifecycle/) | Agent suspend, revoke & audit | Lifecycle management, audit event capture |
| [agent-cross-service](examples/agent-cross-service/) | Cross-service delegation | Two-service setup, minimal gateway for receiving service |
| [agent-keycloak](examples/agent-keycloak/) | Agent delegation with Keycloak | Keycloak user auth + GL-IAM agent delegation |
| [agent-stackauth](examples/agent-stackauth/) | Agent delegation with Stack Auth | Stack Auth token bridge to GL-IAM delegation tokens |

### SSO Partner Registry Examples

Based on a real product requirement: **Lokadata x GLChat SSO** — enabling automatic user authentication when GLChat is embedded as a widget inside a partner website.

| Example | Description | Use Case |
|---------|-------------|----------|
| [sso-token-exchange](examples/sso-token-exchange/) | Server-side HMAC token exchange SSO (Option A - Recommended) | Multiple partners, key rotation, partner lifecycle |
| [sso-jwt-bridge](examples/sso-jwt-bridge/) | JWT-signed token SSO (Option B - Simpler) | Single trusted partner, simple setup |

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
