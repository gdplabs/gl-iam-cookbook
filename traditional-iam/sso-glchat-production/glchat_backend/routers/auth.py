"""Admin login (password → JWT) and current-user endpoint.

Admin logs in via standard GL-IAM password auth to obtain a JWT which the
admin UI then uses to call `/admin/*`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from gl_iam import User
from gl_iam.core.types import PasswordCredentials
from gl_iam.fastapi import get_current_user, get_iam_gateway

from glchat_backend.config import get_settings


router = APIRouter(tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None
    roles: list[str] = []


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    gateway = get_iam_gateway()
    result = await gateway.authenticate(
        credentials=PasswordCredentials(email=body.email, password=body.password),
        organization_id=get_settings().default_org_id,
    )
    if result.is_err:
        raise HTTPException(401, result.error.message)
    return TokenResponse(
        access_token=result.token.access_token,
        token_type=result.token.token_type,
    )


@router.get("/api/v1/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    gateway = get_iam_gateway()
    roles = await gateway.user_store.get_user_roles(user.id, get_settings().default_org_id)
    return UserResponse(
        id=user.id, email=user.email, display_name=user.display_name, roles=roles or []
    )
