"""Third-party integration example with full GitHub OAuth flow.

This example demonstrates how to use GL-IAM's ThirdPartyIntegrationProvider
with a pluggable connector pattern (modeled after BOSA SDK) for managing
external service credentials with encrypted storage.

Features demonstrated:
    - Full GitHub OAuth 2.0 web application flow
    - Pluggable connector pattern (BaseConnector → GitHubConnector)
    - Encrypted credential storage via GL-IAM
    - Multi-account support (multiple GitHub accounts per user)
    - Selected integration management (default account switching)
    - Token revocation on integration removal
    - Manual IAMGateway construction (wiring third_party_provider explicitly)
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from connectors.base import BaseConnector
from connectors.github import GitHubConnector
from gl_iam import IAMGateway, User
from gl_iam.core.exceptions import (
    IntegrationNotFoundError,
)
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user,
    get_iam_gateway,
    require_org_admin,
    require_org_member,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLProvider, PostgreSQLConfig

load_dotenv()


# ============================================================================
# Application Setup
# ============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize GL-IAM gateway with all 6 providers including third-party."""
    default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        encryption_key=os.getenv("ENCRYPTION_KEY"),
        enable_auth_hosting=True,
        auto_create_tables=True,
        default_org_id=default_org_id,
    )
    provider = PostgreSQLProvider(config)

    gateway = IAMGateway(
        auth_provider=provider,
        user_store=provider,
        session_provider=provider,
        organization_provider=provider,
        api_key_provider=provider,
        third_party_provider=provider,
    )
    set_iam_gateway(gateway, default_organization_id=default_org_id)

    github_connector = GitHubConnector(provider=provider)
    connectors: dict[str, BaseConnector] = {github_connector.name: github_connector}

    for connector in connectors.values():
        connector.register_routes(app, prefix=f"/connectors/{connector.name}")

    app.state.connectors = connectors

    yield
    await provider.close()


app = FastAPI(title="Third-Party Integration API", lifespan=lifespan)


# ============================================================================
# Helpers
# ============================================================================
def get_connector(name: str) -> BaseConnector:
    """Get a registered connector by name or raise 404."""
    connectors: dict[str, BaseConnector] = app.state.connectors
    connector = connectors.get(name)
    if connector is None:
        raise HTTPException(status_code=404, detail=f"Connector '{name}' not found")
    return connector


def get_org_id() -> str:
    """Get the default organization ID from environment."""
    return os.getenv("DEFAULT_ORGANIZATION_ID", "default")


# ============================================================================
# Request/Response Models
# ============================================================================
class RegisterRequest(BaseModel):
    """Request model for user registration."""

    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for user login."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """Response model containing access token."""

    access_token: str
    token_type: str


class UserResponse(BaseModel):
    """Response model for user data."""

    id: str
    email: str
    display_name: str | None


class AuthorizeResponse(BaseModel):
    """Response model for OAuth authorization initiation."""

    authorization_url: str


class IntegrationResponse(BaseModel):
    """Response model for a third-party integration."""

    id: str
    connector: str
    user_identifier: str
    auth_string_preview: str | None
    scopes: list[str]
    is_selected: bool
    is_active: bool
    created_at: str | None
    metadata: dict


class SetSelectedRequest(BaseModel):
    """Request model for setting the selected (default) integration."""

    user_identifier: str


class UpdateIntegrationRequest(BaseModel):
    """Request model for updating an integration."""

    scopes: list[str] | None = None
    metadata: dict | None = None
    is_active: bool | None = None


# ============================================================================
# Public Endpoints
# ============================================================================
@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy"}


@app.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest):
    """Register a new user with ORG_MEMBER role."""
    gateway = get_iam_gateway()
    org_id = get_org_id()

    result = await gateway.create_user_with_password(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        password=request.password,
        organization_id=org_id,
    )

    if not result.is_ok:
        raise HTTPException(status_code=400, detail=result.error.message)
    user = result.value

    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Authenticate and get access token."""
    gateway = get_iam_gateway()
    org_id = get_org_id()

    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=org_id,
    )

    if result.is_ok:
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    else:
        raise HTTPException(status_code=401, detail=result.error.message)


# ============================================================================
# Protected Endpoints
# ============================================================================
@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return UserResponse(id=user.id, email=user.email, display_name=user.display_name)


