"""
"Sign in with Google" for a FastAPI app, using GL-IAM with the Stack Auth provider.

Stack Auth handles the Google OAuth handshake and issues its own access token.
GL-IAM then validates that token, so every protected endpoint uses the same
`get_current_user` / `require_org_*` dependencies as the email/password
example (traditional-iam/fastapi-stackauth). That is the SIMI pattern: how the
user signed in does not change your endpoint code.

Flow:
    1. GET /auth/google/login     -> redirect to Stack Auth -> Google consent screen
    2. GET /auth/google/callback  -> exchange code, validate with GL-IAM, return token
       (users with TOTP enabled are sent to /auth/google/mfa to enter their code first)
    3. GET /me (Bearer token)     -> normal GL-IAM protected endpoint
"""

import os
from contextlib import asynccontextmanager
from dataclasses import dataclass

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from gl_iam import IAMGateway, User
from gl_iam.core.error_carrier import raise_for_error
from gl_iam.core.exceptions import AuthenticationError
from gl_iam.fastapi import (
    add_exception_handlers,
    get_current_user,
    get_iam_gateway,
    require_org_admin,
    require_org_member,
    set_iam_gateway,
)
from gl_iam.providers.stackauth import StackAuthConfig, StackAuthProvider
from pydantic import BaseModel, Field

from google_oauth import MFAChallenge, OAuthTokens, PendingLogin, StackAuthOAuthClient

load_dotenv()

# Short-lived cookie that carries `state` + PKCE verifier from /login to /callback.
PENDING_LOGIN_COOKIE = "gliam_google_login"
PENDING_LOGIN_MAX_AGE_SECONDS = 600

# Short-lived cookie that carries Stack Auth's MFA attempt code from /callback to /mfa.
# Stack Auth expires the attempt code after 5 minutes, so the cookie does too.
MFA_ATTEMPT_COOKIE = "gliam_google_mfa"
MFA_ATTEMPT_MAX_AGE_SECONDS = 300
AUTH_COOKIE_PATH = "/auth/google"


@dataclass(frozen=True)
class Settings:
    """Environment configuration, read once at startup."""

    stackauth_base_url: str
    project_id: str
    publishable_client_key: str
    secret_server_key: str
    app_base_url: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            stackauth_base_url=os.getenv("STACKAUTH_BASE_URL", "http://localhost:8102"),
            project_id=os.environ["STACKAUTH_PROJECT_ID"],
            publishable_client_key=os.environ["STACKAUTH_PUBLISHABLE_CLIENT_KEY"],
            secret_server_key=os.environ["STACKAUTH_SECRET_SERVER_KEY"],
            app_base_url=os.getenv("APP_BASE_URL", "http://localhost:8000").rstrip("/"),
        )

    @property
    def google_redirect_uri(self) -> str:
        """Where Stack Auth sends the browser back after Google. Must match on code exchange."""
        return f"{self.app_base_url}/auth/google/callback"

    @property
    def secure_cookies(self) -> bool:
        """Send cookies over HTTPS only when the app itself is served over HTTPS."""
        return self.app_base_url.startswith("https://")


settings = Settings.from_env()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create the GL-IAM gateway (token validation) and the OAuth client (Google login)."""
    provider = StackAuthProvider(
        StackAuthConfig(
            error_policy="typed",
            base_url=settings.stackauth_base_url,
            project_id=settings.project_id,
            publishable_client_key=settings.publishable_client_key,
            secret_server_key=settings.secret_server_key,
        )
    )
    set_iam_gateway(IAMGateway.from_fullstack_provider(provider), default_organization_id=settings.project_id)

    app.state.oauth = StackAuthOAuthClient(
        base_url=settings.stackauth_base_url,
        project_id=settings.project_id,
        publishable_client_key=settings.publishable_client_key,
    )

    if await provider.health_check():
        print(f"Connected to Stack Auth at {settings.stackauth_base_url}")
    print(f"Open {settings.app_base_url}/ and click 'Sign in with Google'")

    yield

    await app.state.oauth.close()
    await provider.close()


app = FastAPI(title="GL-IAM Stack Auth - Sign in with Google", lifespan=lifespan)

# Map GL-IAM errors to 401/403/503 with safe, canonical error bodies.
add_exception_handlers(app, error_policy="v1.2")


def get_oauth_client(request: Request) -> StackAuthOAuthClient:
    """FastAPI dependency: the OAuth client created in lifespan."""
    return request.app.state.oauth


# =============================================================================
# Response models
# =============================================================================


class UserResponse(BaseModel):
    """User profile as GL-IAM sees it, plus the linked sign-in methods."""

    id: str
    email: str | None
    display_name: str | None
    avatar_url: str | None
    roles: list[str]
    oauth_providers: list[str]


class MFACodeRequest(BaseModel):
    """The 6-digit code from the user's authenticator app."""

    code: str = Field(pattern=r"^\d{6}$", examples=["123456"])


