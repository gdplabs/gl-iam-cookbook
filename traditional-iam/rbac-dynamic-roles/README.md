# Dynamic Role Management — Multi-Tenant RBAC

Roles that are **not known at build time**. Two tenants, each with its own role
vocabulary, created, granted, assigned, and retired at runtime through
`IAMGateway` — no migration, no redeploy.

This is the example to read if you have asked any of:

- "Can I create a role from my admin panel instead of a migration?"
- "Can `hotel-bali` and `hotel-ubud` each have a `property_manager` that means
  different things?"
- "Can I take a role out of service without losing who had it?"
- "Who is actually allowed to do these things?"

## What This Example Demonstrates

| # | Act in the walkthrough | The point |
|---|---|---|
| 1 | Define permissions, then a role that carries them, per tenant | `create_permission` → `create_role` |
| 2 | Two roles share a name and nothing else | Roles are organization-scoped |
| 3 | An `ORG_ADMIN` assigns an existing role | `assign_role` — supported on **every** backend |
| 4 | Assigning twice | `changed=False` is a success, not a failure |
| 5 | An `ORG_ADMIN` may not define roles, or grant `platform_admin` | The privilege-escalation guard |
| 6 | Tenants cannot reach into each other | A token is scoped to one organization |
| 7 | `grant_permission_to_role` | Additive |
| 8 | `update_role(permissions=[...])` | **Replaces** the whole set — the sharp edge |
| 9 | `deactivate_role` | Stops granting; assignments retained |
| 10 | `activate_role` | Everything comes back |
| 11 | System roles | Immutable, and their names are reserved |
| 12 | `delete_role` | Irreversible |

Deny paths are first-class here. An example that only shows the happy path
teaches you what works, not where the boundaries are.

## Provider support — read this first

| Operation | Native | Stack Auth | Keycloak |
|---|:---:|:---:|:---:|
| `assign_role` / `remove_role` | ✅ | ✅ | ✅ |
| `check_permission`, `get_user_roles`, `get_user_permissions` | ✅ | ✅ | ✅ |
| `create_role` / `update_role` / `delete_role` | ✅ | ❌ `NOT_SUPPORTED` | ❌ `PROVIDER_ERROR` |
| `deactivate_role` / `activate_role` | ✅ | ❌ `NOT_SUPPORTED` | ❌ `PROVIDER_ERROR` |
| Permission definitions and grants | ✅ | ❌ `PROVIDER_ERROR` | ❌ `PROVIDER_ERROR` |

**Attaching a role to a user works everywhere. *Defining* one requires the
Native provider.** The two failures are different on purpose: `NOT_SUPPORTED`
means the provider implements the method and deliberately refuses it,
`PROVIDER_ERROR` means it has no such method at all.

Running Stack Auth or Keycloak and still want custom roles? Define them in that
product's own console, or wire a Native user store alongside your Stack Auth
auth provider in the same `IAMGateway`.

This example therefore uses the **Native** provider throughout.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:

- PostgreSQL reachable at `DATABASE_URL` (a Docker one-liner is below)
- UV package manager
- **`gl-iam` 0.3.15 or newer** — dynamic role management landed there. Earlier
  releases have `assign_role`/`remove_role` but no role-definition API.

## Quick Start

### 1. Clone and Navigate

```bash
git clone https://github.com/gdplabs/gl-iam-cookbook.git
cd gl-iam-cookbook/traditional-iam/rbac-dynamic-roles/
```

### 2. Install Dependencies

```bash
./setup.sh          # Linux, macOS, WSL
setup.bat           # Windows
```

### 3. Start PostgreSQL

```bash
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=gliam \
  -p 5432:5432 postgres:15
```

### 4. Seed the tenants

```bash
uv run seed.py
```

Creates `hotel-bali` and `hotel-ubud`, one platform admin, and an `ORG_ADMIN`
and `ORG_MEMBER` per tenant. It is idempotent — run it again any time.

### 5. Run the server

```bash
uv run main.py          # http://localhost:8000 — docs at /docs
```

### 6. Watch the whole story

In another terminal:

```bash
uv run walkthrough.py
```

Every act prints the caller, the request, and the status it expected. A deny
path that stops denying fails the run.

## Testing the API