# ============================================================================
# OAuth Flow Endpoints
# ============================================================================
@app.post(
    "/connectors/{connector_name}/authorize",
    response_model=AuthorizeResponse,
)
async def authorize(
    connector_name: str,
    callback_url: str = Query(
        ..., description="URL to redirect user to after OAuth completes"
    ),
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """Start the OAuth flow for a third-party connector.

    Returns an authorization URL that the client should redirect the user to.
    After the user authorizes, GitHub redirects to our callback endpoint which
    stores the integration and then redirects the user to the callback_url.
    """
    connector = get_connector(connector_name)
    org_id = get_org_id()

    authorization_url = await connector.initialize_authorization(
        user_id=user.id, org_id=org_id, callback_url=callback_url
    )
    return AuthorizeResponse(authorization_url=authorization_url)


# ============================================================================
# Integration Management Endpoints
# ============================================================================
@app.get("/integrations", response_model=list[IntegrationResponse])
async def list_integrations(
    connector: str | None = Query(None, description="Filter by connector name"),
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """List the current user's third-party integrations.

    Optionally filter by connector name (e.g., ?connector=github).
    """
    gateway = get_iam_gateway()
    org_id = get_org_id()

    integrations = await gateway.third_party_provider.get_integrations(
        user_id=user.id, organization_id=org_id, connector=connector
    )
    return [
        IntegrationResponse(
            id=i.id,
            connector=i.connector,
            user_identifier=i.user_identifier,
            auth_string_preview=i.auth_string_preview,
            scopes=i.scopes,
            is_selected=i.is_selected,
            is_active=i.is_active,
            created_at=i.created_at.isoformat() if i.created_at else None,
            metadata=i.metadata,
        )
        for i in integrations
    ]


@app.get(
    "/integrations/{connector_name}/selected", response_model=IntegrationResponse | None
)
async def get_selected_integration(
    connector_name: str,
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """Get the selected (default) integration for a connector."""
    gateway = get_iam_gateway()
    org_id = get_org_id()

    integration = await gateway.third_party_provider.get_selected_integration(
        user_id=user.id, connector=connector_name, organization_id=org_id
    )
    if integration is None:
        return None

    return IntegrationResponse(
        id=integration.id,
        connector=integration.connector,
        user_identifier=integration.user_identifier,
        auth_string_preview=integration.auth_string_preview,
        scopes=integration.scopes,
        is_selected=integration.is_selected,
        is_active=integration.is_active,
        created_at=integration.created_at.isoformat()
        if integration.created_at
        else None,
        metadata=integration.metadata,
    )


@app.post("/integrations/{connector_name}/select")
async def set_selected(
    connector_name: str,
    request: SetSelectedRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """Set the selected (default) integration for a connector.

    Useful when a user has multiple accounts for the same connector
    and wants to switch which one is the default.
    """
    gateway = get_iam_gateway()
    org_id = get_org_id()

    try:
        await gateway.third_party_provider.set_selected_integration(
            user_id=user.id,
            connector=connector_name,
            user_identifier=request.user_identifier,
            organization_id=org_id,
        )
        return {"success": True}
    except IntegrationNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.get("/integrations/{connector_name}/check")
async def check_integration(
    connector_name: str,
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """Check if the current user has at least one integration for a connector."""
    gateway = get_iam_gateway()
    org_id = get_org_id()

    has = await gateway.third_party_provider.has_integration(
        user_id=user.id, connector=connector_name, organization_id=org_id
    )
    return {"has_integration": has}


@app.put("/integrations/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    request: UpdateIntegrationRequest,
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """Update an integration's metadata, scopes, or active status."""
    gateway = get_iam_gateway()
    org_id = get_org_id()

    try:
        integration = await gateway.third_party_provider.update_integration(
            integration_id=integration_id,
            organization_id=org_id,
            scopes=request.scopes,
            metadata=request.metadata,
            is_active=request.is_active,
        )
        return IntegrationResponse(
            id=integration.id,
            connector=integration.connector,
            user_identifier=integration.user_identifier,
            auth_string_preview=integration.auth_string_preview,
            scopes=integration.scopes,
            is_selected=integration.is_selected,
            is_active=integration.is_active,
            created_at=integration.created_at.isoformat()
            if integration.created_at
            else None,
            metadata=integration.metadata,
        )
    except IntegrationNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


@app.delete("/integrations/{connector_name}/{user_identifier}")
async def remove_integration(
    connector_name: str,
    user_identifier: str,
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """Remove an integration and revoke the token with the third-party service.

    This performs two operations:
    1. Revokes the OAuth token with the provider (e.g., GitHub)
    2. Deletes the integration from GL-IAM storage
    """
    gateway = get_iam_gateway()
    org_id = get_org_id()
    connector = get_connector(connector_name)

    # Look up the integration to get the decrypted token for revocation
    integration = await gateway.third_party_provider.get_integration_by_user_identifier(
        user_id=user.id,
        connector=connector_name,
        user_identifier=user_identifier,
        organization_id=org_id,
    )
    if integration is None:
        raise HTTPException(status_code=404, detail="Integration not found")

    # Revoke the token with the third-party provider
    auth_string = await gateway.third_party_provider.get_decrypted_auth_string(
        integration_id=integration.id, organization_id=org_id
    )
    if auth_string:
        await connector.revoke_token(auth_string)

    # Delete from GL-IAM storage
    try:
        await gateway.third_party_provider.delete_integration_by_user_identifier(
            user_id=user.id,
            connector=connector_name,
            user_identifier=user_identifier,
            organization_id=org_id,
        )
        return {"success": True, "revoked": True}
    except IntegrationNotFoundError as e:
        raise HTTPException(status_code=404, detail=e.message) from e


# ============================================================================
# Admin Endpoints
# ============================================================================
@app.get(
    "/admin/integrations/{connector_name}", response_model=list[IntegrationResponse]
)
async def admin_list_integrations(
    connector_name: str,
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_admin()),
):
    """List all integrations for a connector (admin only).

    Useful for administrators to see which users have connected a service.
    """
    gateway = get_iam_gateway()
    org_id = get_org_id()

    integrations = await gateway.third_party_provider.get_integrations_by_connector(
        connector=connector_name, organization_id=org_id
    )
    return [
        IntegrationResponse(
            id=i.id,
            connector=i.connector,
            user_identifier=i.user_identifier,
            auth_string_preview=i.auth_string_preview,
            scopes=i.scopes,
            is_selected=i.is_selected,
            is_active=i.is_active,
            created_at=i.created_at.isoformat() if i.created_at else None,
            metadata=i.metadata,
        )
        for i in integrations
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
