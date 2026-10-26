"""
Authentication router for RBAC Showcase.

Provides token retrieval endpoints for testing purposes.
"""

import math
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from fastapi import APIRouter, HTTPException
from gl_iam.core.exceptions import (
    ConfigurationError,
    InvalidCredentialsError,
    ProviderError,
    ProviderUnavailableError,
    RateLimitExceededError,
)

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

    try:
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
    except httpx.RequestError as error:
        raise ProviderUnavailableError(cause=error) from None

    # This demo calls the OAuth endpoint directly, outside the SDK provider.
    # Classify by status and OAuth code; never return the upstream body.
    if response.status_code == 429:
        wait = response.headers.get("Retry-After", "")
        try:
            wait_seconds = float(wait)
        except ValueError:
            try:
                wait_seconds = max(0, (parsedate_to_datetime(wait) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                wait_seconds = None
        if wait_seconds is not None and (not math.isfinite(wait_seconds) or wait_seconds < 0):
            wait_seconds = None
        raise RateLimitExceededError(wait_seconds=wait_seconds)
    if response.status_code == 408 or response.status_code >= 500:
        raise ProviderUnavailableError()
    if response.status_code in (401, 403):
        raise ConfigurationError()
    try:
        data = response.json()
    except ValueError as error:
        raise ProviderError(cause=error) from None
    if not isinstance(data, dict):
        raise ProviderError()
    if response.status_code == 400 and data.get("error") == "invalid_grant":
        raise InvalidCredentialsError()
    if data.get("error") in ("invalid_client", "unauthorized_client"):
        raise ConfigurationError()
    if response.status_code != 200:
        raise ProviderError()
    try:
        return TokenResponse(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_in=data.get("expires_in"),
        )
    except (KeyError, ValueError) as error:
        raise ProviderError(cause=error) from None


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
