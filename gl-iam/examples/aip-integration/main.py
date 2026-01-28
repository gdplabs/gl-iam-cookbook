"""
Secure AI Agent API with GL-IAM authentication.

This example demonstrates how to use GL-IAM to secure AI agent endpoints.
It shows the key integration points between GL-IAM and agent APIs.

Note: This example simulates agent responses when glaip-sdk is not available.
When glaip-sdk is installed, uncomment the agent-related code.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

# =============================================================================
# GL-IAM Imports
# =============================================================================
from gl_iam import IAMGateway, StandardRole, User  # <-- GL-IAM
from gl_iam.core.types import PasswordCredentials, UserCreateInput  # <-- GL-IAM
from gl_iam.fastapi import (  # <-- GL-IAM
    get_current_user,
    get_iam_gateway,
    require_org_member,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import (  # <-- GL-IAM
    PostgreSQLProvider,
    PostgreSQLUserStoreConfig,
)

# =============================================================================
# GL AIP SDK Imports (Optional)
# Uncomment when glaip-sdk is installed
# =============================================================================
# from glaip_sdk import Agent

load_dotenv()


# =============================================================================
# GL-IAM Setup
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan with GL-IAM initialization.

    This sets up the GL-IAM gateway with PostgreSQL provider.
    """
    # Configure GL-IAM provider
    config = PostgreSQLUserStoreConfig(  # <-- GL-IAM
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_auth_hosting=True,
        auto_create_tables=True,
    )
    provider = PostgreSQLProvider(config)  # <-- GL-IAM
    gateway = IAMGateway.from_fullstack_provider(provider)  # <-- GL-IAM
    set_iam_gateway(  # <-- GL-IAM
        gateway, default_organization_id=os.getenv("DEFAULT_ORGANIZATION_ID")
    )
    yield
    await provider.close()


app = FastAPI(title="Secure Agent API", lifespan=lifespan)


# =============================================================================
# Request/Response Models
# =============================================================================
class RegisterRequest(BaseModel):
    """Request model for user registration."""
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    """Request model for user login."""
    email: str
    password: str


class TokenResponse(BaseModel):
    """Response model containing access token."""
    access_token: str
    token_type: str


class ChatRequest(BaseModel):
    """Request model for chat."""
    message: str


class ChatResponse(BaseModel):
    """Response model for chat."""
    response: str
    user_email: str
    access_level: str


# =============================================================================
# Public Endpoints
# =============================================================================
@app.get("/health")
async def health():
    """Public health check."""
    return {"status": "healthy"}


@app.post("/register", response_model=dict)
async def register(request: RegisterRequest):
    """Register a new user."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

    user = await gateway.user_store.create_user(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        organization_id=org_id,
    )
    await gateway.user_store.set_user_password(user.id, request.password, org_id)
    await gateway.user_store.assign_role(user.id, StandardRole.ORG_MEMBER.value, org_id)

    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login and get access token."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

    try:
        result = await gateway.authenticate(
            credentials=PasswordCredentials(email=request.email, password=request.password),
            organization_id=org_id,
        )
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")


# =============================================================================
# Protected Endpoints
# =============================================================================
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    # =========================================================================
    # GL-IAM Authentication & Authorization
    # =========================================================================
    user: User = Depends(get_current_user),  # <-- GL-IAM: Get authenticated user
    _: None = Depends(require_org_member()),  # <-- GL-IAM: Require ORG_MEMBER role
):
    """
    Chat with AI agent. Requires ORG_MEMBER role or higher.

    This endpoint demonstrates:
    1. GL-IAM authentication (get_current_user)
    2. GL-IAM role-based authorization (require_org_member)
    3. Using GL-IAM User properties in agent context
    """
    # =========================================================================
    # GL-IAM Role Check
    # =========================================================================
    if user.has_standard_role(StandardRole.ORG_ADMIN):  # <-- GL-IAM: Check role
        access_level = "Administrator"
    else:
        access_level = "Member"

    # =========================================================================
    # Agent Execution (with GL-IAM user context)
    # =========================================================================
    # When glaip-sdk is available, uncomment this:
    # agent = Agent(
    #     name="secure-assistant",
    #     instruction=f"""You are a helpful assistant.
    # Current user: {user.display_name or user.email}
    # Access level: {access_level}
    # """,
    # )
    # result = agent.run(request.message)

    # Simulated response when glaip-sdk is not available
    result = f"[Simulated Agent Response] Hello {user.display_name or user.email}! You asked: '{request.message}'. You have {access_level} access."

    return ChatResponse(
        response=result,
        user_email=user.email,  # <-- GL-IAM: User.email
        access_level=access_level,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
