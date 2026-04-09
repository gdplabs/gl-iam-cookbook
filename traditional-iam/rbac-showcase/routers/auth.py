"""
Authentication router for RBAC Showcase.

Provides token retrieval endpoints for testing purposes.
"""

import httpx
from fastapi import APIRouter, HTTPException

from config import ProviderType, settings
from schemas import TokenRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/token", response_model=TokenResponse)
async def get_token(request: TokenRequest) -> TokenResponse:
    """
    Get an authentication token.

    For Keycloak: Uses Resource Owner Password Grant (for testing only).
    For StackAuth: Returns instructions as Stack Auth uses different auth flow.

    **Warning**: Password grant is for testing only. Use Authorization Code
    Flow with PKCE in production.
    """
    if settings.provider_type == ProviderType.KEYCLOAK:
        return await _get_keycloak_token(request.username, request.password)
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Stack Auth uses browser-based authentication",
                "instructions": [
                    "1. Use Stack Auth SDK in your frontend",
                    "2. Redirect user to Stack Auth login page",
                    "3. Extract token from session after login",
                    "4. Include token in Authorization header as 'Bearer <token>'",
                ],
            },
        )


async def _get_keycloak_token(username: str, password: str) -> TokenResponse:
    """Get token from Keycloak using Resource Owner Password Grant."""
    token_url = (
        f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
        f"/protocol/openid-connect/token"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            token_url,
            data={
                "grant_type": "password",
                "client_id": settings.keycloak_client_id,
                "client_secret": settings.keycloak_client_secret,
                "username": username,
                "password": password,
            },
        )

        if response.status_code != 200:
            error_detail = response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "Authentication failed",
                    "keycloak_error": error_detail,
                },
            )

        data = response.json()
        return TokenResponse(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
        )


@router.get("/provider")
async def get_provider_info():
    """Get information about the current authentication provider."""
    if settings.provider_type == ProviderType.KEYCLOAK:
        return {
            "provider": "keycloak",
            "server_url": settings.keycloak_server_url,
            "realm": settings.keycloak_realm,
            "client_id": settings.keycloak_client_id,
            "token_endpoint": (
                f"{settings.keycloak_server_url}/realms/{settings.keycloak_realm}"
                f"/protocol/openid-connect/token"
            ),
            "auth_method": "Resource Owner Password Grant (testing) or Authorization Code Flow (production)",
        }
    else:
        return {
            "provider": "stackauth",
            "base_url": settings.stackauth_base_url,
            "project_id": settings.stackauth_project_id,
            "auth_method": "Browser-based OAuth flow via Stack Auth SDK",
        }
