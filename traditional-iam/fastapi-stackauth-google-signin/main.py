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
from pydantic import BaseModel

from google_oauth import PendingLogin, StackAuthOAuthClient

load_dotenv()

# Short-lived cookie that carries `state` + PKCE verifier from /login to /callback.
PENDING_LOGIN_COOKIE = "gliam_google_login"
PENDING_LOGIN_MAX_AGE_SECONDS = 600


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
        path="/auth/google",
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

    tokens = await oauth.exchange_code(code, settings.google_redirect_uri, pending.code_verifier)

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
    json_response.delete_cookie(PENDING_LOGIN_COOKIE, path="/auth/google")  # one-time use
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
