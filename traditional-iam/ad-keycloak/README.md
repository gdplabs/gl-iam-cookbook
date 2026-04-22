# Active Directory Authentication via Keycloak

Authenticate Active Directory users through Keycloak's User Federation (AD vendor preset), with GL-IAM handling authorization.

## Overview

This example demonstrates how corporate AD users can authenticate in your application without any AD-specific code. Keycloak handles the AD protocol natively (via LDAP with AD-specific attributes like `sAMAccountName` and `objectGUID`), and GL-IAM validates the OIDC tokens Keycloak issues.

```
Samba AD DC ←→ Keycloak (User Federation, vendor=ad) ←→ FastAPI + GL-IAM
```

**Key point**: The FastAPI application code is identical to the [ldap-keycloak](../ldap-keycloak/) example. Only the directory (Samba AD DC instead of OpenLDAP) and the realm-export (AD vendor preset) change.

### How this differs from `ldap-keycloak`

| Aspect | `ldap-keycloak` (OpenLDAP) | `ad-keycloak` (this example) |
| --- | --- | --- |
| Directory image | `osixia/openldap` | `nowsci/samba-domain` (Samba AD DC) |
| Keycloak `vendor` | `other` | `ad` |
| Username attribute | `uid` | `sAMAccountName` |
| UUID attribute | `entryUUID` | `objectGUID` (binary) |
| User object classes | `inetOrgPerson` | `person, organizationalPerson, user` |
| User base DN | `ou=People,dc=example,dc=org` | `CN=Users,DC=example,DC=org` |
| Seeding | LDIF bootstrap file | `samba-tool user create` via sidecar |
| Extra required mapper | — | `msad-user-account-control-mapper` |

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Docker and Docker Compose
- Access to GDP Labs Gen AI SDK repository
- **Stop `ldap-keycloak` first if it's running** — both examples use ports 389, 8080, and 9000:
  ```bash
  docker-compose -f ../ldap-keycloak/docker-compose.yml down
  ```

> **Apple Silicon note**: The `nowsci/samba-domain` image is `linux/amd64` and runs under Rosetta 2 emulation on ARM Macs. Boot takes ~60–90s (longer than native); subsequent starts use cached volumes.

## Quick Start

### 1. Setup

```bash
./setup.sh
# or manually:
uv sync
cp .env.example .env
```

### 2. Start Services (Samba AD DC + Keycloak)

```bash
docker-compose up -d
```

Startup sequence (~90s total):
1. `samba-ad` provisions the AD domain `example.org` on first boot (slow the first time; uses persistent volumes after that).
2. `ad-init` sidecar waits for the DC to pass its health check, then seeds `jdoe`, `asmith`, the `members`/`admins` groups, and their memberships.
3. `keycloak-db` and `keycloak` start; Keycloak imports the realm and connects to the DC.

Verify Keycloak is ready (health endpoints are served on the management port 9000):

```bash
curl -s http://localhost:9000/health/ready | jq .
```

Verify AD users were seeded:

```bash
docker exec ad-keycloak-samba samba-tool user list
# Expect: krbtgt, Administrator, Guest, jdoe, asmith
```

### 3. Sync AD Users

After Keycloak starts, trigger a user sync. Pick **one** of the two options below.

#### Option A — Admin console (Keycloak 26 UI)

1. Go to http://localhost:8080/admin (admin / admin)
2. Select realm **gl-iam-ad-demo**
3. Go to **User federation** → click **ad** to open its Settings page
4. Top-right **Action** dropdown → **Sync all users**
5. Assign roles to synced users:
   - Go to **Users** → find `jdoe` → **Role mapping** → Assign **member**
   - Go to **Users** → find `asmith` → **Role mapping** → Assign **admin** + **member**

#### Option B — Command line (kcadm.sh)

