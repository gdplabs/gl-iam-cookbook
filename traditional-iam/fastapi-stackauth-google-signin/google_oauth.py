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

If the user has TOTP two-factor authentication enabled in Stack Auth, the code
exchange does not return tokens. It returns an MFA attempt code instead, and
the backend finishes the sign-in by sending that attempt code together with the
user's 6-digit TOTP code to Stack Auth's MFA sign-in endpoint.

This module holds the OAuth plumbing only (PKCE, URL building, code exchange,
MFA completion, and mapping Stack Auth errors to GL-IAM errors). It knows
nothing about FastAPI, so you can reuse it in Django or a CLI.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode

import httpx
from gl_iam.core.exceptions import (
    AuthenticationError,
    GLIAMError,
    MFAVerificationError,
    ProviderUnavailableError,
    RateLimitExceededError,
)

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


@dataclass(frozen=True)
class MFAChallenge:
    """Returned instead of tokens when the user must enter a TOTP code.

    `attempt_code` is a one-time code from Stack Auth (valid for about 5
    minutes) that proves the Google step already succeeded. Keep it server-side
    or in an HttpOnly cookie, and send it to `complete_mfa` with the TOTP code.
    """

    attempt_code: str


# Stack Auth "known error" codes this module reacts to.
_MFA_REQUIRED = "MULTI_FACTOR_AUTHENTICATION_REQUIRED"
_INVALID_TOTP = "INVALID_TOTP_CODE"


def _retry_after_seconds(response: httpx.Response) -> int | None:
    """Parse `Retry-After` (delta-seconds or HTTP-date) into whole seconds."""
    value = response.headers.get("retry-after", "").strip()
    # isascii() too: str.isdigit() accepts characters like "²" that int() rejects.
    if value.isascii() and value.isdigit():
        return int(value)
    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    # The asctime HTTP-date form ("Sun Nov  6 08:49:37 1994") has no zone. HTTP dates are always GMT.
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=UTC)
    return max(0, int((retry_at - datetime.now(UTC)).total_seconds()))


def _known_error(response: httpx.Response) -> tuple[str | None, dict]:
    """Return Stack Auth's error `code` and `details` from an error response."""
    try:
        body = response.json()
    except ValueError:
        return None, {}
    if not isinstance(body, dict):
        return None, {}
    details = body.get("details")
    return body.get("code"), details if isinstance(details, dict) else {}


def _upstream_error(response: httpx.Response, operation: str) -> GLIAMError:
    """Map a non-2xx Stack Auth response to the matching GL-IAM error.

    429 and 5xx are the sign-in service's problem, not the user's, so they map
    to 429 / 503 (with `Retry-After` when Stack Auth sent one) instead of 401.
    Log the status only. Never echo upstream error text to the client.
    """
    logger.warning("Stack Auth %s failed (status_code=%s)", operation, response.status_code)
    wait_seconds = _retry_after_seconds(response)
    if response.status_code == 429:
        return RateLimitExceededError(wait_seconds=wait_seconds)
    if response.status_code >= 500:
        details = {"wait_seconds": wait_seconds} if wait_seconds is not None else {}
        return ProviderUnavailableError("The sign-in service is unavailable. Try again later.", details=details)
    return AuthenticationError("Google sign-in could not be completed. Start the sign-in again.")


def _tokens_from(body: dict) -> OAuthTokens:
    """Build OAuthTokens from a Stack Auth token / MFA sign-in response body."""
    return OAuthTokens(
        access_token=body["access_token"],
        refresh_token=body.get("refresh_token"),
        is_new_user=bool(body.get("is_new_user", False)),
    )


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

    async def exchange_code(self, code: str, redirect_uri: str, code_verifier: str) -> OAuthTokens | MFAChallenge:
        """Swap the authorization code for Stack Auth tokens.

        `redirect_uri` must be exactly the value used in `authorization_url`.

        Returns:
            OAuthTokens on success, or MFAChallenge when the user has TOTP
            enabled and must finish with `complete_mfa`.

        Raises:
            AuthenticationError: Stack Auth rejected the code (expired, reused, wrong verifier).
            RateLimitExceededError: Stack Auth rate-limited the request (429).
            ProviderUnavailableError: Stack Auth could not be reached or failed (5xx).
        """
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "client_id": self._project_id,
            "client_secret": self._publishable_client_key,
        }
        response = await self._post("/api/v1/auth/oauth/token", data=form)

        if response.status_code != 200:
            error_code, details = _known_error(response)
            if error_code == _MFA_REQUIRED and isinstance(details.get("attempt_code"), str):
                return MFAChallenge(attempt_code=details["attempt_code"])
            raise _upstream_error(response, "code exchange")

        return _tokens_from(response.json())

    async def complete_mfa(self, attempt_code: str, totp_code: str) -> OAuthTokens:
        """Finish an MFA sign-in with the attempt code and the user's TOTP code.

        Raises:
            MFAVerificationError: The TOTP code is wrong. The same attempt code can be retried.
            AuthenticationError: The attempt code expired or was already used. Start the sign-in again.
            RateLimitExceededError: Stack Auth rate-limited the request (429).
            ProviderUnavailableError: Stack Auth could not be reached or failed (5xx).
        """
        response = await self._post(
            "/api/v1/auth/mfa/sign-in",
            json={"type": "totp", "totp": totp_code, "code": attempt_code},
            headers={
                "x-stack-access-type": "client",
                "x-stack-project-id": self._project_id,
                "x-stack-publishable-client-key": self._publishable_client_key,
            },
        )

        if response.status_code != 200:
            error_code, _ = _known_error(response)
            if error_code == _INVALID_TOTP:
                logger.info("Stack Auth rejected the TOTP code")
                raise MFAVerificationError()
            raise _upstream_error(response, "MFA sign-in")

        return _tokens_from(response.json())

    async def _post(self, path: str, **kwargs) -> httpx.Response:
        """POST to Stack Auth, turning network failures into ProviderUnavailableError."""
        try:
            return await self._http.post(f"{self._base_url}{path}", **kwargs)
        except httpx.RequestError as error:
            raise ProviderUnavailableError("The sign-in service is unavailable. Try again later.") from error

    async def close(self) -> None:
        """Release HTTP connections."""
        await self._http.aclose()