class GoogleSignInResponse(BaseModel):
    """Returned by the callback after a successful Google sign-in."""

    access_token: str
    refresh_token: str | None
    token_type: str = "bearer"
    is_new_user: bool
    user: UserResponse


def to_user_response(user: User) -> UserResponse:
    """Map a GL-IAM User to the API response, including OAuth providers from Stack Auth."""
    linked = user.metadata.get("oauth_providers") or []
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        roles=user.roles,
        oauth_providers=[p.get("id", "") for p in linked if isinstance(p, dict)],
    )


# =============================================================================
# Public endpoints
# =============================================================================


@app.get("/health")
async def health():
    """Public health check endpoint."""
    return {"status": "healthy", "provider": "stackauth", "sign_in": ["google"]}


@app.get("/", response_class=HTMLResponse)
async def home():
    """A one-button page so you can try the flow in a browser."""
    return """
    <!doctype html>
    <html><head><meta charset="utf-8"><title>Sign in with Google</title></head>
    <body style="font-family: system-ui, sans-serif; max-width: 32rem; margin: 4rem auto;">
      <h1>GL-IAM + Stack Auth</h1>
      <p>Sign in with your Google account. Stack Auth handles Google; GL-IAM validates the result.</p>
      <p><a href="/auth/google/login"
            style="display:inline-block;padding:.6rem 1.2rem;border:1px solid #888;border-radius:6px;
                   text-decoration:none;color:inherit;">Sign in with Google</a></p>
    </body></html>
    """


# =============================================================================
# Google sign-in (OAuth 2.0 authorization code + PKCE, brokered by Stack Auth)
# =============================================================================


@app.get("/auth/google/login")
async def google_login(oauth: StackAuthOAuthClient = Depends(get_oauth_client)):
    """Step 1: send the browser to Stack Auth, which forwards it to Google."""
    pending, pkce = PendingLogin.start()
    url = oauth.authorization_url("google", settings.google_redirect_uri, pending.state, pkce.challenge)

    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        PENDING_LOGIN_COOKIE,
        pending.to_cookie(),
        max_age=PENDING_LOGIN_MAX_AGE_SECONDS,
        path=AUTH_COOKIE_PATH,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",  # "lax" still sends the cookie on the top-level redirect back from Stack Auth
    )
    return response


@app.get("/auth/google/callback", response_model=GoogleSignInResponse)
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    pending_cookie: str | None = Cookie(default=None, alias=PENDING_LOGIN_COOKIE),
    oauth: StackAuthOAuthClient = Depends(get_oauth_client),
    gateway: IAMGateway = Depends(get_iam_gateway),
):
    """Step 2: verify state, exchange the code, and validate the token with GL-IAM."""
    pending = PendingLogin.from_cookie(pending_cookie)
    if error or not code:
        raise AuthenticationError("Google sign-in was cancelled or failed. Start the sign-in again.")
    if pending is None or not pending.matches(state):
        raise AuthenticationError("This sign-in link is invalid or has expired. Start the sign-in again.")

    outcome = await oauth.exchange_code(code, settings.google_redirect_uri, pending.code_verifier)

    if isinstance(outcome, MFAChallenge):
        # The user has TOTP enabled: park the attempt code and ask for their 6-digit code.
        response = RedirectResponse("/auth/google/mfa", status_code=303)
        response.set_cookie(
            MFA_ATTEMPT_COOKIE,
            outcome.attempt_code,
            max_age=MFA_ATTEMPT_MAX_AGE_SECONDS,
            path=AUTH_COOKIE_PATH,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="lax",  # never sent on cross-site POSTs, so the MFA form cannot be driven from another site
        )
        response.delete_cookie(PENDING_LOGIN_COOKIE, path=AUTH_COOKIE_PATH)  # one-time use
        return response

    return await finish_sign_in(outcome, gateway)


