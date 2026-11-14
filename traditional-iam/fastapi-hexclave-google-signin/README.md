# Sign in with Google — Next.js + FastAPI + Hexclave (Stack Auth)

> **Error handling v1.2:** This example requires `gl-iam>=0.3.25,<0.4.0`
> from PyPI and Python 3.12 or 3.13. Read the
> [migration and installation notes](../../ERROR_HANDLING.md) before running it.

## Overview

"Sign in with Google" with **no OAuth code and no sign-in UI to build**:

- **Next.js ([web/](web/))** shows Hexclave's prebuilt `<SignIn />` component.
- **FastAPI ([main.py](main.py))** uses GL-IAM to check the user's token on every protected endpoint.

> **Stack Auth is now [Hexclave](https://docs.hexclave.com/)**. GL-IAM's `StackAuthProvider` works with it unchanged.

![Architecture: the Next.js app signs in with Google via Hexclave, then calls FastAPI, which verifies the token through GL IAM](images/architecture.png)

![Sequence: Google sign-in via Hexclave's SignIn component, then GET /me validated by GL IAM](images/sign-in-sequence.png)

The prebuilt component makes sign-in easy, but it does **not** replace checking the token on the backend.
`get_current_user` does that check.

## Prerequisites

Please refer to prerequisites [here](../../README.md). Additionally, you need:

- **Node.js 20.12+** (for the Next.js app).
- A Hexclave project ([app.hexclave.com](https://app.hexclave.com)) and its **project ID** and
  **publishable client key** (dashboard → **Project Keys**). No secret key is needed.

## Quick Start

1. **Hexclave dashboard**

   - **Auth Methods:** turn on **Google** (the shared development keys are fine).
   - **Domains:** turn on **Allow all localhost callbacks for development**.

2. **Install** (backend and web app)

   ```bash
   cd gl-iam-cookbook/traditional-iam/fastapi-hexclave-google-signin/
   ./setup.sh        # Windows: setup.bat
   ```

3. **Fill in `.env`**. Both apps read this one file.

   ```bash
   HEXCLAVE_PROJECT_ID=your-project-id
   HEXCLAVE_PUBLISHABLE_CLIENT_KEY=pck_your_publishable_key
   ```

4. **Run** both, in two terminals

   ```bash
   uv run main.py            # FastAPI on :8000
   ```

   ```bash
   cd web && npm run dev     # Next.js on :3000
   ```

5. **Sign in**: open <http://localhost:3000/>, click **Sign in with Google**. You land back on the home page:

   ```
   GET /me {
     "id": "3f1c...",
     "email": "you@gmail.com",
     "display_name": "Your Name",
     "roles": []
   }
   ```

## Understanding the Code

### web/: Next.js

| File | What it does |
|---|---|
| [app/layout.jsx](web/app/layout.jsx) | Creates the Hexclave app and wraps every page in `HexclaveProvider`. |
| [app/sign-in/page.jsx](web/app/sign-in/page.jsx) | The sign-in page: just `<SignIn />`. |
| [app/page.jsx](web/app/page.jsx) | Home page. Signed out → `/sign-in`. Signed in → calls `GET /me`. |
| [app/loading.jsx](web/app/loading.jsx) | Shown while Hexclave loads the user. |
| [next.config.mjs](web/next.config.mjs) | Reads `../.env`, and forwards `/api/*` to FastAPI (no CORS needed). |

**Sign-in page**: the whole thing.

```jsx
import { SignIn } from "@hexclave/next";

export default function SignInPage() {
  return <SignIn />;
}
```

`<SignIn />` shows every method enabled in the dashboard and handles the return from Google itself.

**Hexclave app** ([app/layout.jsx](web/app/layout.jsx)):

```jsx
const hexclave = new HexclaveClientApp({
  tokenStore: "nextjs-cookie",                                 // session lives in a cookie
  urls: { default: { type: "hosted" }, signIn: "/sign-in" },  // our page for sign-in, Hexclave-hosted for the rest
});
```

**Calling the backend** ([app/page.jsx](web/app/page.jsx)):

```jsx
const user = useUser({ or: "redirect" });   // signed out -> /sign-in
const token = await user.getAccessToken();  // Hexclave access token (a JWT)
fetch("/api/me", { headers: { Authorization: `Bearer ${token}` } });
```

Use `getAccessToken()`, not `getAuthorizationHeader()`: the latter returns a Hexclave-only
`Bearer stackauth_...` value that GL-IAM does not accept.

### main.py: FastAPI + GL-IAM

```python
@app.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]):
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "roles": user.roles}
```

`get_current_user` reads `Authorization: Bearer <token>` and asks Hexclave who it belongs to (through
`StackAuthProvider`). No token or a bad token returns `401`. This is the same code as
[fastapi-stackauth](../fastapi-stackauth/): GL-IAM doesn't care how the user signed in. Add roles with
`Depends(require_org_member())` or `Depends(require_org_admin())`, as in that example.
