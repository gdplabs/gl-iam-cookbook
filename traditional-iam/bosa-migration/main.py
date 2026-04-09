"""BOSA Migration Example - GL-IAM FastAPI Application.

This example demonstrates how to migrate from BOSA Core Auth to GL-IAM,
covering all key features:

- 3-tier API Key model (PLATFORM, ORGANIZATION, PERSONAL)
- User management with password authentication
- JWT session management
- Third-party integration storage (encrypted credentials)

Run with: uv run main.py
API docs: http://localhost:8000/docs
"""

import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from config import settings
from deps import api_key_provider, ensure_all_tables, provider, third_party_provider
from routers import (
    api_keys_router,
    auth_router,
    health_router,
    third_party_router,
    users_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager.

    Handles startup and shutdown tasks:
    - Startup: Creates database tables and bootstrap API key if none exists
    - Shutdown: Closes database connections
    """
    # Startup
    print("Starting BOSA Migration Example...")
    print(f"Database: {settings.database_url.split('@')[-1]}")  # Hide credentials
    print(f"Organization: {settings.default_organization_id}")

    # Ensure all tables are created (including api_keys and third_party_integrations)
    print("Ensuring database tables exist...")
    await ensure_all_tables()
    print("Database tables ready.")

    # Create bootstrap key if no PLATFORM keys exist
    try:
        from gl_iam.core.types.api_key import ApiKeyTier

        existing_keys = await api_key_provider.list_api_keys(tier=ApiKeyTier.PLATFORM)
        if not existing_keys:
            print("\nNo PLATFORM API key found. Creating bootstrap key...")
            api_key, plain_key = await api_key_provider.create_bootstrap_key(
                name="Bootstrap Admin Key",
                scopes=["*"],  # All permissions
            )
            print("=" * 60)
            print("BOOTSTRAP API KEY CREATED (save this, shown only once!):")
            print(f"  Key ID: {api_key.id}")
            print(f"  Key:    {plain_key}")
            print("=" * 60)
            print("\nUse this key in the X-API-Key header to create other keys.")
        else:
            print(f"\nFound {len(existing_keys)} existing PLATFORM key(s)")
    except Exception as e:
        print(f"Warning: Could not check/create bootstrap key: {e}")

    yield

    # Shutdown
    print("\nShutting down...")
    await provider.close()
    if third_party_provider:
        await third_party_provider.close()


# OpenAPI security schemes
api_key_scheme = {
    "ApiKeyAuth": {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
        "description": "API Key for machine-to-machine authentication",
    }
}

# Create FastAPI app
app = FastAPI(
    title="BOSA Migration Example",
    openapi_tags=[
        {"name": "API Keys", "description": "3-tier API key management"},
        {"name": "Users", "description": "User management"},
        {"name": "Auth", "description": "Authentication (login/logout)"},
        {"name": "Third-Party", "description": "Third-party integrations"},
        {"name": "Health", "description": "Health check"},
    ],
    swagger_ui_parameters={"persistAuthorization": True},
    description="""
## GL-IAM BOSA Migration Cookbook

This example demonstrates how to migrate from BOSA Core Auth to GL-IAM.

### BOSA → GL-IAM Feature Mapping

| BOSA Feature | GL-IAM Equivalent | Endpoint |
|--------------|-------------------|----------|
| `create_client()` | `api_key_provider.create_api_key()` | `POST /api/keys` |
| `verify_client()` | `api_key_provider.validate_api_key()` | X-API-Key header |
| `create_user()` | `provider.create_user()` | `POST /api/users` |
| `get_user()` | `provider.get_user_by_id/email()` | `GET /api/users/{id}` |
| `authenticate_user()` | `provider.authenticate()` | `POST /api/auth/login` |
| `create_token()` | `provider.create_session()` | `POST /api/auth/login` |
| `verify_token()` | `provider.validate_session()` | Bearer token |
| `revoke_token()` | `provider.revoke_session()` | `POST /api/auth/logout` |
| `create_integration()` | `third_party_provider.store_integration()` | `POST /api/integrations` |
| `get_selected_integration()` | `third_party_provider.get_selected_integration()` | `GET /api/integrations/{connector}/selected` |
| `set_selected_integration()` | `third_party_provider.set_selected_integration()` | `POST /api/integrations/{connector}/selected` |
| `delete_integration()` | `third_party_provider.delete_integration()` | `DELETE /api/integrations/{id}` |
| `has_integration()` | `third_party_provider.has_integration()` | `GET /api/integrations/{connector}/exists` |

### Authentication Methods

- **API Key**: Use `X-API-Key` header for machine-to-machine authentication
- **Bearer Token**: Use `Authorization: Bearer <token>` for user sessions

### 3-Tier API Key Model

| Tier | org_id | user_id | Use Case |
|------|--------|---------|----------|
| PLATFORM | NULL | NULL | System bootstrap, cross-org operations |
| ORGANIZATION | REQUIRED | NULL | Organization-level automation |
| PERSONAL | REQUIRED | REQUIRED | User-level scripts/integrations |
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(health_router)
app.include_router(api_keys_router)
app.include_router(users_router)
app.include_router(auth_router)
app.include_router(third_party_router)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "BOSA Migration Example",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "features": [
            "3-tier API Key Model",
            "User Management",
            "JWT Sessions",
            "Third-Party Integrations",
        ],
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
    )
