# RBAC Showcase - Multi-Provider Example

This example demonstrates GL-IAM's **Role-Based Access Control (RBAC)** features with support for both Keycloak and StackAuth providers. It validates the role mapping behavior and demonstrates the SIMI (Single Interface Multiple Implementation) pattern.

## What This Example Demonstrates

1. **Role Mapping Visualization** - See how provider-specific roles map to GL-IAM standard roles
2. **Role Hierarchy** - Understand how PLATFORM_ADMIN > ORG_ADMIN > ORG_MEMBER works
3. **Standard Role-Based Access Control** - Test protected endpoints at different access levels
4. **Provider Comparison** - Compare role mappings between Keycloak and StackAuth
5. **SIMI Pattern** - Same application code works with different providers

## Standard Roles

GL-IAM defines three standard roles that work across all providers:

| Standard Role | Description | Implied Roles |
|---------------|-------------|---------------|
| `PLATFORM_ADMIN` | Super administrator with access to all resources | ORG_ADMIN, ORG_MEMBER |
| `ORG_ADMIN` | Organization administrator | ORG_MEMBER |
| `ORG_MEMBER` | Regular organization member | (none) |

## Role Mappings

### Keycloak Mappings

| Keycloak Role | Standard Role |
|---------------|---------------|
| `admin` | ORG_ADMIN |
| `member` | ORG_MEMBER |
| `viewer` | ORG_MEMBER |

### Stack Auth Mappings

| Stack Auth Role | Standard Role |
|-----------------|---------------|
| `$admin` | ORG_ADMIN |
| `admin` | ORG_ADMIN |
| `$member` | ORG_MEMBER |
| `member` | ORG_MEMBER |

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- Docker and Docker Compose installed (for Keycloak)
- UV package manager installed

## Getting Started

### 1. Clone and Navigate

```bash
git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
cd gl-iam-cookbook/gl-iam/examples/rbac-showcase/
```

### 2. Install Dependencies

**Unix-based systems (Linux, macOS):**
```bash
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

Or manually: `uv sync`

### 3. Configure Environment

The setup script already creates `.env` from `.env.example`. Edit it to choose your provider:
- `PROVIDER_TYPE=keycloak` (default) - Uses local Docker Keycloak
- `PROVIDER_TYPE=stackauth` - Requires external Stack Auth instance

### 4. Start the Provider

**For Keycloak:**
```bash
docker-compose up -d
```

Wait for Keycloak to be ready:
```bash
docker-compose logs -f keycloak
```

Look for: `Keycloak ... started`

**For Stack Auth:**
Configure your Stack Auth credentials in `.env`:
```
STACKAUTH_BASE_URL=http://your-stackauth-server
STACKAUTH_PROJECT_ID=your-project-id
STACKAUTH_PUBLISHABLE_CLIENT_KEY=pk_your_key
STACKAUTH_SECRET_SERVER_KEY=ssk_your_key
```

### 5. Run the Server

```bash
uv run main.py
```

Output:
```
Connected to Keycloak at http://localhost:8080
Provider type: keycloak
Organization ID: gl-iam-demo
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 6. Explore the API

Open **http://localhost:8000/docs** for interactive API documentation.

## Demo Users (Keycloak)

| Email | Password | Keycloak Roles | Standard Roles |
|-------|----------|----------------|----------------|
| admin@example.com | admin123 | admin | ORG_ADMIN |
| member@example.com | member123 | member | ORG_MEMBER |
| viewer@example.com | viewer123 | viewer | ORG_MEMBER |

> **Note about PLATFORM_ADMIN**: The `PLATFORM_ADMIN` role is typically assigned via metadata
> flag (`is_platform_admin: true`) rather than provider roles. This requires custom token
> mapping in Keycloak. This example focuses on demonstrating `ORG_ADMIN` and `ORG_MEMBER`
> role mapping and hierarchy, which work out of the box with standard Keycloak roles.

## Test the API

### Get a Token

```bash
# Regular member
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "member@example.com", "password": "member123"}' \
  | jq -r '.access_token')

# Organization admin
ADMIN_TOKEN=$(curl -s -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@example.com", "password": "admin123"}' \
  | jq -r '.access_token')
```

Or get token directly from Keycloak:
```bash
TOKEN=$(curl -s -X POST "http://localhost:8080/realms/gl-iam-demo/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=glchat-backend" \
  -d "client_secret=glchat-backend-secret" \
  -d "grant_type=password" \
  -d "username=member@example.com" \
  -d "password=member123" | jq -r '.access_token')
```

### RBAC Demonstration Endpoints

```bash
# View role mappings for current provider
curl http://localhost:8000/rbac/mapping-table \
  -H "Authorization: Bearer $TOKEN" | jq

# View role hierarchy
curl http://localhost:8000/rbac/hierarchy \
  -H "Authorization: Bearer $TOKEN" | jq

# Get your role information
curl http://localhost:8000/rbac/my-roles \
  -H "Authorization: Bearer $TOKEN" | jq

# Test access to different role levels
curl http://localhost:8000/rbac/test-access \
  -H "Authorization: Bearer $TOKEN" | jq

# Compare provider mappings
curl http://localhost:8000/rbac/provider-comparison \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Protected Areas

```bash
# Member area (ORG_MEMBER or higher)
curl http://localhost:8000/rbac/member-area \
  -H "Authorization: Bearer $TOKEN"
# Success for member@example.com

# Admin area (ORG_ADMIN or higher)
curl http://localhost:8000/rbac/admin-area \
  -H "Authorization: Bearer $TOKEN"
