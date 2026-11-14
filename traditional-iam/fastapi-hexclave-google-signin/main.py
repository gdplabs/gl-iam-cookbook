"""FastAPI backend: GL-IAM checks the Hexclave access token sent by the Next.js app (web/)."""

import os
from contextlib import asynccontextmanager
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from gl_iam import IAMGateway, User
from gl_iam.fastapi import add_exception_handlers, get_current_user, set_iam_gateway
from gl_iam.providers.stackauth import StackAuthConfig, StackAuthProvider

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Hexclave was formerly Stack Auth, so GL-IAM's StackAuthProvider works with it unchanged.
    provider = StackAuthProvider(
        StackAuthConfig(
            error_policy="typed",
            base_url=os.getenv("HEXCLAVE_API_URL", "https://api.hexclave.com"),
            project_id=os.environ["HEXCLAVE_PROJECT_ID"],
            publishable_client_key=os.environ["HEXCLAVE_PUBLISHABLE_CLIENT_KEY"],
        )
    )
    set_iam_gateway(IAMGateway.from_fullstack_provider(provider), default_organization_id=os.environ["HEXCLAVE_PROJECT_ID"])
    yield
    await provider.close()


app = FastAPI(lifespan=lifespan)
add_exception_handlers(app, error_policy="v1.2")  # GL-IAM errors -> safe 401/403 JSON


@app.get("/me")
async def me(user: Annotated[User, Depends(get_current_user)]):
    """Needs `Authorization: Bearer <Hexclave access token>`."""
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "roles": user.roles}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
