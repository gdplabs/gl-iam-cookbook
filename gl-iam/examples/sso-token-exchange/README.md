# SSO Token Exchange (Option A — Recommended)

Server-side token exchange SSO using GL-IAM's PartnerRegistryProvider with HMAC-SHA256 signature validation and one-time tokens.

## Overview

This example demonstrates **IdP-Initiated SSO** where an external partner system authenticates users and sends them to your application. The flow has two phases:

```
Partner System                    SSO Receiver (port 8000)
+-----------------+              +----------------------------+
| partner_client  |              | sso_receiver.py            |
|                 |  POST /sso/  |                            |
| 1. Compute HMAC |  -- token -> | 2. GL-IAM: validate sig    |
|    signature    |              | 3. App: store one-time     |
|                 |  <- token -- |    token (TTL: 60s)        |
|                 |              |                            |
| 4. Exchange     |  POST /sso/  | 5. App: consume token      |
|    token        | authenticate | 6. GL-IAM: create user     |
|                 |  ----------> | 7. GL-IAM: create session  |
|                 |  <-- JWT --- |                            |
|                 |              |                            |
| 8. Access API   |  GET /me     | 9. GL-IAM: validate JWT    |
|    with JWT     |  ----------> |                            |
+-----------------+              +----------------------------+
                                          |
                                  +-------+-------+
                                  |  PostgreSQL   |
                                  |  (shared DB)  |
                                  +---------------+
```

**Phase 1 — Server-to-server**: Partner computes HMAC-SHA256 signature over user data and sends it to `/api/v1/sso/token`. GL-IAM validates the signature against the registered partner's secret. The application stores a one-time token.

**Phase 2 — Client-side exchange**: Partner widget sends the one-time token to `/api/v1/sso/authenticate`. The application consumes the token, GL-IAM provisions the user (JIT) and creates a session, returning a JWT.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:

- PostgreSQL database running locally

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/sso-token-exchange/
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

   The setup script creates `.env` from `.env.example` and generates a Fernet encryption key. To customize:

   ```bash
   # Edit .env with your settings
   ```

   > **Important**: The `ENCRYPTION_KEY` is required for HMAC signature validation. The setup script generates one automatically on Unix systems.

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
cd gl-iam-cookbook/gl-iam/examples/sso-token-exchange/
uv run partner_client.py
```

The script runs through the full SSO flow automatically and prints each step.

### Option B: Manual curl commands

```bash
# 1. Health check
curl http://localhost:8000/health

# 2. Register an SSO partner (save the consumer_key and consumer_secret!)
curl -s -X POST http://localhost:8000/admin/partners \
  -H "Content-Type: application/json" \
  -d '{
    "partner_name": "Lokadata Portal",
    "allowed_origins": ["https://lokadata.example.com"],
    "sso_mode": "idp_initiated",
    "user_provisioning": "jit"
  }' | jq .

# Save credentials from the response:
CONSUMER_KEY="sso_xxx"       # from response
CONSUMER_SECRET="yyy"        # from response (shown only once!)

# 3. List registered partners
curl -s http://localhost:8000/admin/partners | jq .

# 4. Generate HMAC signature and request one-time token
# (In practice, the partner system computes this server-side)
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
PAYLOAD='{"email":"alice@lokadata.example.com","display_name":"Alice","external_id":"lok-001"}'
MESSAGE="${TIMESTAMP}|${CONSUMER_KEY}|${PAYLOAD}"
SIGNATURE=$(echo -n "$MESSAGE" | openssl dgst -sha256 -hmac "$CONSUMER_SECRET" | awk '{print $2}')

curl -s -X POST http://localhost:8000/api/v1/sso/token \
  -H "Content-Type: application/json" \
  -d "{
    \"consumer_key\": \"${CONSUMER_KEY}\",
    \"signature\": \"${SIGNATURE}\",
    \"timestamp\": \"${TIMESTAMP}\",
    \"payload\": \"${PAYLOAD}\"
  }" | jq .

# Save the one-time token from the response:
SSO_TOKEN="xxx"

# 5. Exchange one-time token for JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/sso/authenticate \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"${SSO_TOKEN}\"}" | jq -r '.access_token')

echo $TOKEN

# 6. Access protected endpoint with JWT
curl -s http://localhost:8000/api/v1/me \
  -H "Authorization: Bearer $TOKEN" | jq .

# 7. Verify token replay fails (one-time use)
curl -s -X POST http://localhost:8000/api/v1/sso/authenticate \
  -H "Content-Type: application/json" \
  -d "{\"token\": \"${SSO_TOKEN}\"}"
# Expected: 401 Unauthorized
```

## Understanding the Code

### GL-IAM vs Application Code

The SSO flow combines GL-IAM SDK calls with application-specific logic. Each section in `sso_receiver.py` is annotated with `# --- GL-IAM ---` or `# --- Application code ---` comments.

| Component | GL-IAM SDK? | Description |
|-----------|:-----------:|-------------|
| Partner registration | Yes | `register_partner()` generates consumer key/secret |
| Partner listing | Yes | `list_partners()` queries registered partners |
| Secret rotation | Yes | `rotate_consumer_secret()` rotates credentials |
| HMAC signature validation | Yes | `validate_partner_signature()` verifies signature |
| One-time token generation | **No** (app) | `secrets.token_urlsafe()` + in-memory dict |
| One-time token consumption | **No** (app) | Dict pop with TTL check |
| User lookup by external ID | Yes | `get_user_by_external_identity()` |
| JIT user creation | Yes | `create_user()` + `link_external_identity()` |
| Session creation (JWT) | Yes | `create_session()` returns JWT |
| JWT validation | Yes | `get_current_user` FastAPI dependency |

### HMAC Signature Format

GL-IAM validates signatures using:

```
HMAC-SHA256(consumer_secret, "timestamp|consumer_key|payload")
```

The partner computes this with their consumer secret (received during registration). GL-IAM decrypts the stored secret and performs constant-time comparison.

### Token Exchange Sequence

```
1. Partner registers once:
   POST /admin/partners → { consumer_key, consumer_secret }

2. For each SSO login:
   Partner → POST /api/v1/sso/token (HMAC signed) → one-time token
   Widget  → POST /api/v1/sso/authenticate (token) → JWT
   Widget  → GET /api/v1/me (JWT) → user profile
```

### Production Considerations

- **Replace in-memory dict with Redis**: Use `SET key value EX ttl` and `GETDEL key` for atomic one-time token storage
- **Protect admin endpoints**: Add `require_org_admin()` or `require_platform_admin()` dependency
- **HTTPS only**: Always use TLS in production for signature and token transport
- **Rate limiting**: Add rate limits on `/api/v1/sso/token` to prevent brute-force
- **Logging**: Add structured logging for audit trail

## Reference

- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL-IAM PartnerRegistryProvider Protocol](https://gdplabs.gitbook.io/sdk/gl-iam/protocols/partner-registry)
- [SSO Architecture Document](../../docs/Lokadata-GLChat-SSO-Architecture.md)
