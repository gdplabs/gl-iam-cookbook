"""GitHub OAuth connector implementation.

Implements the full GitHub OAuth 2.0 web application flow:
1. Generate authorization URL with CSRF state
2. Handle callback: exchange code for token, fetch GitHub username
3. Store integration via GL-IAM's ThirdPartyIntegrationProvider
4. Revoke token on integration removal

References:
    - BOSA: bosa_server_plugins/github/plugin.py (GithubApiPlugin)
    - GitHub OAuth docs: https://docs.github.com/en/apps/oauth-apps/building-oauth-apps
"""

import base64
import json
import logging
import os
import secrets
import time
import urllib.parse

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse

from connectors.base import BaseConnector
from gl_iam.core.protocols.third_party import ThirdPartyIntegrationProvider

logger = logging.getLogger(__name__)

# State cache TTL in seconds (matches GitHub's OAuth code lifetime)
STATE_CACHE_TTL = 600

# In-memory state cache: state_key -> (callback_url, expiry_timestamp)
# NOTE: Use Redis or another distributed cache in production for multi-process support.
_state_cache: dict[str, tuple[str, float]] = {}


def _cache_set(key: str, value: str, ttl: int = STATE_CACHE_TTL) -> None:
    """Store a value in the state cache with TTL."""
    _state_cache[key] = (value, time.time() + ttl)


def _cache_get(key: str) -> str | None:
    """Get a value from the state cache, returning None if expired or missing."""
    entry = _state_cache.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.time() > expiry:
        del _state_cache[key]
        return None
    return value


def _cache_delete(key: str) -> None:
    """Remove a value from the state cache."""
    _state_cache.pop(key, None)


