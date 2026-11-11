# Sign in with Google — FastAPI + Stack Auth

> **Error handling v1.2:** This example requires `gl-iam>=0.3.25,<0.4.0`
> from PyPI and Python 3.12 or 3.13. SDK failures use canonical
> `error_code`/`message` fields and recovery guidance. Read the
> [migration and installation notes](../../ERROR_HANDLING.md) before running it.

## Overview

This example adds **"Sign in with Google"** to a FastAPI backend using GL-IAM with the
[Stack Auth](https://stack-auth.com/) provider, without a frontend SDK.

- **Stack Auth** brokers the Google OAuth handshake and issues a Stack Auth access token.
- **GL-IAM** validates that token through `StackAuthProvider`. Every protected endpoint uses the same
  `get_current_user` / `require_org_member()` / `require_org_admin()` dependencies as the
  password-based [fastapi-stackauth](../fastapi-stackauth/) example.

That is the SIMI pattern applied to sign-in methods: **how** the user signed in (Google, password,
magic link) doesn't change your endpoint code.

<img alt="Sign in with Google sequence between Browser, Your app, GL IAM, Stack Auth, and Google: the browser calls GET /auth/google/login, the app returns a 302 to Stack Auth with state and a PKCE challenge, the browser calls Stack Auth's /authorize/google, Stack Auth redirects to Google consent and receives the sign-in result, Stack Auth returns a 302 to /auth/google/callback with a code, the app exchanges the code and PKCE verifier with Stack Auth for an access token, calls gateway.validate_session(token) on GL IAM to get the user with roles, and returns tokens and the user to the browser." src="docs/google-signin-overview.png">

Your app never talks to Google directly. It only sees a Stack Auth code, exchanges it for a Stack Auth
token, and asks GL-IAM who the token belongs to. See [The full flow](#the-full-flow) for how `state` and PKCE protect each step.

## Prerequisites

Please refer to prerequisites [here](../../README.md).

Additionally, you need:
- A Stack Auth project (cloud or self-hosted). See [fastapi-stackauth](../fastapi-stackauth/README.md#getting-started) for self-hosting steps.
- Stack Auth API keys: project ID, publishable client key, secret server key
- A Google account to sign in with
- *(Production only)* A Google Cloud OAuth client. In development, Stack Auth's shared Google keys work.

## Quick Start

1. **Open the directory**

   ```bash
   git clone https://github.com/gdplabs/gl-iam-cookbook.git
   cd gl-iam-cookbook/traditional-iam/fastapi-stackauth-google-signin/
   ```

2. **Install dependencies**

   ```bash
   ./setup.sh        # Linux/macOS
   setup.bat         # Windows
   ```

   Or manually: `uv sync && cp .env.example .env`

3. **Enable Google in Stack Auth**

   In the Stack Auth dashboard for your project:

   1. Open **Auth Methods** and turn on **Google**.
   2. **Development:** keep the default **shared keys**. Nothing else is needed. (The consent
      screen shows Stack Auth's branding.)
   3. **Production:** choose **custom keys** and paste your Google **Client ID** and **Client Secret**.
      In [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials),
      create an *OAuth client ID* (type *Web application*). Then add this **Authorized redirect URI**,
      which points at Stack Auth, not at this app:

      ```
      https://api.stack-auth.com/api/v1/auth/oauth/callback/google      # Stack Auth Cloud
      http://localhost:8102/api/v1/auth/oauth/callback/google           # self-hosted dev
      ```

4. **Trust this app's domain in Stack Auth**

   Stack Auth only redirects back to trusted domains. Open **Domains** in the dashboard and either:
   - enable **Allow all localhost callbacks for development**, or
   - add `http://localhost:8000` as a trusted domain (use your real HTTPS domain in production).

5. **Configure `.env`**

   ```bash
   STACKAUTH_BASE_URL=https://api.stack-auth.com       # or http://localhost:8102
   STACKAUTH_PROJECT_ID=your-project-id
   STACKAUTH_PUBLISHABLE_CLIENT_KEY=pck_your_publishable_key
   STACKAUTH_SECRET_SERVER_KEY=ssk_your_secret_key
   APP_BASE_URL=http://localhost:8000                  # public URL of this app
   ```

   The callback URL is derived as `APP_BASE_URL/auth/google/callback`.

6. **Run the server**

   ```bash
   uv run main.py
   ```

7. **Sign in**

   Open <http://localhost:8000/> in a browser and click **Sign in with Google**. After the Google
   consent screen, the callback returns JSON like this:

   ```json
   {
     "access_token": "eyJhbGciOi...",
     "refresh_token": "...",
     "token_type": "bearer",
     "is_new_user": true,
     "user": {
       "id": "3f1c...",
       "email": "you@gmail.com",
       "display_name": "Your Name",
       "avatar_url": "https://lh3.googleusercontent.com/...",
       "roles": [],
       "oauth_providers": ["google"]
     }
   }
   ```

   On first sign-in, Stack Auth creates the user automatically (`is_new_user: true`).

   If the account has **TOTP two-factor authentication** enabled in Stack Auth, the callback
   redirects to `/auth/google/mfa` instead. Enter the 6-digit code from your authenticator app and
   the page shows the same JSON.

## Testing the API

Copy `access_token` from the callback response:

```bash
export TOKEN="eyJhbGciOi..."

# Health check (public)
curl http://localhost:8000/health

# Start the Google flow (shows the redirect to Stack Auth; finish it in a browser)
curl -i http://localhost:8000/auth/google/login

# Current user (authenticated) - same endpoint as the password example
curl http://localhost:8000/me -H "Authorization: Bearer $TOKEN"

# Member area (requires a team role, see below)
curl http://localhost:8000/member-area -H "Authorization: Bearer $TOKEN"

# Admin area (requires the team admin role)
curl http://localhost:8000/admin-area -H "Authorization: Bearer $TOKEN"
```

Expected results for a new Google user:

| Endpoint | Result |
|---|---|
| `/me` | `200` with profile and `"oauth_providers": ["google"]` |
| `/member-area` | `403` until the user is in a team with a member role |
| `/admin-area` | `403` until the user has the team admin role |
| any endpoint without a token | `401` |

To grant roles, follow
[Team Selection Required for Role Mapping](../fastapi-stackauth/README.md#important-team-selection-required-for-role-mapping):
add the Google user to a team, assign `team_member`/`team_admin` (`$member`/`$admin` on self-hosted),
and make that team the user's selected team. Then sign in again to get a fresh token.

Error cases (try them):

```bash
# Tampered/expired state, or no login cookie -> 401
curl -i "http://localhost:8000/auth/google/callback?code=fake&state=fake"

# User cancelled on the Google consent screen -> 401
curl -i "http://localhost:8000/auth/google/callback?error=access_denied"

# MFA step without the attempt cookie set by the callback -> 401
curl -i -X POST http://localhost:8000/auth/google/mfa \
  -H "Content-Type: application/json" -d '{"code": "123456"}'

# MFA code that is not 6 digits -> 422
curl -i -X POST http://localhost:8000/auth/google/mfa \
  -H "Content-Type: application/json" -d '{"code": "abc"}'
```

Status codes from the sign-in routes:

| Situation | Status | `error_code` |
|---|---|---|
| Bad/expired `state`, cancelled consent, rejected or reused code | `401` | `authentication_failed` |
| Wrong TOTP code (you can retry with a new code) | `401` | `mfa_verification_failed` |
| Stack Auth rate-limited the request | `429` + `Retry-After` | `rate_limited` |
| Stack Auth unreachable or returned 5xx | `503` (+ `Retry-After` if Stack Auth sent one) | `provider_unavailable` |

## Understanding the Code

The example has two files with separate jobs:

| File | Responsibility |
|---|---|
| [google_oauth.py](google_oauth.py) | OAuth plumbing: PKCE, `state`, authorize URL, code exchange, MFA completion, Stack Auth → GL-IAM error mapping. No FastAPI imports, so it can be reused in Django or a CLI. |
| [main.py](main.py) | FastAPI wiring: GL-IAM gateway, the login, callback and MFA routes, protected endpoints. |

### The full flow

The flow (see the [diagram above](#overview)) is OAuth 2.0 Authorization Code with **PKCE**:

- **`state` cookie:** the callback is accepted only if `state` matches the short-lived HttpOnly
  cookie set at login, which ties it to the browser that started it (CSRF protection).
- **PKCE verifier:** only the challenge leaves the server when the browser is sent to
  `/authorize/google`. A stolen code is useless without the verifier sent to `/auth/oauth/token`.
- **`validate_session`:** the callback checks the new token on the same path as `get_current_user`,
  so protected endpoints don't care how the user signed in.

### 1. Starting the login

```python
@app.get("/auth/google/login")
async def google_login(oauth: StackAuthOAuthClient = Depends(get_oauth_client)):
    pending, pkce = PendingLogin.start()
    url = oauth.authorization_url("google", settings.google_redirect_uri, pending.state, pkce.challenge)
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(PENDING_LOGIN_COOKIE, pending.to_cookie(), httponly=True, samesite="lax", ...)
```

- `PendingLogin.start()` creates a random `state` and a PKCE verifier/challenge pair.
- The **challenge** goes to Stack Auth in the URL. The **verifier** stays in an HttpOnly cookie
  scoped to `/auth/google` and is sent only during the code exchange.
- `samesite="lax"` still sends the cookie on the top-level redirect back from Stack Auth.
- Change `"google"` to `"github"`, `"microsoft"`, and so on to add more providers. The rest of the flow is identical.

### 2. Handling the callback

```python
pending = PendingLogin.from_cookie(pending_cookie)
if pending is None or not pending.matches(state):
    raise AuthenticationError(...)                      # → 401 via add_exception_handlers

outcome = await oauth.exchange_code(code, settings.google_redirect_uri, pending.code_verifier)
if isinstance(outcome, MFAChallenge):
    ...                                                 # → step 2b, see below
return await finish_sign_in(outcome, gateway)           # validate_session + JSON response
```

- `state` is compared in constant time against the cookie, which proves the callback belongs to this
  browser's login. Non-ASCII `state` values are rejected as a mismatch instead of crashing the comparison.
- `exchange_code` POSTs to Stack Auth's `/api/v1/auth/oauth/token` with the code and PKCE verifier.
  `redirect_uri` must be identical to the one used in step 1.
- The token is then validated through the **GL-IAM gateway**, the same path `get_current_user`
  uses. The response therefore carries the canonical GL-IAM `User`: roles, permissions, and
  `metadata["oauth_providers"]`.
- Errors are GL-IAM exceptions. `_upstream_error` in `google_oauth.py` maps Stack Auth's `429` to
  `RateLimitExceededError` (keeping `Retry-After`), `5xx` to `ProviderUnavailableError`, and anything else
  to `AuthenticationError`. `add_exception_handlers(app, error_policy="v1.2")` turns them into
  429/503/401 with safe bodies. Upstream error text is logged by status code only and never returned.

### 2b. Two-factor (TOTP) users

When the Google account's Stack Auth user has TOTP enabled, the code exchange doesn't return tokens.
Stack Auth answers `400 MULTI_FACTOR_AUTHENTICATION_REQUIRED` with a one-time `attempt_code`
(valid for 5 minutes). `exchange_code` returns that as an `MFAChallenge`, and the app finishes the
sign-in in two more steps:

```python
# Callback: park the attempt code in an HttpOnly cookie and ask for the TOTP code
response = RedirectResponse("/auth/google/mfa", status_code=303)
response.set_cookie(MFA_ATTEMPT_COOKIE, outcome.attempt_code, max_age=300, httponly=True, samesite="lax", ...)

# POST /auth/google/mfa {"code": "123456"}
tokens = await oauth.complete_mfa(attempt_code, body.code)
return await finish_sign_in(tokens, gateway)
```

- `complete_mfa` POSTs `{"type": "totp", "totp": ..., "code": attempt_code}` to Stack Auth's
  `/api/v1/auth/mfa/sign-in` and gets the same tokens a non-MFA sign-in returns.
- A wrong code raises `MFAVerificationError` (401). The cookie is kept, so the user can try again
  until the attempt code expires.
- The attempt code never reaches JavaScript or the URL. `SameSite=lax` keeps it off cross-site
  POSTs, so another site can't submit codes for the user.

### 3. Protected endpoints are unchanged

```python
@app.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return to_user_response(user)
```

This is the same code as the password example. GL-IAM doesn't care that the token came from Google.

### Stack Auth OAuth endpoints used

| Step | Endpoint | Key params |
|---|---|---|
| Authorize | `GET /api/v1/auth/oauth/authorize/google` | `client_id`=project ID, `client_secret`=publishable key, `redirect_uri`, `state`, `code_challenge`, `code_challenge_method=S256`, `grant_type=authorization_code`, `response_type=code`, `scope=legacy`, `type=authenticate` |
| Exchange | `POST /api/v1/auth/oauth/token` (form) | `grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier`, `client_id`, `client_secret` |
| MFA (TOTP users) | `POST /api/v1/auth/mfa/sign-in` (JSON, client headers) | `type=totp`, `totp`, `code`=attempt code; headers `x-stack-access-type: client`, `x-stack-project-id`, `x-stack-publishable-client-key` |

### Production notes

- **Don't return tokens as JSON to a browser.** Set them as `HttpOnly; Secure; SameSite` cookies and
  redirect to your frontend, or hand them to your SPA through a backend-for-frontend session.
- Use **custom Google keys** (step 3). Shared keys are for development only and don't allow custom scopes.
- Serve over **HTTPS**. Cookies get `Secure` automatically when `APP_BASE_URL` starts with `https://`.
- Stack Auth access tokens are short-lived, and `StackAuthProvider.refresh_session` is a no-op. Refresh
  with the `refresh_token` through Stack Auth (`POST /api/v1/auth/oauth/token` with
  `grant_type=refresh_token`), or let the user sign in again.

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| Stack Auth error page "redirect URL not whitelisted" | Step 4: trust `http://localhost:8000` or allow localhost callbacks |
| Google `redirect_uri_mismatch` | Custom keys: the Google redirect URI must be Stack Auth's callback, not this app's |
| Callback returns `401` immediately | The login cookie is missing or expired (10 min), or you opened the callback in a different browser |
| MFA page says the sign-in expired | The attempt code lasts 5 minutes. Start again from `/auth/google/login` |
| `/member-area` returns `403` | The Google user has no selected team or role yet (see Testing the API) |

## Next Steps

- [fastapi-stackauth](../fastapi-stackauth/): password sign-in with the same provider and endpoints
- [django-stackauth](../django-stackauth/): Stack Auth with Django
- [rbac-showcase](../rbac-showcase/): switch between Keycloak and Stack Auth with configuration only
- [agent-stackauth](../../agent-iam/agent-stackauth/): delegate a Stack Auth user's access to an AI agent
- [GL-IAM GitBook](https://gdplabs.gitbook.io/sdk/gl-iam) · [Stack Auth OAuth providers](https://docs.stack-auth.com/docs/concepts/auth-providers)
