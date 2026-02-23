"""
Secure AI Agent API with Advanced GL-IAM Integration.

This example demonstrates all GL-IAM integration patterns:
1. User context in agent instruction
2. User-scoped session operations
3. Role-based tool filtering
4. Role-based agent configuration

GL-IAM provides: Authentication, Authorization, User/Role management
GL AIP SDK provides: Agent creation and local execution

Note: This example simulates agent responses when glaip-sdk is not available.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import IAMGateway, StandardRole, User
from gl_iam.core.types import PasswordCredentials, UserCreateInput
from gl_iam.fastapi import (
    get_current_user,
    get_iam_gateway,
    require_org_member,
    set_iam_gateway,
)
from gl_iam.providers.postgresql import PostgreSQLProvider, PostgreSQLConfig

load_dotenv()


# =============================================================================
# GL-IAM Helper Functions
# =============================================================================
def build_gliam_instruction(user: User, base_instruction: str) -> str:
    """
    Build agent instruction with GL-IAM user context.

    The agent will be aware of the user's identity and access level.
    """
    if user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        access = "Platform Administrator"
    elif user.has_standard_role(StandardRole.ORG_ADMIN):
        access = "Administrator"
    elif user.has_standard_role(StandardRole.ORG_MEMBER):
        access = "Member"
    else:
        access = "Viewer"

    security_context = f"""
[GL-IAM Security Context]
User: {user.email}
User ID: {user.id}
Organization: {user.organization_id}
Access Level: {access}
Roles: {", ".join(user.roles) if user.roles else "None"}

You must respect these access controls in all operations.
"""
    return f"{base_instruction}\n{security_context}"


def get_agent_config_for_user(user: User) -> dict:
    """
    Get role-appropriate agent configuration.

    Different users get different configurations based on their
    GL-IAM role hierarchy:
    - PLATFORM_ADMIN: Full access, planning enabled, long timeout
    - ORG_ADMIN: Standard config, moderate limits
    - ORG_MEMBER and below: Restricted config, lower limits
    """
    if user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        return {
            "planning": True,
            "timeout_seconds": 1800,  # 30 minutes
            "max_steps": 100,
        }
    if user.has_standard_role(StandardRole.ORG_ADMIN):
        return {
            "planning": True,
            "timeout_seconds": 600,  # 10 minutes
            "max_steps": 50,
        }
    return {
        "planning": False,
        "timeout_seconds": 120,  # 2 minutes
        "max_steps": 20,
    }


def get_tools_for_user(user: User, all_tools: list[str]) -> list[str]:
    """
    Filter tools based on GL-IAM roles.

    Non-admin users cannot access admin-only tools.
    """
    if user.has_standard_role(StandardRole.ORG_ADMIN):
        return all_tools  # Admins get all tools
    # Filter out admin-only tools for non-admin users
    return [t for t in all_tools if not t.startswith("admin_")]


def build_tool_config_from_user(user: User) -> dict:
    """
    Convert GL-IAM User to tool configuration for data scoping.

    This is the KEY INTEGRATION POINT between GL-IAM and AIP SDK.
    GL-IAM provides the authenticated user; we extract properties
    needed by tools for data scoping.
    """
    if user.has_standard_role(StandardRole.PLATFORM_ADMIN):
        access_level = "platform_admin"
    elif user.has_standard_role(StandardRole.ORG_ADMIN):
        access_level = "admin"
    elif user.has_standard_role(StandardRole.ORG_MEMBER):
        access_level = "member"
    else:
        access_level = "viewer"

    return {
        "user_id": user.id,
        "tenant_id": user.organization_id or "default",
        "access_level": access_level,
    }


# =============================================================================
# GL-IAM Application Setup
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan with GL-IAM initialization."""
    config = PostgreSQLConfig(
        database_url=os.getenv("DATABASE_URL"),
        secret_key=os.getenv("SECRET_KEY"),
        enable_auth_hosting=True,
        auto_create_tables=True,
    )
    provider = PostgreSQLProvider(config)
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(
        gateway, default_organization_id=os.getenv("DEFAULT_ORGANIZATION_ID")
    )

    app.state.provider = provider

    yield
    await provider.close()


