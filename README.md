# GL-IAM Cookbook

Welcome to the **GL-IAM Cookbook** — a collection of production-ready examples for integrating GL-IAM authentication and authorization into your applications.

## Getting Started

1. **Clone the repository**

   ```bash
   git clone https://github.com/gdplabs/gl-iam-cookbook.git
   cd gl-iam-cookbook
   ```

2. **Navigate to the example you need**

   ```bash
   # Traditional IAM examples (human users & services)
   cd traditional-iam/fastapi-postgresql

   # Agent IAM examples (AI agent delegation)
   cd agent-iam/agent-delegation-fastapi
   ```

3. **Follow the README in each subfolder** for specific setup instructions and examples

## Prerequisites

1. **Python 3.11+** — Can be [installed via UV](https://docs.astral.sh/uv/guides/install-python/).
2. **UV** — Please check https://docs.astral.sh/uv/ on how to install it.
3. **Docker** — Required for running PostgreSQL/Keycloak containers.

## Repository Structure

```
gl-iam-cookbook/
├── README.md
│
├── traditional-iam/               # Human users & services
│   ├── fastapi-postgresql/        # FastAPI + self-managed user store
│   ├── fastapi-keycloak/          # FastAPI + Keycloak enterprise SSO
│   ├── fastapi-stackauth/         # FastAPI + Stack Auth
│   ├── django-postgresql/         # Django + self-managed user store
│   ├── django-keycloak/           # Django + Keycloak enterprise SSO
│   ├── django-stackauth/          # Django + Stack Auth
│   ├── rbac-showcase/             # RBAC with multi-provider support
│   ├── api-key-hierarchy/         # API key management with SOLID patterns
│   ├── dpop-keycloak/             # DPoP token binding with Keycloak
│   ├── ldap-keycloak/             # LDAP authentication via Keycloak
│   ├── ad-keycloak/               # Active Directory authentication via Keycloak (Samba AD DC)
│   ├── saml-keycloak/             # SAML 2.0 federation via Keycloak
│   ├── sso-token-exchange/        # SSO with HMAC token exchange (SDK primitive only)
│   ├── sso-jwt-bridge/            # SSO with JWT bridge (single-partner simpler pattern)
│   ├── sso-glchat-production/     # Production-grade IdP-initiated SSO (end-to-end, all §12 gaps)
│   ├── third-party-integration/   # Third-party OAuth (GitHub flow)
│   ├── audit-trail-fastapi/       # Audit trail with FastAPI
│   └── bosa-migration/            # BOSA Core Auth migration guide
│
├── agent-iam/                     # AI agents & delegation
│   ├── agent-delegation-fastapi/  # Core agent delegation with FastAPI
│   ├── agent-delegation-django/   # Core agent delegation with Django
│   ├── agent-delegation-chain/    # Multi-hop delegation chains
│   ├── agent-scope-constraints/   # Resource constraint validators
│   ├── agent-lifecycle/           # Agent suspend, revoke & audit
│   ├── agent-cross-service/       # Cross-service delegation
│   ├── agent-keycloak/            # Agent delegation with Keycloak
│   ├── agent-stackauth/           # Agent delegation with Stack Auth
│   ├── aip-integration/           # Secure agent APIs (basic)
│   ├── aip-integration-advanced/  # Secure agent APIs (advanced)
│   └── aip-server-integration/    # Add GL-IAM to existing AIP server
│
└── explorations/                  # Experimental prototypes
    ├── agent-iam-dashboard/       # Agent IAM dashboard
    ├── agent-iam-delegation-e2e/  # Agent delegation end-to-end demo
    ├── keycloak-dpop-mtls-lab/    # DPoP + mTLS concepts lab
    └── token-refresh-for-long-running-agents/
```

## Traditional IAM Examples

For securing **human users** and **service-to-service** communication.

### Quickstart (Provider Examples)

| Example | Description | Provider |
|---------|-------------|----------|
| [fastapi-postgresql](traditional-iam/fastapi-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [fastapi-keycloak](traditional-iam/fastapi-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [fastapi-stackauth](traditional-iam/fastapi-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |
| [django-postgresql](traditional-iam/django-postgresql/) | Self-managed user store with PostgreSQL | PostgreSQLProvider |
| [django-keycloak](traditional-iam/django-keycloak/) | Enterprise identity with Keycloak | KeycloakProvider |
| [django-stackauth](traditional-iam/django-stackauth/) | Modern auth with Stack Auth | StackAuthProvider |

Each Django example demonstrates three view patterns:
- **FBV + Decorators**: `@gl_iam_login_required`, `@require_org_member()`
- **CBV + Mixins**: `GLIAMLoginRequiredMixin`, `OrgMemberRequiredMixin`
- **DRF APIView**: `GLIAMAuthentication`, `IsOrgMember` permission

### Authorization, Security & Integration

| Example | Description | Features |
|---------|-------------|----------|
| [rbac-showcase](traditional-iam/rbac-showcase/) | RBAC with multi-provider support | Role mapping, hierarchy, SIMI pattern |
| [api-key-hierarchy](traditional-iam/api-key-hierarchy/) | API key management with SOLID patterns | 3-tier API keys, scope-based authorization |
| [dpop-keycloak](traditional-iam/dpop-keycloak/) | DPoP token binding with Keycloak | Proof-of-possession, replay protection |
| [ldap-keycloak](traditional-iam/ldap-keycloak/) | LDAP authentication via Keycloak (OpenLDAP) | User Federation, group-to-role mapping |
| [ad-keycloak](traditional-iam/ad-keycloak/) | Active Directory authentication via Keycloak (Samba AD DC) | AD vendor preset, `sAMAccountName`/`objectGUID`, MSAD UAC mapper |
| [saml-keycloak](traditional-iam/saml-keycloak/) | SAML 2.0 SSO via Keycloak | Identity Brokering, attribute mapping |
| [third-party-integration](traditional-iam/third-party-integration/) | Full GitHub OAuth flow | Encrypted credential storage, multi-account support |
| [audit-trail-fastapi](traditional-iam/audit-trail-fastapi/) | Audit trail with FastAPI | Structured event logging |

### SSO Partner Registry

Based on a real product requirement: **Lokadata x GLChat SSO** — enabling automatic user authentication when GLChat is embedded as a widget inside a partner website.

| Example | Description | Features |
|---------|-------------|----------|
| [sso-token-exchange](traditional-iam/sso-token-exchange/) | Server-side HMAC token exchange (SDK primitive) | Multi-partner, key rotation, JIT provisioning |
| [sso-jwt-bridge](traditional-iam/sso-jwt-bridge/) | JWT-signed token SSO (simpler pattern) | Single trusted partner, stateless verification |
| [sso-glchat-production](traditional-iam/sso-glchat-production/) | **Production-grade IdP-initiated SSO — end-to-end demo** | 5-component topology (partner FE+BE, GLChat BE + admin + widget), Redis one-time tokens, nonce replay protection, per-`consumer_key` rate limiting, dynamic CSP `frame-ancestors`, `postMessage` token delivery, platform-admin-protected partner CRUD, secret rotation with grace period, structured audit trail, rich step-banner logs |

> `sso-token-exchange` shows the SDK primitive in isolation; `sso-glchat-production` wraps it with every production concern from [§12 of the architecture doc](https://github.com/GDP-ADMIN/gl-sdk/blob/main/libs/gl-iam/docs/architecture/IDP_VS_SP_INITIATED_SSO_COMPARISON.md) and a realistic 3-backend + 2-frontend topology you can walk through in a browser. Start there if you're adopting IdP-initiated SSO for real.

### Migration

| Example | Description | Features |
|---------|-------------|----------|
| [bosa-migration](traditional-iam/bosa-migration/) | Complete BOSA Core Auth migration guide | 3-tier API keys, JWT sessions, third-party integrations |

## Agent IAM Examples

For securing **AI agents** with delegation-based authentication.

### Core Delegation

| Example | Description | Features |
|---------|-------------|----------|
| [agent-delegation-fastapi](agent-iam/agent-delegation-fastapi/) | Core agent delegation with FastAPI | Register agents, delegate authority, scope-protected endpoints |
| [agent-delegation-django](agent-iam/agent-delegation-django/) | Core agent delegation with Django | FBV decorators, CBV mixins, DRF permission classes |
| [agent-delegation-chain](agent-iam/agent-delegation-chain/) | Multi-hop delegation chains | Scope narrowing, chain inspection, orchestrator-to-worker |
| [agent-scope-constraints](agent-iam/agent-scope-constraints/) | Resource constraint validators | String equality, set subset, numeric LTE, composite |
| [agent-lifecycle](agent-iam/agent-lifecycle/) | Agent suspend, revoke & audit | Lifecycle management, audit event callback |
| [agent-cross-service](agent-iam/agent-cross-service/) | Cross-service delegation | Two-service setup, minimal agent-only gateway |

### Provider-Specific

| Example | Description | Features |
|---------|-------------|----------|
| [agent-keycloak](agent-iam/agent-keycloak/) | Agent delegation with Keycloak | Keycloak OIDC + GL-IAM agent delegation |
| [agent-stackauth](agent-iam/agent-stackauth/) | Agent delegation with Stack Auth | StackAuth token bridge, delegation JWT conversion |

### AIP (AI Agent Platform) Integration

| Example | Description | Use Case |
|---------|-------------|----------|
| [aip-server-integration](agent-iam/aip-server-integration/) | Add GL-IAM to existing AIP server | Unified auth (Bearer + API key) |
| [aip-integration](agent-iam/aip-integration/) | Secure agent APIs with GL-IAM (basic) | New agent APIs from scratch |
| [aip-integration-advanced](agent-iam/aip-integration-advanced/) | Advanced GL-IAM patterns for agents | Role-based tools, user-scoped memory |

## SIMI Pattern

All examples demonstrate the **Single Interface Multiple Implementation (SIMI)** pattern. The same GL-IAM code works regardless of which provider you use:

```python
# SAME CODE — works with PostgreSQL, Keycloak, StackAuth
@app.get("/protected")
async def protected(user: User = Depends(get_current_user)):
    return {"user": user.email}
```

Only the provider configuration changes between examples.

## Documentation

- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL SDK GitBook](https://gdplabs.gitbook.io/sdk)
