# LDAP Authentication via Keycloak

Authenticate LDAP/Active Directory users through Keycloak's User Federation, with GL-IAM handling authorization.

## Overview

This example demonstrates how corporate LDAP users can authenticate in your application without any LDAP-specific code. Keycloak handles the LDAP protocol natively, and GL-IAM validates the OIDC tokens Keycloak issues.

```
OpenLDAP ←→ Keycloak (User Federation) ←→ FastAPI + GL-IAM
```

**Key point**: The FastAPI application code is identical to any Keycloak example. LDAP is entirely handled by Keycloak's configuration.

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

### 2. Start Services (OpenLDAP + Keycloak)

```bash
docker-compose up -d
```

Wait ~30 seconds for Keycloak to import the realm and connect to OpenLDAP.

Verify Keycloak is ready:

```bash
curl -s http://localhost:8080/health/ready | jq .
```

### 3. Sync LDAP Users

After Keycloak starts, trigger a user sync from the admin console:

1. Go to http://localhost:8080/admin (admin / admin)
2. Select realm **gl-iam-ldap-demo**
3. Go to **User federation** → **ldap**
4. Click **Synchronize all users**
5. Assign roles to synced users:
   - Go to **Users** → find `jdoe` → **Role mapping** → Assign **member**
   - Go to **Users** → find `asmith` → **Role mapping** → Assign **admin** + **member**

### 4. Run the Application

```bash
uv run main.py
```

Server starts at http://localhost:8000.

## Testing the API

### Health Check

```bash
curl http://localhost:8000/health
# {"status":"healthy","provider":"keycloak","federation":"ldap"}
```

### Authenticate an LDAP User

```bash
# Get token for LDAP user jdoe
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-ldap-demo/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=glchat-backend" \
  -d "client_secret=glchat-backend-secret" \
  -d "username=jdoe" \
  -d "password=jdoe123" | jq -r '.access_token')

echo $TOKEN
```

### Access Protected Endpoints

```bash
# User profile
curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"
# {"id":"...","email":"jdoe@example.org","display_name":"John Doe","roles":["member"]}

# Member area (requires ORG_MEMBER+)
curl http://localhost:8000/member-area -H "Authorization: Bearer $TOKEN"
# {"message":"Welcome jdoe@example.org!","access_level":"member"}

# Admin area (requires ORG_ADMIN+ — should fail for jdoe)
curl http://localhost:8000/admin-area -H "Authorization: Bearer $TOKEN"
# 403 Forbidden
```

### Test with Admin User

```bash
# Get token for LDAP admin user
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-ldap-demo/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=glchat-backend" \
  -d "client_secret=glchat-backend-secret" \
  -d "username=asmith" \
  -d "password=asmith123" | jq -r '.access_token')

# Admin area (should succeed for asmith)
curl http://localhost:8000/admin-area -H "Authorization: Bearer $ADMIN_TOKEN"
# {"message":"Welcome Admin asmith@example.org!","access_level":"admin"}
```

## Understanding the Code

### No LDAP-Specific Code

The entire `main.py` uses standard `KeycloakProvider` — the same code from the [fastapi-keycloak](../fastapi-keycloak/) example. LDAP is configured in Keycloak, not in your application.

### How Keycloak Handles LDAP

1. **User Federation**: Keycloak connects to OpenLDAP and imports users on first login
2. **Attribute Mapping**: LDAP attributes (uid, mail, givenName, sn) are mapped to Keycloak user fields
3. **Token Issuance**: Keycloak issues standard OIDC tokens for LDAP users
4. **GL-IAM Validation**: `KeycloakProvider` validates the token — doesn't know or care if the user came from LDAP

### Role Mapping

LDAP groups can be mapped to Keycloak roles using group-ldap-mapper:
- LDAP group `admins` → Keycloak role `admin` → GL IAM `ORG_ADMIN`
- LDAP group `members` → Keycloak role `member` → GL IAM `ORG_MEMBER`

## Cleanup

```bash
docker-compose down -v
```

## Next Steps

- [fastapi-keycloak](../fastapi-keycloak/) — Standard Keycloak setup (no LDAP)
- [saml-keycloak](../saml-keycloak/) — SAML 2.0 federation via Keycloak
- [rbac-showcase](../rbac-showcase/) — Advanced RBAC patterns
- [GL-IAM GitBook: Enterprise Protocols](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/tutorials/traditional-iam/enterprise-protocols)