app = FastAPI(title="GL-IAM + GL AIP SDK Advanced Integration", lifespan=lifespan)


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
    """Response model for chat with GL-IAM context."""

    response: str
    gliam_user_email: str
    gliam_access_level: str
    gliam_user_id: str
    agent_config: dict
    available_tools: list[str]


# =============================================================================
# Auth Endpoints
# =============================================================================
@app.get("/health")
async def health():
    """Public health check."""
    return {"status": "healthy"}


@app.post("/register", response_model=dict)
async def register(request: RegisterRequest):
    """Register a new user."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

    user = await gateway.user_store.create_user(
        UserCreateInput(
            email=request.email,
            display_name=request.display_name or request.email.split("@")[0],
        ),
        organization_id=org_id,
    )
    await gateway.user_store.set_user_password(user.id, request.password, org_id)

    return {"id": user.id, "email": user.email, "display_name": user.display_name}


@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login and get access token."""
    gateway = get_iam_gateway()
    org_id = os.getenv("DEFAULT_ORGANIZATION_ID")

    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=request.email, password=request.password),
        organization_id=org_id,
    )

    if result.is_ok:
        return TokenResponse(
            access_token=result.token.access_token,
            token_type=result.token.token_type,
        )
    else:
        raise HTTPException(status_code=401, detail=result.error.message)


# =============================================================================
# Protected Endpoint with GL-IAM + GL AIP SDK
# =============================================================================
@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    # GL-IAM Authentication & Authorization
    user: User = Depends(get_current_user),  # <-- GL-IAM: Get authenticated user
    _: None = Depends(require_org_member()),  # <-- GL-IAM: Require ORG_MEMBER+
):
    """
    Chat with AI agent using GL-IAM for security.

    Security layers:
    1. GL-IAM authenticates the user (get_current_user)
    2. GL-IAM checks ORG_MEMBER role (require_org_member)
    3. GL-IAM user context is injected into agent instruction
    4. GL-IAM roles determine agent configuration and available tools
    """
    # Build instruction with GL-IAM user context
    instruction = build_gliam_instruction(
        user=user,
        base_instruction="You are a helpful assistant with access to user data.",
    )

    # Get role-appropriate agent configuration
    agent_config = get_agent_config_for_user(user)

    # Get tools filtered by GL-IAM role
    all_tools = ["search", "calculator", "admin_delete", "admin_modify"]
    available_tools = get_tools_for_user(user, all_tools)

    # Build tool config with GL-IAM user context for data scoping
    tool_config = build_tool_config_from_user(user)

    # ==========================================================================
    # Agent Execution (with GL-IAM context)
    # When glaip-sdk is available, uncomment this:
    # ==========================================================================
    # agent = Agent(
    #     name="gliam-secured-agent",
    #     instruction=instruction,
    #     tools=available_tools,  # GL-IAM role-filtered tools
    #     agent_config=agent_config,  # GL-IAM role-based config
    # )
    # result = agent.run(
    #     request.message,
    #     session_id=user.id,  # GL-IAM User.id for memory scoping
    #     runtime_config={"tool_configs": tool_config},
    # )

    # Simulated response when glaip-sdk is not available
    access_level = (
        "admin" if user.has_standard_role(StandardRole.ORG_ADMIN) else "member"
    )
    result = (
        f"[Advanced Agent Response]\n"
        f"User: {user.display_name or user.email}\n"
        f"Access Level: {access_level}\n"
        f"Available Tools: {', '.join(available_tools)}\n"
        f"Agent Config: planning={agent_config['planning']}, timeout={agent_config['timeout_seconds']}s\n"
        f"Question: {request.message}\n"
        f"Response: I'm here to help! Your access level determines what tools I can use."
    )

    # Audit logging with GL-IAM user context
    print(f"[AUDIT] GL-IAM User {user.id} ({user.email}) - Agent action completed")

    return ChatResponse(
        response=result,
        gliam_user_email=user.email,
        gliam_access_level=access_level,
        gliam_user_id=user.id,
        agent_config=agent_config,
        available_tools=available_tools,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