class GitHubConnector(BaseConnector):
    """GitHub OAuth connector following the BOSA plugin pattern.

    Implements the GitHub OAuth 2.0 web application flow with CSRF state
    management and encrypted credential storage via GL-IAM.

    Environment variables required:
        GITHUB_CLIENT_ID: OAuth App client ID
        GITHUB_CLIENT_SECRET: OAuth App client secret
        APP_BASE_URL: Base URL for the callback (e.g., http://localhost:8000)
    """

    GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
    GITHUB_API_URL = "https://api.github.com"
    GITHUB_API_VERSION = "2022-11-28"
    TOKEN_LENGTH = 64
    CACHE_STATE_PREFIX = "github-state-"

    def __init__(self, provider: ThirdPartyIntegrationProvider) -> None:
        super().__init__(provider)
        self._client_id = os.getenv("GITHUB_CLIENT_ID", "")
        self._client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
        self._base_url = os.getenv("APP_BASE_URL", "http://localhost:8000")

    @property
    def name(self) -> str:
        return "github"

    @property
    def scopes(self) -> list[str]:
        return ["repo", "read:user", "read:org"]

    async def initialize_authorization(
        self, user_id: str, org_id: str, callback_url: str
    ) -> str:
        """Generate GitHub OAuth authorization URL with CSRF state.

        The state parameter encodes user_id, org_id, and a random token as
        base64 JSON. The random token is used as a cache key to store the
        callback_url for retrieval during the callback.
        """
        redirect_uri = f"{self._base_url}/connectors/github/callback"
        state = self._create_state(user_id, org_id, callback_url)

        params = urllib.parse.urlencode({
            "client_id": self._client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.scopes),
            "state": state,
        })
        return f"{self.GITHUB_AUTHORIZE_URL}?{params}"

    async def handle_callback(self, code: str, state: str) -> str:
        """Handle GitHub OAuth callback.

        1. Decode and validate the CSRF state
        2. Exchange the authorization code for an access token
        3. Fetch the GitHub username
        4. Store the integration via GL-IAM
        5. Return the frontend callback URL
        """
        # Decode and validate state
        state_data = self._decode_state(state)
        user_id = state_data["user_id"]
        org_id = state_data["org_id"]
        state_code = state_data["state_code"]
        callback_url = self._validate_state(user_id, org_id, state_code)

        # Exchange code for access token
        token_data = await self._exchange_code(code)
        access_token = token_data["access_token"]
        granted_scopes = token_data.get("scope", "").split(",")

        # Fetch GitHub username
        github_username = await self._fetch_github_username(access_token)

        # Store integration via GL-IAM (encrypted at rest)
        await self.provider.store_integration(
            user_id=user_id,
            connector=self.name,
            auth_string=access_token,
            organization_id=org_id,
            user_identifier=github_username,
            scopes=granted_scopes,
            metadata={"provider": "github"},
        )

        logger.info("Stored GitHub integration for user %s (%s)", user_id, github_username)
        return callback_url

    async def revoke_token(self, auth_string: str) -> None:
        """Revoke a GitHub access token via the GitHub API.

        Uses the DELETE /applications/{client_id}/grant endpoint to fully
        revoke the OAuth grant, not just the individual token.
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.delete(
                    f"{self.GITHUB_API_URL}/applications/{self._client_id}/grant",
                    auth=(self._client_id, self._client_secret),
                    json={"access_token": auth_string},
                    headers={"Accept": "application/vnd.github+json"},
                    timeout=10,
                )
                # 204 = success, 404 = already revoked (both are fine)
                if response.status_code not in (204, 404):
                    logger.warning(
                        "GitHub token revocation returned status %d", response.status_code
                    )
            except httpx.HTTPError as e:
                logger.warning("Failed to revoke GitHub token: %s", e)

    def register_routes(self, app: FastAPI, prefix: str) -> None:
        """Register the GitHub OAuth callback route.

        This route is public (no authentication) because GitHub redirects
        the user's browser here after authorization.
        """

        @app.get(f"{prefix}/callback")
        async def github_callback(request: Request):
            code = request.query_params.get("code")
            state = request.query_params.get("state")

            if not code or not state:
                return {"error": "Missing code or state parameter"}

            try:
                callback_url = await self.handle_callback(code, state)
                return RedirectResponse(url=callback_url)
            except Exception as e:
                logger.exception("GitHub OAuth callback failed")
                return {"error": str(e)}

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _create_state(self, user_id: str, org_id: str, callback_url: str) -> str:
        """Create a CSRF state token and cache the callback URL.

        The state is a base64-encoded JSON object containing user_id, org_id,
        and a random state_code. The state_code is used as a cache key to
        look up the callback_url during the callback.
        """
        state_code = secrets.token_urlsafe(self.TOKEN_LENGTH)
        cache_key = f"{self.CACHE_STATE_PREFIX}{user_id}:{org_id}:{state_code}"
        _cache_set(cache_key, callback_url)

        state_data = {
            "user_id": user_id,
            "org_id": org_id,
            "state_code": state_code,
        }
        return base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    def _decode_state(self, state: str) -> dict:
        """Decode a base64-encoded state parameter."""
        decoded = base64.urlsafe_b64decode(state).decode()
        return json.loads(decoded)

    def _validate_state(self, user_id: str, org_id: str, state_code: str) -> str:
        """Validate the state and return the cached callback URL.

        The state is consumed (deleted from cache) after validation to prevent
        replay attacks.

        Raises:
            ValueError: If the state is invalid or expired.
        """
        cache_key = f"{self.CACHE_STATE_PREFIX}{user_id}:{org_id}:{state_code}"
        callback_url = _cache_get(cache_key)
        if callback_url is None:
            raise ValueError("Invalid or expired OAuth state")
        _cache_delete(cache_key)
        return callback_url

    async def _exchange_code(self, code: str) -> dict:
        """Exchange an authorization code for an access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.GITHUB_TOKEN_URL,
                data={
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "code": code,
                    "redirect_uri": f"{self._base_url}/connectors/github/callback",
                },
                headers={"Accept": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                raise ValueError(f"GitHub OAuth error: {data['error_description']}")
            return data

    async def _fetch_github_username(self, access_token: str) -> str:
        """Fetch the authenticated GitHub user's login name."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.GITHUB_API_URL}/user",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {access_token}",
                    "X-GitHub-Api-Version": self.GITHUB_API_VERSION,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()["login"]
