# SAML 2.0 Federation via Keycloak

Authenticate users from a SAML 2.0 Identity Provider through Keycloak, with GL-IAM handling authorization.

## Overview

This example demonstrates SAML 2.0 Single Sign-On where a corporate Identity Provider (IdP) authenticates users, and Keycloak translates SAML assertions into OIDC tokens that GL-IAM validates.

```
SAML IdP (Keycloak #2) ←→ Keycloak SP ←→ FastAPI + GL-IAM
```

For testing, we use a second Keycloak instance as the SAML IdP. In production, this would be **Azure AD**, **Okta**, **ADFS**, **Google Workspace**, etc.

**Key point**: The FastAPI application code is identical to any Keycloak example. SAML is entirely handled by Keycloak's Identity Brokering configuration.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker and Docker Compose
- Access to GDP Labs Gen AI SDK repository

## Quick Start

### 1. Setup

```bash
./setup.sh
# or manually:
uv sync
cp .env.example .env
```

### 2. Start Services (Two Keycloak Instances)

```bash
docker-compose up -d
```

Wait ~45 seconds for both Keycloak instances to start:
- **Keycloak SP** (port 8080): Your application's Keycloak — GL-IAM connects here
- **SAML IdP** (port 8180): Simulates corporate Identity Provider

Verify both are ready:

```bash
curl -s http://localhost:8080/health/ready | jq .
curl -s http://localhost:8180/health/ready | jq .
```

### 3. Run the Application

```bash
uv run main.py
```

Server starts at http://localhost:8000.

## Testing the SAML Flow

SAML requires a **browser-based flow** (unlike password-based auth which works with curl).

### Step 1: Get the Login URL

```bash
curl http://localhost:8000/login | jq .
```

### Step 2: Open in Browser

1. Open the `login_url` from the response in your browser
2. You'll see the Keycloak SP login page with a **"Corporate SSO (SAML)"** button
3. Click the SAML IdP button
4. You'll be redirected to the SAML IdP (port 8180) login page
5. Login with a corporate user:
   - `alice@corporate.com` / `alice123`
   - `bob@corporate.com` / `bob123`
6. After successful SAML authentication, you'll be redirected back to Keycloak SP
7. Keycloak SP issues an OIDC token

### Step 3: Test with the Token

After the SAML flow, get a token using the Keycloak SP's token endpoint. Since the SAML user has been federated into Keycloak SP, you can also use direct grant for subsequent requests:

```bash
# Note: Direct grant only works after the user has completed the initial
# browser-based SAML flow at least once (which creates the federated user)
# For first-time auth, always use the browser flow.

# Health check
curl http://localhost:8000/health
# {"status":"healthy","provider":"keycloak","federation":"saml"}
```

### Testing API Endpoints (after SAML federation)

```bash
# If you have a token from the browser flow:
curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# {"id":"...","email":"alice@corporate.com","display_name":"Alice Corporate","roles":["member"]}

curl http://localhost:8000/member-area -H "Authorization: Bearer $TOKEN"
# {"message":"Welcome alice@corporate.com!","access_level":"member"}
```

## Understanding the Code

### No SAML-Specific Code

The entire `main.py` uses standard `KeycloakProvider` — identical to the [fastapi-keycloak](../fastapi-keycloak/) example. SAML is configured in Keycloak, not in your application.

### How Keycloak Handles SAML

1. **Identity Brokering**: Keycloak SP is configured as a SAML Service Provider
2. **SAML Assertion**: The IdP sends a signed SAML assertion with user attributes
3. **Attribute Mapping**: Keycloak maps SAML attributes (email, firstName, lastName) to user fields
4. **User Federation**: First-time SAML users are automatically created in Keycloak SP
5. **Token Issuance**: Keycloak SP issues a standard OIDC token
6. **GL-IAM Validation**: `KeycloakProvider` validates the token — doesn't know the user came from SAML

### Docker Compose Architecture

| Service | Port | Role |
| --- | --- | --- |
| `saml-idp` | 8180 | SAML Identity Provider (simulates corporate IdP) |
| `keycloak-sp` | 8080 | SAML Service Provider (your Keycloak, GL-IAM connects here) |
| `keycloak-db` | — | PostgreSQL for Keycloak SP |

### Role Mapping

SAML users get the `member` role by default via the `hardcoded-role-idp-mapper`. For production, configure attribute-to-role mapping:
- SAML attribute `role=manager` → Keycloak role `admin` → GL IAM `ORG_ADMIN`
- SAML attribute `role=employee` → Keycloak role `member` → GL IAM `ORG_MEMBER`

## Adapting for Production SAML IdPs

Replace the SAML IdP Keycloak instance with your corporate IdP:

1. In Keycloak SP admin (http://localhost:8080/admin):
   - Go to **Identity Providers** → **corporate-saml-idp**
   - Update **Single Sign-On Service URL** to your IdP's SSO URL
   - Import your IdP's **metadata XML** (or configure manually)

2. In your corporate IdP:
   - Download Keycloak SP's metadata from:
     `http://localhost:8080/realms/gl-iam-saml-demo/protocol/saml/descriptor`
   - Register it as a trusted Service Provider

| IdP | Metadata URL |
| --- | --- |
| Azure AD | `https://login.microsoftonline.com/{tenant}/federationmetadata/2007-06/federationmetadata.xml` |
| Okta | Okta Admin → App → Sign On → SAML Metadata |
| ADFS | `https://{server}/FederationMetadata/2007-06/FederationMetadata.xml` |
| Google | Google Admin → Apps → SAML Apps → Download Metadata |

## Cleanup

```bash
docker-compose down -v
```

## Next Steps

- [fastapi-keycloak](../fastapi-keycloak/) — Standard Keycloak setup (no SAML)
- [ldap-keycloak](../ldap-keycloak/) — LDAP/AD federation via Keycloak
- [rbac-showcase](../rbac-showcase/) — Advanced RBAC patterns
- [GL-IAM GitBook: Enterprise Protocols](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/tutorials/traditional-iam/enterprise-protocols)
