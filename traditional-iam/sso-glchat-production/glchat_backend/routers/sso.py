"""Public SSO endpoints called by the partner backend and the widget."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from glchat_backend.config import get_settings
from glchat_backend.middleware.rate_limit import check as rate_limit_check
from glchat_backend.services.sso_service import SSOService


router = APIRouter(prefix="/api/v1/sso", tags=["sso"])


class SSOTokenRequest(BaseModel):
    consumer_key: str
    signature: str
    timestamp: str
    nonce: str
    payload: str  # JSON string


class SSOTokenResponse(BaseModel):
    token: str
    expires_in: int


class SSOAuthenticateRequest(BaseModel):
    """Matches the architecture doc: `POST /api/v1/sso/authenticate {sso_token}`.
    See: https://github.com/GDP-ADMIN/gl-sdk/blob/main/libs/gl-iam/docs/architecture/IDP_VS_SP_INITIATED_SSO_COMPARISON.md
    """
    sso_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


def get_sso_service(request: Request) -> SSOService:
    return request.app.state.sso_service


@router.post("/token", response_model=SSOTokenResponse)
async def issue_sso_token(
    request: Request,
    body: SSOTokenRequest,
    sso: SSOService = Depends(get_sso_service),
):
    await rate_limit_check(request, get_settings().rate_limit_sso_token)
    token = await sso.issue_token(
        consumer_key=body.consumer_key,
        signature=body.signature,
        timestamp=body.timestamp,
        nonce=body.nonce,
        payload=body.payload,
        source_ip=getattr(request.state, "client_ip", None),
    )
    return SSOTokenResponse(token=token, expires_in=get_settings().sso_token_ttl_seconds)


@router.post("/authenticate", response_model=TokenResponse)
async def authenticate(
    request: Request,
    body: SSOAuthenticateRequest,
    sso: SSOService = Depends(get_sso_service),
):
    await rate_limit_check(request, get_settings().rate_limit_sso_auth)
    access_token, token_type = await sso.exchange_token(body.sso_token)
    return TokenResponse(access_token=access_token, token_type=token_type)
