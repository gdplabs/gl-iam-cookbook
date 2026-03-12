# SSO JWT Bridge (Option B — Simpler)

JWT-signed token SSO using a shared secret between the partner and your application. Simpler than Option A but with fewer security controls.

## Overview

This example demonstrates a **stateless SSO approach** where the partner signs a short-lived JWT with a shared secret. No partner registry, HMAC signatures, or one-time token storage is needed.

```
Partner System                    SSO Receiver (port 8000)
+-----------------+              +----------------------------+
| partner_client  |              | sso_receiver.py            |
|                 |              |                            |
| 1. Sign JWT     |  POST /sso/ | 2. App: verify JWT sig     |
|    with shared  | jwt-auth    | 3. GL-IAM: create user     |
|    secret       |  ---------> | 4. GL-IAM: create session  |
|                 |  <-- JWT -- |                            |
|                 |              |                            |
| 5. Access API   |  GET /me    | 6. GL-IAM: validate JWT    |
|    with JWT     |  ---------> |                            |
+-----------------+              +----------------------------+
                                          |
                                  +-------+-------+
                                  |  PostgreSQL   |
                                  |  (shared DB)  |
                                  +---------------+
```

### Tradeoffs vs Option A (sso-token-exchange)

| Feature | Option A (Token Exchange) | Option B (JWT Bridge) |
|---------|---------------------------|------------------------|
| Setup complexity | More complex | Simpler |
| Per-partner key rotation | Yes | No (shared secret) |
| Partner deactivation | Yes | No |
| Partner audit trail | Yes (registry) | No |
| Token replay protection | Yes (one-time tokens) | Relies on JWT `exp` |
| Dependencies | GL-IAM PartnerRegistry | PyJWT only |

**Use Option B when**: You have a single trusted partner and want the simplest possible integration.
**Use Option A when**: You need multiple partners, key rotation, or partner lifecycle management.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:

- PostgreSQL database running locally

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/sso-jwt-bridge/
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

   The setup script creates `.env` from `.env.example`. To customize:

   ```bash
   # Edit .env with your settings
   ```

   > **Important**: The `SSO_SHARED_SECRET` must be identical in the receiver's `.env` and the partner client's `--secret` argument.

4. **Start PostgreSQL** (if not running)

   ```bash
   docker run -d --name postgres \
     -e POSTGRES_PASSWORD=postgres \
     -e POSTGRES_DB=gliam \
     -p 5432:5432 \
     postgres:15
   ```

5. **Run the SSO receiver**

   ```bash
   uv run sso_receiver.py
   ```

   Output:

   ```
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

## Test the API

### Option A: Run the partner client script

In a second terminal:

```bash
cd gl-iam-cookbook/gl-iam/examples/sso-jwt-bridge/
uv run partner_client.py
```

### Option B: Manual curl commands

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Generate a partner JWT (using Python one-liner)
PARTNER_JWT=$(python3 -c "
import jwt, time
claims = {
    'iss': 'partner-portal',
    'sub': 'lok-user-002',
    'email': 'bob@lokadata.example.com',
    'display_name': 'Bob from Lokadata',
    'iat': int(time.time()),
    'exp': int(time.time()) + 60,
}
print(jwt.encode(claims, 'shared-secret-between-partner-and-glchat-min-32-chars', algorithm='HS256'))
")

echo "Partner JWT: $PARTNER_JWT"

# 3. Exchange partner JWT for session JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/sso/jwt-authenticate \
  -H "Content-Type: application/json" \
  -d "{\"partner_jwt\": \"${PARTNER_JWT}\"}" | jq -r '.access_token')

echo $TOKEN

# 4. Access protected endpoint
curl -s http://localhost:8000/api/v1/me \
  -H "Authorization: Bearer $TOKEN" | jq .
```

## Understanding the Code

### GL-IAM vs Application Code

| Component | GL-IAM SDK? | Description |
|-----------|:-----------:|-------------|
| JWT signature verification | **No** (app) | `PyJWT.decode()` with shared secret |
| User lookup by external ID | Yes | `get_user_by_external_identity()` |
| JIT user creation | Yes | `create_user()` + `link_external_identity()` |
| Session creation (JWT) | Yes | `create_session()` returns session JWT |
| JWT validation (session) | Yes | `get_current_user` FastAPI dependency |

### Partner JWT Claims

The partner signs a JWT with these required claims:

| Claim | Required | Description |
|-------|:--------:|-------------|
| `iss` | Yes | Issuer — must match `PARTNER_ISSUER` env var |
| `sub` | Yes | External user ID at the partner |
| `email` | Yes | User's email address |
| `exp` | Yes | Expiry (keep short, e.g. 60 seconds) |
| `display_name` | No | User's display name |
| `first_name` | No | User's first name |
| `last_name` | No | User's last name |

### Production Considerations

- **Use a strong shared secret**: At least 32 characters, stored securely (e.g., AWS Secrets Manager)
- **Keep JWT expiry short**: 30-60 seconds prevents replay attacks
- **HTTPS only**: Always use TLS for JWT transport
- **Consider Option A for multiple partners**: If you need per-partner secrets, rotation, or deactivation
- **Validate `iss` claim strictly**: Prevents cross-partner token misuse

## Reference

- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [SSO Token Exchange (Option A)](../sso-token-exchange/) — Recommended for production with multiple partners
