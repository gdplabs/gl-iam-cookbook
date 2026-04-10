"""
LDAP Authentication via Keycloak with GL-IAM.

This example demonstrates how to authenticate LDAP/Active Directory users
through Keycloak's User Federation feature. The GL-IAM code is identical
to a standard Keycloak setup — Keycloak handles LDAP natively.

Architecture:
    OpenLDAP ←→ Keycloak (User Federation) ←→ FastAPI + GL-IAM
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

    Keycloak handles LDAP federation transparently — no LDAP-specific
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
        print("LDAP users can authenticate through Keycloak's User Federation")

    yield


app = FastAPI(title="GL-IAM LDAP via Keycloak", lifespan=lifespan)


class UserResponse(BaseModel):
    """Response model for user data with roles."""
    id: str
    email: str
    display_name: str | None
    roles: list[str]


@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "provider": "keycloak", "federation": "ldap"}


@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """
    Get current user profile.

    Works for both LDAP-federated users and local Keycloak users.
    GL-IAM doesn't distinguish between them — Keycloak issues the
    same OIDC token format regardless of the user's origin.
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
    LDAP users get roles via Keycloak's group-to-role mapping.
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
