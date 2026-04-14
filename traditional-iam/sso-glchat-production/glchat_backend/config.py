"""Runtime configuration for the GLChat backend."""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    database_url: str
    redis_url: str
    secret_key: str
    encryption_key: str
    default_org_id: str

    sso_token_ttl_seconds: int
    hmac_timestamp_tolerance_seconds: int
    nonce_ttl_seconds: int

    rate_limit_sso_token: str
    rate_limit_sso_auth: str

    partner_site_origin: str
    glchat_admin_origin: str
    glchat_widget_origin: str

    bootstrap_admin_email: str
    bootstrap_admin_password: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        redis_url=os.environ["REDIS_URL"],
        secret_key=os.environ["GLCHAT_SECRET_KEY"],
        encryption_key=os.environ["GLCHAT_ENCRYPTION_KEY"],
        default_org_id=os.environ.get("DEFAULT_ORGANIZATION_ID", "glchat"),
        sso_token_ttl_seconds=int(os.environ.get("SSO_TOKEN_TTL_SECONDS", "60")),
        hmac_timestamp_tolerance_seconds=int(os.environ.get("HMAC_TIMESTAMP_TOLERANCE_SECONDS", "60")),
        nonce_ttl_seconds=int(os.environ.get("NONCE_TTL_SECONDS", "120")),
        rate_limit_sso_token=os.environ.get("RATE_LIMIT_SSO_TOKEN", "20/minute"),
        rate_limit_sso_auth=os.environ.get("RATE_LIMIT_SSO_AUTH", "60/minute"),
        partner_site_origin=os.environ.get("PARTNER_SITE_ORIGIN", "http://localhost:3001"),
        glchat_admin_origin=os.environ.get("GLCHAT_ADMIN_ORIGIN", "http://localhost:3002"),
        glchat_widget_origin=os.environ.get("GLCHAT_WIDGET_ORIGIN", "http://localhost:3003"),
        bootstrap_admin_email=os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@glchat.example.com"),
        bootstrap_admin_password=os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "AdminPass123!"),
    )
