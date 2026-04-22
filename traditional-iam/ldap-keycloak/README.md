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

Verify Keycloak is ready (health endpoints are served on the management port 9000):

```bash
curl -s http://localhost:9000/health/ready | jq .
```

### 3. Sync LDAP Users

After Keycloak starts, trigger a user sync. Pick **one** of the two options below.

#### Option A — Admin console (Keycloak 26 UI)

1. Go to http://localhost:8080/admin (admin / admin)
2. Select realm **gl-iam-ldap-demo**
3. Go to **User federation** → click **ldap** to open its Settings page
4. Top-right **Action** dropdown → **Sync all users**
   > In Keycloak 26 the standalone "Synchronize all users" button was moved into this Action menu. Older Keycloak versions show the button inline on the provider page.
5. Assign roles to synced users:
   - Go to **Users** → find `jdoe` → **Role mapping** → Assign **member**
   - Go to **Users** → find `asmith` → **Role mapping** → Assign **admin** + **member**

#### Option B — Command line (kcadm.sh)

```bash
# 1. Log in once
docker exec ldap-keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin --password admin

# 2. Find the LDAP provider's component id
LDAP_ID=$(docker exec ldap-keycloak /opt/keycloak/bin/kcadm.sh get components \
  -r gl-iam-ldap-demo --query 'type=org.keycloak.storage.UserStorageProvider' \
  --fields id --format csv --noquotes | tail -1)

# 3. Trigger full sync (quote the URL so the shell does not eat the '?')
docker exec ldap-keycloak /opt/keycloak/bin/kcadm.sh create \
  "user-storage/$LDAP_ID/sync?action=triggerFullSync" -r gl-iam-ldap-demo

# 4. Assign roles
docker exec ldap-keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r gl-iam-ldap-demo --uusername jdoe --rolename member
docker exec ldap-keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r gl-iam-ldap-demo --uusername asmith --rolename admin --rolename member
```

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

## Using with Active Directory

For a runnable AD example, see [`../ad-keycloak/`](../ad-keycloak/). The bullets below are the minimal realm-export diff if you want to adapt **this** example in-place against a real AD (or Samba AD DC):

1. **Use the AD vendor preset in the admin UI** — it auto-fills most fields correctly. Prefer it over editing `realm-export.json` by hand.
2. **Fields to change** in the federation component (`realm-export.json` → `components.org.keycloak.storage.UserStorageProvider[0].config`):
   - `vendor` → `ad`
   - `usernameLDAPAttribute` → `sAMAccountName`
   - `rdnLDAPAttribute` → `cn`
   - `uuidLDAPAttribute` → `objectGUID`
   - `userObjectClasses` → `person, organizationalPerson, user`
   - `usersDn` → `CN=Users,DC=yourdomain,DC=com`
   - `bindDn` → `CN=<service-account>,CN=Users,DC=yourdomain,DC=com`
3. **Update the username mapper** sub-component: `ldap.attribute` → `sAMAccountName` (was `uid`). The `email`, `first name`, and `last name` mappers stay unchanged — AD uses `mail`, `givenName`, and `sn` too.
4. **Add the `msad-user-account-control-mapper`** sub-component (the AD vendor preset installs it automatically via the UI; hand-authored JSON must include it explicitly). Without it, disabled or locked AD accounts still authenticate.
5. **Gotchas**:
   - AD requires paging: set `pagination: ["true"]` on the federation component.
   - Use `ldaps://<dc>:636` + a trusted certificate in production, not `ldap://…:389`.
   - Keep `editMode: READ_ONLY` and bind with a service account that has only the permissions Keycloak needs.

## Cleanup

```bash
docker-compose down -v
```

## Next Steps

- [fastapi-keycloak](../fastapi-keycloak/) — Standard Keycloak setup (no LDAP)
- [saml-keycloak](../saml-keycloak/) — SAML 2.0 federation via Keycloak
- [rbac-showcase](../rbac-showcase/) — Advanced RBAC patterns
- [GL-IAM GitBook: Enterprise Protocols](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/tutorials/traditional-iam/enterprise-protocols)