# Returns 403 for member@example.com

curl http://localhost:8000/rbac/admin-area \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Success for admin@example.com

# Platform admin area (PLATFORM_ADMIN only - requires custom metadata)
curl http://localhost:8000/rbac/platform-admin-area \
  -H "Authorization: Bearer $ADMIN_TOKEN"
# Returns 403 (ORG_ADMIN doesn't have PLATFORM_ADMIN access)
```

**Key Demonstration**: The `admin@example.com` user with `ORG_ADMIN` role can access:
- `/rbac/member-area` (via role hierarchy - ORG_ADMIN implies ORG_MEMBER)
- `/rbac/admin-area` (direct ORG_ADMIN access)

But cannot access:
- `/rbac/platform-admin-area` (requires PLATFORM_ADMIN)

### Role Management (Admin Only)

```bash
# Get available roles
curl http://localhost:8000/admin/roles/available \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq

# Get authorization rules
curl http://localhost:8000/admin/authorization-rules \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

## Understanding the Code

### SIMI Pattern (Single Interface Multiple Implementation)

The application code uses **standard roles** that work across providers:

```python
from gl_iam.fastapi import require_org_admin, require_org_member

@app.get("/admin-area")
async def admin_area(_: None = Depends(require_org_admin())):
    # Works with Keycloak "admin" or StackAuth "$admin"
    return {"access": "granted"}
```

Only the provider configuration changes:

```python
# config.py
if settings.provider_type == ProviderType.KEYCLOAK:
    gateway, provider = create_keycloak_gateway()
else:
    gateway, provider = create_stackauth_gateway()
```

### Role Hierarchy Implementation

GL-IAM respects role hierarchy automatically:

```python
# User with ORG_ADMIN role
user.has_standard_role(StandardRole.ORG_ADMIN)   # True
user.has_standard_role(StandardRole.ORG_MEMBER)  # True (via hierarchy)

# Without hierarchy (exact match)
user.has_standard_role(StandardRole.ORG_MEMBER, respect_hierarchy=False)  # False
```

### Directory Structure

```
rbac-showcase/
├── main.py              # FastAPI application with provider factory
├── config.py            # Multi-provider Pydantic settings
├── deps.py              # FastAPI dependencies
├── schemas.py           # Pydantic response models
├── routers/
│   ├── auth.py          # Token retrieval endpoints
│   ├── rbac.py          # RBAC demonstration endpoints
│   └── admin.py         # Role management endpoints
├── docker-compose.yml   # Keycloak setup
├── realm-export.json    # Pre-configured Keycloak realm
└── README.md            # This file
```

## Test Scenarios

### Role Mapping Validation

| Scenario | Expected Result |
|----------|-----------------|
| Keycloak user with `admin` role | has_standard_role(ORG_ADMIN) = True |
| Keycloak user with `member` role | has_standard_role(ORG_MEMBER) = True |
| Keycloak user with `viewer` role | has_standard_role(ORG_MEMBER) = True |
| StackAuth user with `$admin` role | has_standard_role(ORG_ADMIN) = True |
| StackAuth user with `$member` role | has_standard_role(ORG_MEMBER) = True |

### Role Hierarchy Validation

| User Role | /member-area | /admin-area | /platform-admin-area |
|-----------|--------------|-------------|---------------------|
| PLATFORM_ADMIN | ✓ | ✓ | ✓ |
| ORG_ADMIN | ✓ | ✓ | ✗ |
| ORG_MEMBER | ✓ | ✗ | ✗ |

### Authorization Rules

| Action | PLATFORM_ADMIN | ORG_ADMIN | ORG_MEMBER |
|--------|----------------|-----------|------------|
| Assign any role | ✓ | ✗ (org only) | ✗ |
| Remove any role | ✓ | ✗ (org only) | ✗ |
| Assign platform_admin | ✓ | ✗ | ✗ |
| Remove own admin role | ✗ | ✗ | N/A |

## Switching Providers

To switch from Keycloak to StackAuth:

1. Update `.env`:
   ```
   PROVIDER_TYPE=stackauth
   STACKAUTH_BASE_URL=http://your-stackauth-server
   STACKAUTH_PROJECT_ID=your-project-id
   STACKAUTH_PUBLISHABLE_CLIENT_KEY=pk_your_key
   STACKAUTH_SECRET_SERVER_KEY=ssk_your_key
   ```

2. Restart the server:
   ```bash
   uv run main.py
   ```

3. Note: The `/auth/token` endpoint won't work with StackAuth (browser-based auth).
   Use the Stack Auth SDK in your frontend to obtain tokens.

## Cleanup

```bash
docker-compose down -v
```

## Reference

This example is based on the [GL-IAM RBAC documentation](https://gdplabs.gitbook.io/sdk/gl-iam/rbac).

## Troubleshooting

### Keycloak not starting

If Keycloak fails to start, check the logs:
```bash
docker-compose logs keycloak
```

Common issues:
- Port 8080 already in use
- Not enough memory for Docker

### Token validation fails

Ensure the Keycloak realm is properly imported:
1. Access Keycloak Admin Console: http://localhost:8080/admin (admin/admin)
2. Check that `gl-iam-demo` realm exists
3. Verify users are present in the realm

### StackAuth connection fails

Verify your StackAuth credentials:
```bash
curl -H "x-stack-project-id: your-project-id" \
     -H "x-stack-publishable-client-key: pk_your_key" \
     your-stackauth-server/api/v1/health
```