```bash
# 1. Log in once
docker exec ad-keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master --user admin --password admin

# 2. Find the AD provider's component id
AD_ID=$(docker exec ad-keycloak /opt/keycloak/bin/kcadm.sh get components \
  -r gl-iam-ad-demo --query 'type=org.keycloak.storage.UserStorageProvider' \
  --fields id --format csv --noquotes | tail -1)

# 3. Trigger full sync (quote the URL so the shell does not eat the '?')
docker exec ad-keycloak /opt/keycloak/bin/kcadm.sh create \
  "user-storage/$AD_ID/sync?action=triggerFullSync" -r gl-iam-ad-demo

# 4. Assign roles
docker exec ad-keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r gl-iam-ad-demo --uusername jdoe --rolename member
docker exec ad-keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r gl-iam-ad-demo --uusername asmith --rolename admin --rolename member
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
# {"status":"healthy","provider":"keycloak","federation":"ad"}
```

### Authenticate an AD User

```bash
# Get token for AD user jdoe
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-ad-demo/protocol/openid-connect/token" \
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
# Get token for AD admin user
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-ad-demo/protocol/openid-connect/token" \
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

### No AD-Specific Code

The entire `main.py` uses standard `KeycloakProvider` — the same code from the [ldap-keycloak](../ldap-keycloak/) and [fastapi-keycloak](../fastapi-keycloak/) examples. AD is configured in Keycloak, not in your application.

### How Keycloak Handles AD

1. **AD vendor preset** — `vendor: "ad"` in `realm-export.json` turns on AD-specific defaults (paging, AD object classes, username attribute).
2. **Attribute mapping** — AD attributes (`sAMAccountName`, `mail`, `givenName`, `sn`) map to Keycloak user fields; `objectGUID` becomes the external id.
3. **MSAD account controls** — the `msad-user-account-control-mapper` sub-component honors AD account flags (disabled, locked, password-expired) during login. Easy to forget when hand-authoring `realm-export.json`; Keycloak's UI AD preset installs it automatically.
4. **Token issuance** — Keycloak issues standard OIDC tokens for AD users.
5. **GL-IAM validation** — `KeycloakProvider` validates the token; doesn't know or care that the user came from AD.

### Demo-only shortcuts (do not copy into production)

- `INSECURELDAP=true` — disables the DC's "strong auth required" flag so Keycloak can bind over plain LDAP. In production, use **LDAPS** (`ldaps://dc:636`) with a trusted certificate.
- `NOCOMPLEXITY=true` — disables AD password complexity so the demo users can have `jdoe123` / `asmith123`.
- `privileged: true` on the DC — simplifies Samba's kernel requirements for the demo. In production, use explicit `cap_add` lists.
- `bindCredential: "Password123!"` for the Domain Administrator. In production, use a dedicated service account with only the permissions Keycloak needs, and store its password in a secret manager.

### Role Mapping

AD security groups can be mapped to Keycloak roles using a `group-ldap-mapper` sub-component. This example uses manual role assignment (`kcadm.sh add-roles`) to keep parity with the LDAP sibling. For group-to-role sync, add a `group-ldap-mapper` to `realm-export.json` and point its `groups.dn` at `CN=Users,DC=example,DC=org`.

## Cleanup

Two modes, pick based on whether you want to keep the AD domain data:

```bash
# Keep users & the provisioned domain (fastest next startup)
docker-compose down

# Destroy everything, including the AD domain (next up re-provisions from scratch)
docker-compose down -v
```

> **Why this matters**: the `samba_data` volume holds the provisioned domain, including every user's stable `objectGUID`. If you `down -v` and then `up -d`, the next sync will re-import users with **new GUIDs** — any role assignments you made in Keycloak will be orphaned. Use `down -v` only when you intentionally want a clean slate.

## Next Steps

- [ldap-keycloak](../ldap-keycloak/) — Same pattern with OpenLDAP
- [fastapi-keycloak](../fastapi-keycloak/) — Standard Keycloak setup (no external directory)
- [saml-keycloak](../saml-keycloak/) — SAML 2.0 federation via Keycloak
- [rbac-showcase](../rbac-showcase/) — Advanced RBAC patterns
- [GL-IAM GitBook: Enterprise Protocols](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/tutorials/traditional-iam/enterprise-protocols)
