"""
"Sign in with Google" with Hexclave (formerly Stack Auth) + GL-IAM.

- index.html: Hexclave's browser SDK signs the user in with Google (no OAuth code here).
- main.py:    GL-IAM checks the user's token on every protected endpoint.
"""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import HTMLResponse
from gl_iam import IAMGateway, User
from gl_iam.fastapi import add_exception_handlers, get_current_user, set_iam_gateway
from gl_iam.providers.stackauth import StackAuthConfig, StackAuthProvider

load_dotenv()

HEXCLAVE = {
    "baseUrl": os.getenv("HEXCLAVE_API_URL", "https://api.hexclave.com"),
    "projectId": os.environ["HEXCLAVE_PROJECT_ID"],
    "publishableClientKey": os.environ["HEXCLAVE_PUBLISHABLE_CLIENT_KEY"],
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Connect GL-IAM to Hexclave so it can validate Hexclave access tokens."""
    provider = StackAuthProvider(
        StackAuthConfig(
            error_policy="typed",
            base_url=HEXCLAVE["baseUrl"],
            project_id=HEXCLAVE["projectId"],
            publishable_client_key=HEXCLAVE["publishableClientKey"],
        )
    )
    set_iam_gateway(IAMGateway.from_fullstack_provider(provider), default_organization_id=HEXCLAVE["projectId"])
    yield
    await provider.close()


app = FastAPI(title="Sign in with Google (Hexclave + GL-IAM)", lifespan=lifespan)
add_exception_handlers(app, error_policy="v1.2")  # GL-IAM errors -> safe 401/403/503 responses


@app.get("/", response_class=HTMLResponse)
async def home():
    """The sign-in page, with this project's Hexclave settings filled in."""
    page = (Path(__file__).parent / "index.html").read_text()
    return page.replace("HEXCLAVE_SETTINGS", json.dumps(HEXCLAVE))


@app.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]):
    """Protected: needs `Authorization: Bearer <Hexclave access token>`."""
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "roles": user.roles}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
