"""
Server-side "Sign in with Google" through Stack Auth's OAuth REST API.

Stack Auth brokers the Google login: your backend sends the browser to Stack
Auth, Stack Auth sends it to Google, and Google returns it (via Stack Auth) to
your callback with a one-time authorization code. Your backend then swaps that
code for a Stack Auth access token, which GL-IAM validates like any other
Stack Auth token.

    Browser ──► /auth/google/login ──► Stack Auth /authorize/google ──► Google
       ▲                                                                 │
       └── /auth/google/callback?code=... ◄── Stack Auth /callback ◄──────┘

This module holds the OAuth plumbing only (PKCE, URL building, code exchange).
It knows nothing about FastAPI, so you can reuse it in Django or a CLI.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from gl_iam.core.exceptions import AuthenticationError, ProviderUnavailableError

logger = logging.getLogger(__name__)


def _random_urlsafe(num_bytes: int = 32) -> str:
    """Return a URL-safe random string with no padding (43 chars for 32 bytes)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(num_bytes)).rstrip(b"=").decode()


@dataclass(frozen=True)
class PKCEPair:
    """A PKCE code verifier and its S256 challenge (RFC 7636).

    The challenge goes to the authorize URL. The verifier stays on the server
    side of the flow and is sent only with the code exchange, so a stolen
    authorization code is useless without it.
    """

    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> PKCEPair:
        """Create a fresh verifier/challenge pair."""
        verifier = _random_urlsafe()
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        return cls(verifier=verifier, challenge=challenge)


@dataclass(frozen=True)
class PendingLogin:
    """What the callback needs to finish a login that /login started.

    It is stored in a short-lived HttpOnly cookie, which ties the callback to
    the same browser that started the login (CSRF protection via `state`).
    """

    state: str
    code_verifier: str

    @classmethod
    def start(cls) -> tuple[PendingLogin, PKCEPair]:
        """Begin a new login: random state plus a PKCE pair."""
        pkce = PKCEPair.generate()
        return cls(state=_random_urlsafe(), code_verifier=pkce.verifier), pkce

    def to_cookie(self) -> str:
        """Serialize for the cookie. Both parts are URL-safe base64, so '.' is a safe separator."""
        return f"{self.state}.{self.code_verifier}"

    @classmethod
    def from_cookie(cls, value: str | None) -> PendingLogin | None:
        """Parse the cookie value, or return None if it is missing or malformed."""
        if not value or value.count(".") != 1:
            return None
        state, verifier = value.split(".")
        return cls(state=state, code_verifier=verifier)

    def matches(self, returned_state: str | None) -> bool:
        """Constant-time check that the callback's state is the one we issued."""
        # compare_digest raises TypeError for non-ASCII str, so reject those first.
        return (
            bool(returned_state)
            and self.state.isascii()
            and returned_state.isascii()
            and secrets.compare_digest(self.state, returned_state)
        )


@dataclass(frozen=True)
class OAuthTokens:
    """Tokens Stack Auth returns after a successful code exchange."""

    access_token: str
    refresh_token: str | None
    is_new_user: bool


class StackAuthOAuthClient:
    """Minimal client for Stack Auth's OAuth authorize and token endpoints.

    Args:
        base_url: Stack Auth API URL, e.g. https://api.stack-auth.com or http://localhost:8102.
        project_id: Stack Auth project ID (used as the OAuth client_id).
        publishable_client_key: Publishable client key (used as the OAuth client_secret).
    """

    def __init__(self, base_url: str, project_id: str, publishable_client_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._project_id = project_id
        self._publishable_client_key = publishable_client_key
        self._http = httpx.AsyncClient(timeout=15)

    def authorization_url(self, provider: str, redirect_uri: str, state: str, code_challenge: str) -> str:
        """Build the URL that starts the OAuth flow for `provider` (e.g. "google")."""
        params = {
            "client_id": self._project_id,
            "client_secret": self._publishable_client_key,
            "redirect_uri": redirect_uri,
            "scope": "legacy",
            "state": state,
            "grant_type": "authorization_code",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "response_type": "code",
            "type": "authenticate",
        }
        return f"{self._base_url}/api/v1/auth/oauth/authorize/{provider}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> OAuthTokens:
        """Swap the authorization code for Stack Auth tokens.

        `redirect_uri` must be exactly the value used in `authorization_url`.

        Raises:
            AuthenticationError: Stack Auth rejected the code (expired, reused, wrong verifier).
            ProviderUnavailableError: Stack Auth could not be reached.
        """
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self._project_id,
            "client_secret": self._publishable_client_key,
        }
        try:
            response = await self._http.post(f"{self._base_url}/api/v1/auth/oauth/token", data=form)
        except httpx.RequestError as error:
            raise ProviderUnavailableError("The sign-in service is unavailable. Try again later.") from error

        if response.status_code != 200:
            # Log the status only. Never echo upstream error text to the client.
            logger.warning("Stack Auth code exchange failed (status_code=%s)", response.status_code)
            raise AuthenticationError("Google sign-in could not be completed. Start the sign-in again.")

        body = response.json()
        return OAuthTokens(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            is_new_user=bool(body.get("is_new_user", False)),
        )

    async def close(self) -> None:
        """Release HTTP connections."""
        await self._http.aclose()
