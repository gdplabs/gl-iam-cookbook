# BOSA Migration Example

Migrate from BOSA Core Auth to GL-IAM. This comprehensive example demonstrates all legacy BOSA Core Auth features implemented in GL-IAM's PostgreSQLProvider.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- PostgreSQL database running locally
- Encryption key for third-party integrations (optional)

## Getting Started

1. **Clone the repository & open the directory**

   ```bash
   git clone https://github.com/GDP-ADMIN/gl-iam-cookbook.git
   cd gl-iam-cookbook/gl-iam/examples/bosa-migration/
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

3. **Configure environment**

   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

   Generate encryption key for third-party integrations:
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

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

   On first run, a bootstrap API key will be created and displayed. **Save this key!**

   ```
   ============================================================
   BOOTSTRAP API KEY CREATED (save this, shown only once!):
     Key ID: 12345678-...
     Key:    gliam_abc123...
   ============================================================
   ```

6. **Open API documentation**

   Navigate to http://localhost:8000/docs

## BOSA → GL-IAM Feature Mapping

| BOSA Feature | GL-IAM Equivalent | Endpoint |
|--------------|-------------------|----------|
| `create_client()` | `api_key_provider.create_api_key(tier=ORGANIZATION)` | `POST /api/keys` |
| `verify_client()` | `api_key_provider.validate_api_key()` | X-API-Key header |
| `create_user()` | `provider.create_user()` | `POST /api/users` |
| `get_user()` | `provider.get_user_by_id/email()` | `GET /api/users/{id}` |
| `authenticate_user()` | `provider.authenticate()` | `POST /api/auth/login` |
| `create_token()` | `provider.create_session()` | `POST /api/auth/login` |
| `verify_token()` | `provider.validate_session()` | Bearer token |
| `revoke_token()` | `provider.revoke_session()` | `POST /api/auth/logout` |
| `create_integration()` | `third_party_provider.store_integration()` | `POST /api/integrations` |
| `get_integration()` | `third_party_provider.get_integration_by_user_identifier()` | `GET /api/integrations/{connector}/{user_identifier}` |
| `get_selected_integration()` | `third_party_provider.get_selected_integration()` | `GET /api/integrations/{connector}/selected` |
| `set_selected_integration()` | `third_party_provider.set_selected_integration()` | `POST /api/integrations/{connector}/selected` |
| `delete_integration()` | `third_party_provider.delete_integration()` | `DELETE /api/integrations/{id}` |
| `has_integration()` | `third_party_provider.has_integration()` | `GET /api/integrations/{connector}/exists` |

## Test the API

### 1. Create Organization API Key (using bootstrap key)

```bash
# Use the bootstrap key from startup
curl -X POST http://localhost:8000/api/keys \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gliam_YOUR_BOOTSTRAP_KEY" \
  -d '{
    "name": "Admin Key",
    "tier": "organization",
    "scopes": ["keys:create", "users:create", "api:read", "api:write"]
  }'
```

### 2. Create a User

```bash
curl -X POST http://localhost:8000/api/users \
  -H "Content-Type: application/json" \
  -H "X-API-Key: gliam_YOUR_ORG_KEY" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "display_name": "Test User"
  }'
```

### 3. Login to Get JWT Token

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
# Returns: {"access_token": "eyJ...", "token_type": "Bearer", ...}
```

### 4. Get Current User

```bash
curl http://localhost:8000/api/users/me \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 5. Store Third-Party Integration (GitHub example)

```bash
curl -X POST http://localhost:8000/api/integrations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "connector": "github",
    "auth_string": "ghp_xxxxxxxxxxxxxxxxxxxx",
    "user_identifier": "johndoe",
    "scopes": ["repo", "user"]
  }'
```

### 6. List Integrations

```bash
curl "http://localhost:8000/api/integrations?connector=github" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 7. Get Selected Integration

```bash
curl http://localhost:8000/api/integrations/github/selected \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### 8. Logout

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## 3-Tier API Key Model

GL-IAM uses a 3-tier API key ownership model:

| Tier | org_id | user_id | Use Case |
|------|--------|---------|----------|
| **PLATFORM** | NULL | NULL | System bootstrap, cross-org operations |
| **ORGANIZATION** | REQUIRED | NULL | Organization-level automation, admin keys |
| **PERSONAL** | REQUIRED | REQUIRED | User-level scripts, personal integrations |

### Key Creation Rules

- **PLATFORM** keys can create any tier
- **ORGANIZATION** keys can create ORGANIZATION or PERSONAL tier
- **PERSONAL** keys cannot create other keys
- Child keys cannot have scopes that exceed parent key's scopes

### Common Scopes

| Scope | Description |
|-------|-------------|
| `*` | All permissions (admin) |
| `keys:create` | Create new API keys |
| `users:create` | Create new users |
| `api:read` | Read access to API |
| `api:write` | Write access to API |

## Project Structure

```
bosa-migration/
├── README.md           # This file
├── pyproject.toml      # UV project config
├── .env.example        # Environment template
├── setup.sh            # Unix setup script
├── setup.bat           # Windows setup script
├── main.py             # FastAPI application
├── config.py           # Pydantic Settings
├── deps.py             # FastAPI dependencies (auth, providers)
├── schemas.py          # Request/response models
└── routers/
    ├── __init__.py
    ├── api_keys.py     # 3-tier API key management
    ├── users.py        # User CRUD operations
    ├── auth.py         # Login/logout with JWT
    ├── third_party.py  # Third-party integrations
    └── health.py       # Health check
```

## Understanding the Code

### Provider Initialization (deps.py)

```python
from gl_iam.providers.postgresql import (
    PostgreSQLProvider,
    PostgreSQLApiKeyProvider,
    PostgreSQLThirdPartyProvider,
    PostgreSQLUserStoreConfig,
)

# Configuration
config = PostgreSQLUserStoreConfig(
    database_url=settings.database_url,
    secret_key=settings.secret_key,
    encryption_key=settings.encryption_key,
    enable_auth_hosting=True,
    auto_create_tables=True,
)

# Initialize providers
provider = PostgreSQLProvider(config)
api_key_provider = PostgreSQLApiKeyProvider(provider._engine, config)
third_party_provider = PostgreSQLThirdPartyProvider(
    provider._engine,
    encryption_key=config.encryption_key,
)
```

### Authentication Flow

```
API Key Authentication:
  Request → X-API-Key header → validate_api_key() → ApiKeyIdentity

JWT Authentication:
  Login → authenticate() → create_session() → JWT Token
  Request → Authorization header → validate_session() → User
```

### Third-Party Integration Flow

```
Store: auth_string → Fernet encrypt → PostgreSQL
Retrieve: PostgreSQL → Fernet decrypt → auth_string (internal only)
Display: Show masked preview (ghp_****xxxx)
```

## Reference

- [GL-IAM SDK Documentation](https://gdplabs.gitbook.io/sdk)
- [BOSA Core Auth Migration Guide](https://gdplabs.gitbook.io/sdk/tutorials/gl-iam/bosa-migration)
