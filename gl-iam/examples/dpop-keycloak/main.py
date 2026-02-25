"""
DPoP Keycloak Demo - FastAPI Resource Server

This example demonstrates a FastAPI server that validates DPoP proofs
using GL-IAM with Keycloak as the identity provider.

The key difference from regular Bearer token validation:
- Client must prove possession of a private key
- Access token is bound to the client's public key (cnf.jkt claim)
- Each request includes a DPoP proof JWT signed with the client's key
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from pydantic import BaseModel

from gl_iam import DPoPConfig, IAMGateway, User
from gl_iam.fastapi import (
    get_current_user,
    get_current_user_with_dpop,
    set_iam_gateway,
)
from gl_iam.providers.keycloak import (
    KeycloakConfig,
    KeycloakProvider,
)

from gl_iam.providers.keycloak.dpop import KeycloakDPoPProvider

load_dotenv()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize GL-IAM gateway with Keycloak and DPoP support."""
    keycloak_config = KeycloakConfig(
        server_url=_require_env("KEYCLOAK_SERVER_URL"),
        realm=_require_env("KEYCLOAK_REALM"),
        client_id=_require_env("KEYCLOAK_CLIENT_ID"),
        client_secret=_require_env("KEYCLOAK_CLIENT_SECRET"),
    )

    keycloak_provider = KeycloakProvider(config=keycloak_config)

    dpop_config = DPoPConfig(enabled=True, required=False, nonce_enabled=False)
    dpop_provider = KeycloakDPoPProvider(
        keycloak_config=keycloak_config, dpop_config=dpop_config
    )
    gateway = IAMGateway.from_fullstack_provider(
        provider=keycloak_provider, dpop_provider=dpop_provider
    )
    set_iam_gateway(gateway, default_organization_id=os.getenv("KEYCLOAK_REALM"))

    is_healthy = await keycloak_provider.health_check()
    if is_healthy:
        print(f"Connected to Keycloak at {os.getenv('KEYCLOAK_SERVER_URL')}")
        print("DPoP is enabled - tokens will be bound to client keys")
    app.state.iam_gateway = gateway
    app.state.default_organization_id = os.getenv("KEYCLOAK_REALM")
    yield


app = FastAPI(title="DPoP Keycloak Demo", lifespan=lifespan)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str]


@app.get("/health")
async def health():
    """Public health check - no authentication required."""
    return {"status": "healthy", "dpop": "enabled"}


@app.get("/api/public")
async def public():
    """Public endpoint - no authentication required."""
    return {"message": "This is a public endpoint"}


@app.get("/api/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """
    Standard Bearer token endpoint.

    This works with regular access tokens (not DPoP-bound).
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
    )


@app.get("/api/protected", response_model=UserResponse)
async def get_protected(user: User = Depends(get_current_user_with_dpop)):
    """
    DPoP-protected endpoint.

    This endpoint requires:
    - Authorization: DPoP <access_token>
    - DPoP: <dpop_proof_jwt>

    The proof must be signed with the same private key that was used
    when obtaining the access token from Keycloak.
    """
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
