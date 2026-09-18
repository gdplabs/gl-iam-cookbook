# Refresh Tokens with FastAPI (Native Provider)

Keep users signed in with a long-lived **refresh token** while every **access token** stays short-lived. A stolen access token is useless within minutes; the refresh token, sent only to one endpoint, quietly gets the client a new one.

This example covers the whole lifecycle on GL-IAM's Native provider (PostgreSQL-backed):

| Step | Endpoint | GL-IAM call |
|------|----------|-------------|
| Log in with "remember me" and a 5-minute access token | `POST /login` | `gateway.authenticate(..., issue_refresh_token=True, access_token_ttl_seconds=300)` |
| Get a new access token | `POST /token/refresh` | `gateway.refresh_session(refresh_token)` |
| List signed-in devices | `GET /devices` | `gateway.list_refresh_tokens(user_id, org_id)` |
| Sign one device out | `DELETE /devices/{id}` | `gateway.revoke_refresh_token(id, user_id, org_id)` |
| End a device's current access tokens only | `DELETE /devices/{id}/sessions` | `gateway.revoke_refresh_token_sessions(id, user_id, org_id)` |
| Sign out everywhere in this organization | `POST /logout-everywhere` | `gateway.revoke_all_sessions(user_id, org_id)` |

> **Requires `gl-iam` 0.3.19 or later.** Refresh tokens, per-login access-token lifetimes, and organization-scoped revocation were added in that release.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:

- PostgreSQL 13 or later running locally

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/gdplabs/gl-iam-cookbook.git
   cd gl-iam-cookbook/traditional-iam/fastapi-refresh-tokens/
   ```

2. **Install dependencies**

   **For Unix-based systems (Linux, macOS):**

   ```bash
   ./setup.sh
   ```

   **For Windows:**

   ```cmd
   setup.bat
   ```

   Or manually: `uv sync`

3. **Configure environment** (optional)

   The setup script already creates `.env` from `.env.example`. `REFRESH_TOKEN_EXPIRY_SECONDS` sets how long a refresh token lives (one year by default).

4. **Start PostgreSQL** (if not running)

   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=gliam \
     -p 5432:5432 \
     postgres:15
   ```

5. **Run the server**

   ```bash
   uv run main.py
   ```

   The API is at `http://localhost:8000` (interactive docs at `/docs`). Tables are created on first start.

## Test the API

Run these in order; each step uses values from the previous ones.

**1. Register**

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!"}'
```

**2. Log in** — `remember_me` defaults to `true`, and the access token lives 300 seconds:

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "Bearer",
  "expires_at": "2026-09-18T07:41:22Z",
  "refresh_token": "gliamrt_qFg5x9KiAhh_0icPlFi-G9gHaMrgzecZxjnRwnPxNSg",
  "refresh_expires_at": "2027-09-18T07:36:22Z",
  "refresh_token_id": "983466ce-ebfd-4c7c-b18d-a6b930f40685"
}
```

Save the values:

```bash
export ACCESS_TOKEN="<access_token>"
export REFRESH_TOKEN="<refresh_token>"
export DEVICE_ID="<refresh_token_id>"
```

A lifetime outside 300–2,592,000 seconds is rejected with `400`, never silently adjusted:

```bash
curl -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@example.com", "password": "SecurePass123!", "access_token_ttl_seconds": 60}'
```

**3. Call a protected endpoint**

```bash
curl http://localhost:8000/me -H "Authorization: Bearer $ACCESS_TOKEN"
```

**4. Refresh** — before `expires_at`, swap the refresh token for a new access token:

```bash
curl -X POST http://localhost:8000/token/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"
```

The response has a new `access_token` and the **same** `refresh_token` and `refresh_expires_at`. Refresh tokens are not rotated, so keep using the one you have. Update `ACCESS_TOKEN` with the new value.

**5. List signed-in devices** — log in a second time (another "device") first to see two entries:

```bash
curl http://localhost:8000/devices -H "Authorization: Bearer $ACCESS_TOKEN"
```

```json
[
  {
    "refresh_token_id": "983466ce-ebfd-4c7c-b18d-a6b930f40685",
    "preview": "gliamrt_qFg5…xNSg",
    "created_at": "2026-09-18T07:36:22.336301+00:00",
    "expires_at": "2027-09-18T07:36:22+00:00",
    "last_used_at": "2026-09-18T07:36:22+00:00",
    "active_sessions": 2
  }
]
```

`preview` is safe to show in a UI; it cannot be used to sign in.

**6. End a device's current access tokens** — the device can refresh again afterwards:

```bash
curl -X DELETE http://localhost:8000/devices/$DEVICE_ID/sessions \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# {"revoked_access_tokens": 2}
```

Your `ACCESS_TOKEN` was one of them, so `/me` now returns `401`. Get a new one with step 4 — it still works.

**7. Sign a device out** — its refresh token and access tokens stop working on the next request. Signing out the device you are using is allowed:

```bash
curl -X DELETE http://localhost:8000/devices/$DEVICE_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# 204; a second call returns 404
```

**8. Sign out everywhere** (with a token from another device that is still signed in):

```bash
curl -X POST http://localhost:8000/logout-everywhere \
  -H "Authorization: Bearer $ACCESS_TOKEN"
# {"revoked_sessions": 1}
```

Every refresh token and session the user has **in this organization** is revoked; other organizations are untouched.

## Understanding the Code

### Opting in

Refresh tokens are opt-in per login. Without `issue_refresh_token=True`, login behaves exactly as in [fastapi-postgresql](../fastapi-postgresql/): one access token, no refresh token.

```python
result = await gateway.authenticate(
    credentials=PasswordCredentials(email=request.email, password=request.password),
    organization_id=ORG_ID,
    issue_refresh_token=request.remember_me,
    access_token_ttl_seconds=request.access_token_ttl_seconds,
)
```

### What an exchange guarantees

| Behavior | Why it matters |
|----------|----------------|
| The refresh token alone is enough | The user and organization come from the token itself |
| Same refresh token back, original expiry | No rotation to track; an exchange never extends the refresh token's life |
| Lifetime chosen at login is reused | Pass `access_token_ttl_seconds=` to `refresh_session` to override one exchange |
| Access token never outlives the refresh token | Near the end, the access token is cut short to match |
| Rejected when revoked, expired, or the user or organization is deactivated | The client gets `401` and sends the user back to login |

### Storage and safety

- Only a SHA-256 hash of each refresh token is stored; the database never holds the token itself.
- Revocation is checked on every request, so it takes effect immediately rather than at expiry.
- Another user's `refresh_token_id` behaves as "not found", so users cannot sign each other's devices out.
- If a user's sessions are revoked while they are logging in, that login is refused (`CREDENTIALS_CHANGED`) instead of producing a live token. This needs PostgreSQL 13+.

### Revoking inside your own transaction

`revoke_all_sessions`, `revoke_refresh_token`, and `revoke_refresh_token_sessions` accept `db_session=` — your own SQLAlchemy `AsyncSession` — so a revocation commits or rolls back together with your own writes, such as deleting a user's last login secret. See [Sessions & Token Lifetime](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/operations/sessions#revoke-sessions).

## Next Steps

- [fastapi-postgresql](../fastapi-postgresql/) — the base Native example, with role-based access control
- [dpop-standalone](../dpop-standalone/) — bind tokens to a client key; refresh tokens issued with a DPoP key bind every exchanged access token to it
- [GL-IAM docs: Refresh](https://gdplabs.gitbook.io/sdk/gl-identity-and-access-management/guides/traditional-iam/user-authentication/refresh)