@app.get("/auth/google/mfa", response_class=HTMLResponse)
async def google_mfa_form():
    """Step 2b (TOTP users only): a minimal page that asks for the authenticator code."""
    return """
    <!doctype html>
    <html><head><meta charset="utf-8"><title>Two-factor verification</title></head>
    <body style="font-family: system-ui, sans-serif; max-width: 32rem; margin: 4rem auto;">
      <h1>Two-factor verification</h1>
      <p>Enter the 6-digit code from your authenticator app.</p>
      <form id="mfa">
        <input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="\\d{6}" maxlength="6" required>
        <button type="submit">Verify</button>
      </form>
      <pre id="result" style="white-space: pre-wrap;"></pre>
      <script>
        document.getElementById("mfa").addEventListener("submit", async (event) => {
          event.preventDefault();
          const response = await fetch("/auth/google/mfa", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({code: event.target.code.value}),
          });
          document.getElementById("result").textContent = JSON.stringify(await response.json(), null, 2);
        });
      </script>
    </body></html>
    """


@app.post("/auth/google/mfa", response_model=GoogleSignInResponse)
async def google_mfa_verify(
    body: MFACodeRequest,
    attempt_code: str | None = Cookie(default=None, alias=MFA_ATTEMPT_COOKIE),
    oauth: StackAuthOAuthClient = Depends(get_oauth_client),
    gateway: IAMGateway = Depends(get_iam_gateway),
):
    """Step 2c: send the attempt code + TOTP code to Stack Auth, then validate with GL-IAM.

    A wrong code returns 401 (`mfa_verification_failed`) and keeps the cookie,
    so the user can try again until the attempt code expires.
    """
    if not attempt_code:
        raise AuthenticationError("This sign-in has expired. Start the sign-in again.")

    tokens = await oauth.complete_mfa(attempt_code, body.code)
    return await finish_sign_in(tokens, gateway)


async def finish_sign_in(tokens: OAuthTokens, gateway: IAMGateway) -> JSONResponse:
    """Validate the Stack Auth token with GL-IAM and return it with the user profile."""
    # Same validation path the Bearer-token dependencies use.
    result = await gateway.validate_session(tokens.access_token, organization_id=settings.project_id)
    if result.is_err:
        raise_for_error(result.error)

    # NOTE: returned as JSON so you can copy the token into curl. In a real web
    # app, set the tokens as HttpOnly cookies and redirect to your frontend.
    response = GoogleSignInResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        is_new_user=tokens.is_new_user,
        user=to_user_response(result.unwrap()),
    )
    json_response = JSONResponse(response.model_dump())
    # Both cookies are one-time use.
    json_response.delete_cookie(PENDING_LOGIN_COOKIE, path=AUTH_COOKIE_PATH)
    json_response.delete_cookie(MFA_ATTEMPT_COOKIE, path=AUTH_COOKIE_PATH)
    return json_response


# =============================================================================
# Protected endpoints - identical to the email/password Stack Auth example
# =============================================================================


@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Current user's profile. Works for Google and password users alike."""
    return to_user_response(user)


@app.get("/member-area")
async def member_area(user: User = Depends(get_current_user), _: None = Depends(require_org_member())):
    """Accessible by ORG_MEMBER, ORG_ADMIN, or PLATFORM_ADMIN."""
    return {"message": f"Welcome {user.email}!", "access_level": "member"}


@app.get("/admin-area")
async def admin_area(user: User = Depends(get_current_user), _: None = Depends(require_org_admin())):
    """Accessible by ORG_ADMIN or PLATFORM_ADMIN only."""
    return {"message": f"Welcome Admin {user.email}!", "access_level": "admin"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
