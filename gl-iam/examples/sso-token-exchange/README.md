# SSO Token Exchange (Option A — Recommended)

Server-side token exchange SSO using GL-IAM's PartnerRegistryProvider with HMAC-SHA256 signature validation and one-time tokens.

## Real-World Context

This example is based on a real product requirement: **Lokadata x GLChat SSO integration**.

- **Lokadata** has its own website with its own login system
- **GLChat** is embedded as an AI chat widget (iframe) inside Lokadata's website
- **Problem**: Users had to log in to Lokadata first, then separately log in to GLChat — a poor user experience
- **Solution**: When a user logs in to Lokadata, they should be automatically authenticated in the GLChat widget

In this architecture, Lokadata acts as the **Identity Provider (IdP)** that pushes user identity to GLChat. The cookbook example simulates this flow: `partner_client.py` represents the Lokadata backend, and `sso_receiver.py` represents the GLChat backend using GL-IAM.

> See the full architecture document: [Lokadata x GLChat SSO Architecture](https://github.com/gdplabs/gl-iam-cookbook/blob/main/docs/Lokadata-GLChat-SSO-Architecture.md)

### Why Option A for this case?

Option A (Token Exchange) is recommended for Lokadata x GLChat because:
- **Multiple partners**: GLChat may be embedded by other partner websites in the future, each needing their own consumer key
- **Key rotation**: Partners can rotate their consumer secrets with optional grace period for zero-downtime deployments
- **Partner lifecycle**: Partners can be deactivated without code changes
- **Security restrictions**: Per-partner email domain allowlists, IP restrictions, user caps, and role constraints
- **Audit trail**: Every partner registration and SSO attempt is tracked

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

   The setup script creates `.env` from `.env.example` and generates an encryption key. To customize:

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

# 2. Register an SSO partner with security restrictions
curl -s -X POST http://localhost:8000/admin/partners \
  -H "Content-Type: application/json" \
  -d '{
    "partner_name": "Lokadata Portal",
    "allowed_origins": ["https://lokadata.example.com"],
    "sso_mode": "idp_initiated",
    "user_provisioning": "jit",
    "allowed_email_domains": ["lokadata.example.com"],
    "max_users": 1000
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
| Secret rotation | Yes | `rotate_consumer_secret()` with optional `grace_period_seconds` |
| HMAC signature validation | Yes | `validate_partner_signature()` verifies signature + email domain |
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

### Who Calls What? (Production Architecture)

In production, there are **three separate systems** involved. The `partner_client.py` script simulates both the partner backend and the GLChat widget since there's no real iframe in this demo.

```
                          Lokadata Backend              GLChat Widget (iframe)        GLChat Backend
                          (partner server)              (JS in browser)              (sso_receiver.py)
                          ─────────────────             ─────────────────            ─────────────────
Step 1 (one-time):        POST /admin/partners  ──────────────────────────────────>  Register partner
                          ← consumer_key + secret ◄────────────────────────────────

Step 2:                   Compute HMAC signature
                          (local, no network call)

Step 3 (server-to-srv):   POST /api/v1/sso/token ────────────────────────────────>  Validate HMAC
                          ← one-time sso_token ◄──────────────────────────────────  Generate token

                          Load iframe:
                          <iframe src="glchat.com
                          /widget?sso_token=xxx">
                                    │
                                    ▼
Step 4:                              Read sso_token from URL
                                     POST /api/v1/sso/authenticate ───────────>  Consume token
                                     ← session JWT ◄──────────────────────────  Create user + session
                                     Store JWT in JS memory

Step 5:                              GET /api/v1/me (Bearer JWT) ─────────────>  Validate JWT
                                     ← user profile ◄─────────────────────────  Return user
                                     Render chat UI ✓
```

**Key point**: The GLChat widget calls its **own backend** (same-origin: `glchat.com` → `glchat.com`), so no CORS is needed. The session JWT is stored in JavaScript memory, never exposed in URLs or logs.

### Production Considerations

- **Replace in-memory dict with Redis**: Use `SET key value EX ttl` and `GETDEL key` for atomic one-time token storage
- **Protect admin endpoints**: Add `require_org_admin()` or `require_platform_admin()` dependency
- **HTTPS only**: Always use TLS in production for signature and token transport
- **Rate limiting**: Add rate limits on `/api/v1/sso/token` to prevent brute-force
- **Logging**: Add structured logging for audit trail
- **Email domain restrictions**: Set `allowed_email_domains` per partner to prevent unauthorized email assertions
- **Grace period for rotation**: Use `grace_period_seconds` (e.g., 3600) when rotating secrets in distributed deployments
- **Enforce IP allowlists**: Check `partner.allowed_source_ips` in your HTTP middleware (GL-IAM stores but doesn't enforce)
- **Enforce user caps**: Check `partner.max_users` during JIT provisioning (GL-IAM stores but doesn't enforce)

## Reference

- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam)
- [GL-IAM PartnerRegistryProvider Protocol](https://gdplabs.gitbook.io/sdk/gl-iam/protocols/partner-registry)
- [SSO Architecture Document](../../docs/Lokadata-GLChat-SSO-Architecture.md)