Get a token. Note that login is **per organization** — the token is scoped to it.

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"platform-admin@example.com","password":"Platform@dmin1","organization_id":"hotel-bali"}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')
```

**Who am I, and what can I do here?**

```bash
curl -s http://localhost:8000/orgs/hotel-bali/me -H "Authorization: Bearer $TOKEN"
```

`effective_roles` excludes roles whose definition is deactivated;
`assigned_roles` shows the raw assignments. Comparing the two is the clearest
way to see what `deactivate_role` does.

**Define a permission, then a role that carries it:**

```bash
curl -s -X POST http://localhost:8000/orgs/hotel-bali/permissions \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"bookings:refund","description":"Refund a confirmed booking"}'

curl -s -X POST http://localhost:8000/orgs/hotel-bali/roles \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"front_desk","description":"Front desk staff","permissions":["bookings:refund"]}'
```

**List what this tenant can see** — its own roles plus the global system roles
(which come back with `"organization_id": null`):

```bash
curl -s http://localhost:8000/orgs/hotel-bali/roles -H "Authorization: Bearer $TOKEN"
curl -s 'http://localhost:8000/orgs/hotel-bali/roles?include_inactive=true' -H "Authorization: Bearer $TOKEN"
```

**Assign it to a user:**

```bash
curl -s -X POST http://localhost:8000/orgs/hotel-bali/roles/assign \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"user_id":"<USER_ID>","role":"front_desk"}'
```

**Add one permission without restating the rest:**

```bash
curl -s -X POST http://localhost:8000/orgs/hotel-bali/permissions/grant \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"role_name":"front_desk","permission_name":"bookings:read"}'
```

**Retire it reversibly, then bring it back:**

```bash
curl -s -X POST http://localhost:8000/orgs/hotel-bali/roles/front_desk/deactivate -H "Authorization: Bearer $TOKEN"
curl -s -X POST http://localhost:8000/orgs/hotel-bali/roles/front_desk/activate   -H "Authorization: Bearer $TOKEN"
```

**Remove it from one user, or delete it for everyone:**

```bash
curl -s -X POST http://localhost:8000/orgs/hotel-bali/roles/remove \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"user_id":"<USER_ID>","role":"front_desk"}'

