"""
RBAC Showcase - Multi-Provider Example for GL-IAM.

This example demonstrates GL-IAM's RBAC (Role-Based Access Control) features
with support for both Keycloak and StackAuth providers.

Features demonstrated:
- Role mapping visualization (provider roles -> standard roles)
- Role hierarchy (PLATFORM_ADMIN > ORG_ADMIN > ORG_MEMBER)
- Standard role-based access control
- Provider-agnostic code (SIMI pattern)
- Role management authorization

To switch providers, set PROVIDER_TYPE in .env to "keycloak" or "stackauth".
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from config import ProviderType, settings
from gl_iam import IAMGateway
from gl_iam.core.exceptions import AuthenticationError, PermissionDeniedError
from gl_iam.fastapi import set_iam_gateway

# Load environment variables
load_dotenv()


def create_keycloak_gateway() -> IAMGateway:
    """Create IAMGateway with Keycloak provider."""
    from gl_iam.providers.keycloak import KeycloakConfig, KeycloakProvider

    config = KeycloakConfig(
        server_url=settings.keycloak_server_url,
        realm=settings.keycloak_realm,
        client_id=settings.keycloak_client_id,
        client_secret=settings.keycloak_client_secret,
    )
    provider = KeycloakProvider(config=config)
    return IAMGateway.from_fullstack_provider(provider), provider


def create_stackauth_gateway() -> IAMGateway:
    """Create IAMGateway with Stack Auth provider."""
    from gl_iam.providers.stackauth import StackAuthConfig, StackAuthProvider

    config = StackAuthConfig(
        base_url=settings.stackauth_base_url,
        project_id=settings.stackauth_project_id,
        publishable_client_key=settings.stackauth_publishable_client_key,
        secret_server_key=settings.stackauth_secret_server_key,
    )
    provider = StackAuthProvider(config)
    return IAMGateway.from_fullstack_provider(provider), provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Initializes the GL-IAM gateway with the configured provider.
    """
    # Create gateway based on provider type
    if settings.provider_type == ProviderType.KEYCLOAK:
        gateway, provider = create_keycloak_gateway()
        provider_name = "Keycloak"
        provider_url = settings.keycloak_server_url
    else:
        gateway, provider = create_stackauth_gateway()
        provider_name = "Stack Auth"
        provider_url = settings.stackauth_base_url

    # Set gateway with organization ID
    set_iam_gateway(gateway, default_organization_id=settings.get_organization_id())

    # Verify connection
    is_healthy = await provider.health_check()
    if is_healthy:
        print(f"Connected to {provider_name} at {provider_url}")
        print(f"Provider type: {settings.provider_type.value}")
        print(f"Organization ID: {settings.get_organization_id()}")
    else:
        print(f"Warning: {provider_name} health check failed")

    yield


# Create FastAPI app
app = FastAPI(
    title="GL-IAM RBAC Showcase",
    description="""
This example demonstrates GL-IAM's Role-Based Access Control (RBAC) features.

## Features

- **Role Mapping**: See how provider roles map to standard GL-IAM roles
- **Role Hierarchy**: Understand how PLATFORM_ADMIN > ORG_ADMIN > ORG_MEMBER works
- **Protected Areas**: Test access control at different role levels
- **Provider Comparison**: Compare Keycloak and StackAuth mappings
- **Role Management**: Admin endpoints for role assignment/removal

## Standard Roles

| Standard Role | Description |
|---------------|-------------|
| PLATFORM_ADMIN | Super administrator with access to all resources |
| ORG_ADMIN | Organization administrator |
| ORG_MEMBER | Regular organization member |

## Test Users (Keycloak)

| Email | Password | Roles |
|-------|----------|-------|
| platform-admin@example.com | platform123 | admin (with is_platform_admin flag) |
| admin@example.com | admin123 | admin |
| member@example.com | member123 | member |
| viewer@example.com | viewer123 | viewer |
""",
    version="1.0.0",
    lifespan=lifespan,
)


# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    return JSONResponse(
        status_code=401,
        content={
            "detail": str(exc),
            "error_type": "authentication_error",
        },
    )


@app.exception_handler(PermissionDeniedError)
async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
    """Handle permission denied errors."""
    return JSONResponse(
        status_code=403,
        content={
            "detail": str(exc),
            "error_type": "permission_denied",
        },
    )


# Include routers
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.rbac import router as rbac_router

app.include_router(auth_router)
app.include_router(rbac_router)
app.include_router(admin_router)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health():
    """Public health check endpoint."""
    return {
        "status": "healthy",
        "provider": settings.provider_type.value,
        "organization_id": settings.get_organization_id(),
    }


@app.get("/", tags=["Info"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "GL-IAM RBAC Showcase",
        "provider": settings.provider_type.value,
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "auth": {
                "get_token": "POST /auth/token",
                "provider_info": "GET /auth/provider",
            },
            "rbac": {
                "mapping_table": "GET /rbac/mapping-table",
                "hierarchy": "GET /rbac/hierarchy",
                "my_roles": "GET /rbac/my-roles",
                "test_access": "GET /rbac/test-access",
                "provider_comparison": "GET /rbac/provider-comparison",
                "platform_admin_area": "GET /rbac/platform-admin-area",
                "admin_area": "GET /rbac/admin-area",
                "member_area": "GET /rbac/member-area",
            },
            "admin": {
                "assign_role": "POST /admin/roles/assign",
                "remove_role": "POST /admin/roles/remove",
                "available_roles": "GET /admin/roles/available",
                "authorization_rules": "GET /admin/authorization-rules",
            },
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
