"""
SAML 2.0 Federation via Keycloak with GL-IAM.

This example demonstrates how to authenticate users from a SAML 2.0
Identity Provider through Keycloak. The GL-IAM code is identical to a
standard Keycloak setup — Keycloak handles SAML protocol translation.

Architecture:
    SAML IdP (Keycloak #2) ←→ Keycloak SP ←→ FastAPI + GL-IAM

For testing, we use a second Keycloak instance as the SAML IdP.
In production, this would be Azure AD, Okta, ADFS, etc.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from gl_iam import IAMGateway, User
from gl_iam.fastapi import (
    get_current_user,
    require_org_admin,
    require_org_member,
    set_iam_gateway,
)
from gl_iam.providers.keycloak import KeycloakConfig, KeycloakProvider

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialize GL-IAM with Keycloak provider.

    Keycloak handles SAML federation transparently — no SAML-specific
    code is needed in the application.
    """
    config = KeycloakConfig(
        server_url=os.getenv("KEYCLOAK_SERVER_URL"),
        realm=os.getenv("KEYCLOAK_REALM"),
        client_id=os.getenv("KEYCLOAK_CLIENT_ID"),
        client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET"),
    )
    provider = KeycloakProvider(config=config)
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway, default_organization_id=os.getenv("KEYCLOAK_REALM"))

    is_healthy = await provider.health_check()
    if is_healthy:
        print(f"Connected to Keycloak at {os.getenv('KEYCLOAK_SERVER_URL')}")
        print("SAML users can authenticate through Keycloak's Identity Brokering")

    yield


app = FastAPI(title="GL-IAM SAML via Keycloak", lifespan=lifespan)


class UserResponse(BaseModel):
    """Response model for user data with roles."""
    id: str
    email: str
    display_name: str | None
    roles: list[str]


@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "provider": "keycloak", "federation": "saml"}


@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """
    Get current user profile.

    Works for both SAML-federated users and local Keycloak users.
    GL-IAM doesn't distinguish between them — Keycloak maps SAML
    attributes to OIDC claims before issuing the token.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
    )


@app.get("/member-area")
async def member_area(
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_member()),
):
    """
    Member area endpoint.

    Accessible by ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN.
    SAML users get roles via Keycloak's attribute-to-role mapping.
    """
    return {"message": f"Welcome {user.email}!", "access_level": "member"}


@app.get("/admin-area")
async def admin_area(
    user: User = Depends(get_current_user),
    _: None = Depends(require_org_admin()),
):
    """
    Admin area endpoint.

    Accessible by ORG_ADMIN or PLATFORM_ADMIN only.
    """
    return {"message": f"Welcome Admin {user.email}!", "access_level": "admin"}


@app.get("/login")
async def login_redirect():
    """
    Show the Keycloak login URL.

    Users will see the SAML IdP option on the Keycloak login page.
    SAML requires browser-based flow (not Resource Owner Password Grant).
    """
    keycloak_url = os.getenv("KEYCLOAK_SERVER_URL")
    realm = os.getenv("KEYCLOAK_REALM")
    return {
        "login_url": f"{keycloak_url}/realms/{realm}/account",
        "note": "Open this URL in a browser. Click the SAML IdP button to authenticate.",
        "token_endpoint": (
            f"{keycloak_url}/realms/{realm}/protocol/openid-connect/token"
        ),
    }


@app.get("/callback")
async def callback(code: str = ""):
    """
    OAuth2 callback endpoint.

    After SAML authentication, Keycloak redirects here with an authorization code.
    In a real application, you would exchange this code for tokens.
    """
    if not code:
        return {"error": "No authorization code received"}
    return {
        "message": "SAML authentication successful!",
        "code": code[:20] + "...",
        "next_step": "Exchange this code for an access token at the token endpoint",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