curl -s -X DELETE http://localhost:8000/orgs/hotel-bali/roles/front_desk -H "Authorization: Bearer $TOKEN"
```

### Endpoints

| Method | Path | Who |
|---|---|---|
| `POST` | `/login` | anyone |
| `GET` | `/orgs/{org}/me` | any member |
| `GET` | `/orgs/{org}/roles` · `/roles/{name}` | any member |
| `POST` | `/orgs/{org}/roles` | `PLATFORM_ADMIN` |
| `PATCH` | `/orgs/{org}/roles/{name}` | `PLATFORM_ADMIN` |
| `POST` | `/orgs/{org}/roles/{name}/deactivate` · `/activate` | `PLATFORM_ADMIN` |
| `DELETE` | `/orgs/{org}/roles/{name}` | `PLATFORM_ADMIN` |
| `POST` | `/orgs/{org}/roles/assign` · `/remove` | `ORG_ADMIN` (own tenant); `PLATFORM_ADMIN` for a standard role |
| `GET` | `/orgs/{org}/permissions` | any member |
| `POST` | `/orgs/{org}/permissions` | `PLATFORM_ADMIN` |
| `DELETE` | `/orgs/{org}/permissions/{name}` | `PLATFORM_ADMIN` |
| `POST` | `/orgs/{org}/permissions/grant` · `/revoke` | `PLATFORM_ADMIN` |

## Understanding the Code

### The app never decides who is allowed

Every gateway call takes `caller_id`, and GL-IAM enforces authority itself.
There is no "trust the caller" path, and this example deliberately doesn't add
one:

```python
role = unwrap(await gateway.create_role(
    name=request.name,
    organization_id=organization_id,
    caller_id=user.id,          # checked by the SDK, not by us
    permissions=request.permissions or None,
))
```

The rules, in one table:

| Operation | `PLATFORM_ADMIN` | `ORG_ADMIN` (own org) | `ORG_MEMBER` |
|---|:---:|:---:|:---:|
| Define / edit / delete a role or permission | ✅ | ❌ | ❌ |
| Grant or revoke a permission on a role | ✅ | ❌ | ❌ |
| Assign or remove a **custom** role | ✅ | ✅ | ❌ |
| Assign or remove a **standard** role | ✅ | ❌ | ❌ |

An `ORG_ADMIN` spends authority their tenant already holds; defining a role
*mints* authority. The standard-role restriction is what stops an org admin
minting a `platform_admin` and escalating past their own ceiling.

### `Result` → HTTP, in one place (`deps.py`)

GL-IAM returns `Result[T]` rather than raising, so something has to map error
codes to statuses. Doing it once keeps every route two lines long:

```python
_STATUS_BY_CODE = {
    ErrorCode.PERMISSION_DENIED: 403,
    ErrorCode.ROLE_NOT_FOUND: 404,
    ErrorCode.ROLE_ALREADY_EXISTS: 409,
    ErrorCode.NOT_SUPPORTED: 501,   # the backend can't; nothing went wrong
    ...
}
```

`NOT_SUPPORTED` and `PROVIDER_ERROR` map to **501**, not 500 — "this backend
doesn't do that" is a fact about your deployment, not a server fault.

### One gateway, many tenants

Multi-tenancy is a parameter on each call, not a gateway per tenant. What makes
it a real boundary is that `deps.get_tenant_user` validates the session against
the organization **in the URL**, so a token minted for `hotel-ubud` doesn't
authenticate against `hotel-bali`.

### The two traps worth internalizing

- **`PATCH /roles/{name}` with `permissions` replaces the entire set.** Act 8
  shows two permissions vanishing. Use `POST /permissions/grant` to add one.
- **`deactivate_role` keeps assignments.** `get_user_roles` still lists the
  role; `user.roles` and the permission set do not. That is deliberate —
  reactivation restores the assignment, so hiding it would erase the very
  association you need in order to reason about what reactivation will do.

### Bootstrapping the first platform admin

Defining roles requires a `PLATFORM_ADMIN`, so the first one cannot be created
through the API. `seed.py` breaks the cycle with `roles=["platform_admin"]` on
`create_user_with_password`, which assigns at creation time without a caller —
the same path `gliam bootstrap-admin` uses. Everything after that goes through
the authorized API.

## Upgrading an existing deployment

Roles and permissions became organization-scoped in migrations `V012` and
`V013`. If you already had custom roles:

- Rows named `platform_admin` / `org_admin` / `org_member` become global system
  roles.
- **Every other pre-existing role is assigned to the organization literally
  named `default`** — a migration can't read your running config to learn what
  `default_org_id` actually is.
- Pre-existing **permissions** stay global and become `is_system = true`, hence
  read-only.

Re-point anything that landed in the wrong place:

```sql
SELECT name, organization_id, is_system, is_active
  FROM gl_iam.roles WHERE organization_id = 'default';

UPDATE gl_iam.roles
   SET organization_id = 'hotel-bali'
 WHERE name = 'property_manager' AND organization_id = 'default';
```

## Troubleshooting

| Symptom | Cause |
|---|---|
| `501` with `not_supported` / `provider_error` | You pointed this at Stack Auth or Keycloak. Role definitions need the Native provider. |
| `403` on `POST /roles` as an org admin | Defining roles is `PLATFORM_ADMIN`-only. Assigning them is not. |
| `404` on a role you can see in the database | Wrong `organization_id` — role names resolve within one tenant. |
| `404` assigning a role that plainly exists | It's deactivated. Deactivated roles can't be assigned. |
| `422` creating a role | A name in `permissions` doesn't exist yet. Create the permission first. |
| `401` on every request | The token was minted for a different `organization_id`. |
| `PasswordPolicyError` in `seed.py` | This example sets `min_length=12, require_special=True`. Update the passwords in `.env` to match. |

## Next Steps

- [Manage Custom Roles](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/traditional-iam/authorization/role-management)
- [Assign Roles to Users](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/traditional-iam/authorization/assign-roles)
- [Manage Permissions](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/traditional-iam/authorization/permission-management)
- [Features & Provider Support](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/resources/features) — the full matrix
- [rbac-showcase](../rbac-showcase/) — standard roles and hierarchy across providers
- [audit-trail-fastapi](../audit-trail-fastapi/) — persist the events every operation here emits
