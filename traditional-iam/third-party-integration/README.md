# Third-Party Integration: Full GitHub OAuth Flow

This example demonstrates GL-IAM's `ThirdPartyIntegrationProvider` with a **pluggable connector pattern** (modeled after BOSA SDK) for managing third-party OAuth credentials with encrypted storage.

## What You'll Learn

- Full GitHub OAuth 2.0 web application flow
- Pluggable connector architecture (`BaseConnector` → `GitHubConnector`)
- Encrypted credential storage via GL-IAM
- Multi-account support (multiple GitHub accounts per user)
- Selected integration management (default account switching)
- Token revocation on integration removal
- Manual `IAMGateway` construction (wiring `third_party_provider` explicitly)

## Prerequisites

- **Python 3.11+** and [UV](https://docs.astral.sh/uv/) package manager
- **Docker** (for PostgreSQL)
- **GitHub account** (to create an OAuth App)

## GitHub OAuth App Setup

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **"New OAuth App"**
3. Fill in the form:
   - **Application name**: `GL-IAM Demo` (or any name)
   - **Homepage URL**: `http://localhost:8000`
   - **Authorization callback URL**: `http://localhost:8000/connectors/github/callback`
4. Click **"Register application"**
5. Copy the **Client ID**
6. Click **"Generate a new client secret"** and copy the **Client Secret**

> **Important**: The callback URL must match exactly: `http://localhost:8000/connectors/github/callback`

## Quick Start

### 1. Start PostgreSQL

```bash
docker run -d --name postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=gliam \
  -p 5432:5432 \
  postgres:15
```

### 2. Install dependencies and configure

```bash
cd gl-iam/examples/third-party-integration
./setup.sh
```

### 3. Configure GitHub OAuth credentials

Edit `.env` and set your GitHub OAuth App credentials:

```bash
GITHUB_CLIENT_ID=your-client-id-here
GITHUB_CLIENT_SECRET=your-client-secret-here
```

The setup script auto-generates `ENCRYPTION_KEY` for you. If not, generate one:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 4. Run the server

```bash
uv run main.py
```

The server starts at `http://localhost:8000`.

## Test the API

### Step 1: Register and Login

```bash
# Register a user
curl -s -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!", "display_name": "Test User"}'

# Login and get token
TOKEN=$(curl -s -X POST http://localhost:8000/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "SecurePass123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: $TOKEN"
```

### Step 2: Start GitHub OAuth Flow

```bash
# Initiate OAuth — returns a GitHub authorization URL
curl -s -X POST "http://localhost:8000/connectors/github/authorize?callback_url=http://localhost:3000/settings" \
  -H "Authorization: Bearer $TOKEN"
```

This returns:
```json
{
  "authorization_url": "https://github.com/login/oauth/authorize?client_id=...&state=..."
}
```

**Open the `authorization_url` in your browser.** GitHub will:
1. Ask you to authorize the application
2. Redirect to `http://localhost:8000/connectors/github/callback` with the code
3. The callback exchanges the code for a token, stores the integration, and redirects you to the `callback_url`

### Step 3: Verify the Integration

```bash
# Check if you have a GitHub integration
curl -s http://localhost:8000/integrations/github/check \
  -H "Authorization: Bearer $TOKEN"
# → {"has_integration": true}

# List all integrations
curl -s http://localhost:8000/integrations \
  -H "Authorization: Bearer $TOKEN"
# → [{"id": "...", "connector": "github", "user_identifier": "your-github-username", ...}]

# List only GitHub integrations
curl -s "http://localhost:8000/integrations?connector=github" \
  -H "Authorization: Bearer $TOKEN"

# Get the selected (default) GitHub integration
curl -s http://localhost:8000/integrations/github/selected \
  -H "Authorization: Bearer $TOKEN"
```

### Step 4: Manage Integrations

```bash
# Update integration metadata (use the integration ID from the list response)
curl -s -X PUT http://localhost:8000/integrations/INTEGRATION_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"metadata": {"team": "backend"}, "scopes": ["repo", "read:user"]}'

# If you have multiple GitHub accounts, switch the default:
curl -s -X POST http://localhost:8000/integrations/github/select \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"user_identifier": "other-github-username"}'
```

### Step 5: Remove Integration

```bash
# Remove integration (also revokes the GitHub token)
curl -s -X DELETE http://localhost:8000/integrations/github/your-github-username \
  -H "Authorization: Bearer $TOKEN"
# → {"success": true, "revoked": true}
```

### Admin Endpoints

```bash
# First, promote user to admin (requires direct DB access or another admin)
# Then list all GitHub integrations across users:
curl -s http://localhost:8000/admin/integrations/github \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Understanding the Code

### Connector Pattern (BOSA Plugin Pattern)

The connector pattern separates OAuth logic from integration storage:

```
connectors/
├── base.py      # BaseConnector abstract class
└── github.py    # GitHubConnector implementation
```

`BaseConnector` defines the interface that all connectors must implement:
- `initialize_authorization()` — Generate OAuth URL with CSRF state
- `handle_callback()` — Exchange code for token, store integration
- `revoke_token()` — Revoke token with the OAuth provider
- `register_routes()` — Register callback endpoint on FastAPI

To add a new connector (e.g., Google), create `connectors/google.py` that extends `BaseConnector`.

### OAuth Flow

```
User → POST /connectors/github/authorize (with Bearer token)
  ↓
Server creates CSRF state, returns GitHub OAuth URL
  ↓
User opens URL in browser → GitHub authorization page
  ↓
User clicks "Authorize" → GitHub redirects to:
GET /connectors/github/callback?code=xxx&state=yyy
  ↓
Server validates state, exchanges code for access token
  ↓
Server fetches GitHub username via API
  ↓
Server stores integration via GL-IAM (encrypted at rest)
  ↓
Server redirects user to callback_url (frontend)
```

### CSRF State Management

The state parameter prevents CSRF attacks during OAuth:

1. **Create**: Base64-encode `{user_id, org_id, state_code}` and cache `callback_url` keyed by `state_code`
2. **Validate**: Decode state, look up `state_code` in cache, delete after use (one-time)
3. **TTL**: State expires after 10 minutes (matching GitHub's code lifetime)

> **Production note**: This example uses an in-memory dict for state storage. In production, use Redis or another distributed cache for multi-process support.

### Manual Gateway Construction

Unlike the basic `fastapi-postgresql` example which uses `IAMGateway.from_fullstack_provider()`, this example constructs the gateway manually to wire the `third_party_provider`:

```python
gateway = IAMGateway(
    auth_provider=provider,
    user_store=provider,
    session_provider=provider,
    organization_provider=provider,
    api_key_provider=provider,
    third_party_provider=provider,  # Must be wired explicitly
)
```

### Encryption

GL-IAM encrypts OAuth tokens at rest using Fernet symmetric encryption. The `encryption_key` in `PostgreSQLConfig` is used to encrypt/decrypt the `auth_string` field. The `ThirdPartyIntegration` model exposes `auth_string_preview` (a masked version) for display purposes, never the actual token.

## Extending: Adding a New Connector

To add a Google OAuth connector:

1. Create `connectors/google.py`:

```python
from connectors.base import BaseConnector

class GoogleConnector(BaseConnector):
    @property
    def name(self) -> str:
        return "google"

    @property
    def scopes(self) -> list[str]:
        return ["openid", "email", "profile"]

    async def initialize_authorization(self, user_id, org_id, callback_url):
        # Build Google OAuth URL with state...
        pass

    async def handle_callback(self, code, state):
        # Exchange code, fetch profile, store integration...
        pass

    async def revoke_token(self, auth_string):
        # POST https://oauth2.googleapis.com/revoke...
        pass

    def register_routes(self, app, prefix):
        @app.get(f"{prefix}/callback")
        async def google_callback(request):
            # Handle Google OAuth callback...
            pass
```

2. Register it in `main.py` lifespan:

```python
google_connector = GoogleConnector(provider=provider)
connectors[google_connector.name] = google_connector
google_connector.register_routes(app, prefix="/connectors/google")
```

All integration management endpoints (`/integrations/*`) work automatically for any connector.

## Security Notes

- **Encrypted at rest**: OAuth tokens are encrypted using Fernet before database storage
- **CSRF protection**: State parameter prevents cross-site request forgery during OAuth
- **Token revocation**: Removing an integration revokes the token with GitHub
- **No token exposure**: API responses only show `auth_string_preview` (masked), never the actual token
- **State cache**: Uses in-memory dict with TTL — use Redis in production for multi-process deployments
- **Scoped access**: Integration endpoints require `ORG_MEMBER` role; admin endpoints require `ORG_ADMIN`

## API Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check |
| `POST` | `/register` | None | Register user |
| `POST` | `/login` | None | Login, get JWT |
| `GET` | `/me` | Bearer | Current user profile |
| `POST` | `/connectors/{name}/authorize` | ORG_MEMBER | Start OAuth flow |
| `GET` | `/connectors/{name}/callback` | None | OAuth callback (GitHub redirects here) |
| `GET` | `/integrations` | ORG_MEMBER | List user's integrations |
| `GET` | `/integrations/{connector}/selected` | ORG_MEMBER | Get default integration |
| `POST` | `/integrations/{connector}/select` | ORG_MEMBER | Set default integration |
| `GET` | `/integrations/{connector}/check` | ORG_MEMBER | Check if integration exists |
| `PUT` | `/integrations/{id}` | ORG_MEMBER | Update integration |
| `DELETE` | `/integrations/{connector}/{user_id}` | ORG_MEMBER | Remove integration + revoke token |
| `GET` | `/admin/integrations/{connector}` | ORG_ADMIN | List all integrations (admin) |
