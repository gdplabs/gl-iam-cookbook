"""Trusted Partner backend — simulates an external IdP (e.g., Lokadata).

Responsibilities:
- Hosts a local username/password login (toy — real partners have their own).
- Issues its own session cookie.
- When the user clicks "Open GLChat", calls GLChat BE /api/v1/sso/token
  with a fresh HMAC-signed assertion containing a nonce.
- Returns the one-time SSO token to the partner FE, which then opens the
  GLChat widget in an iframe and delivers the token via postMessage.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from itsdangerous import BadSignature, URLSafeTimedSerializer
from pydantic import BaseModel

from partner_backend.hmac_signer import sign_user_assertion

load_dotenv()
logging.basicConfig(level=logging.WARNING, format="%(asctime)s [partner-be] %(message)s")
logger = logging.getLogger("partner_backend")
logger.setLevel(logging.INFO)

# Reuse GLChat backend's pretty logger for consistent styling across terminals.
# Import `app` as `plog_app` to avoid clashing with the FastAPI `app` below.
from glchat_backend.pretty_log import C, banner, done, err, kv, sdk  # noqa: E402
from glchat_backend.pretty_log import app as plog_app  # noqa: E402

GLCHAT_BACKEND_URL = os.environ.get("GLCHAT_BACKEND_URL", "http://localhost:8000")
PARTNER_SITE_ORIGIN = os.environ.get("PARTNER_SITE_ORIGIN", "http://localhost:3001")
GLCHAT_WIDGET_ORIGIN = os.environ.get("GLCHAT_WIDGET_ORIGIN", "http://localhost:3003")
SESSION_SECRET = os.environ["PARTNER_SESSION_SECRET"]

# Toy user store — in real life this is the partner's production user DB.
PARTNER_USERS: dict[str, dict] = {
    "alice@trusted-partner.example.com": {
        "password": "alice-pass",
        "external_id": "partner-001",
        "display_name": "Alice Example",
    },
    "bob@trusted-partner.example.com": {
        "password": "bob-pass",
        "external_id": "partner-002",
        "display_name": "Bob Example",
    },
}

serializer = URLSafeTimedSerializer(SESSION_SECRET, salt="partner-session")


app = FastAPI(title="Trusted Partner Backend (simulated IdP)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[PARTNER_SITE_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    email: str
    password: str


class StartSSOResponse(BaseModel):
    sso_token: str
    widget_url: str


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "partner-backend"}


@app.post("/api/login")
async def login(body: LoginRequest, response: Response):
    banner(
        "POST /api/login  —  user logs in to partner site",
        color=C.MAGENTA,
        subtitle="This is the ONLY credential entry. GLChat is not contacted here.",
    )
    kv("email", body.email)
    user = PARTNER_USERS.get(body.email)
    if not user or user["password"] != body.password:
        err(f"Invalid credentials for {body.email}")
        raise HTTPException(401, "Invalid credentials")
    cookie_value = serializer.dumps({"email": body.email})
    response.set_cookie(
        "partner_session",
        cookie_value,
        httponly=True,
        samesite="lax",
        secure=False,  # True in production with TLS
        max_age=3600,
    )
    plog_app("Partner session cookie issued",
        f"partner_session={cookie_value[:16]}… HttpOnly SameSite=lax max_age=3600")
    done(f"User {body.email} authenticated at the partner (IdP side)")
    return {"email": body.email, "display_name": user["display_name"]}


def _session_email(cookie: str | None) -> str:
    if not cookie:
        raise HTTPException(401, "Not logged in to partner site")
    try:
        data = serializer.loads(cookie, max_age=3600)
    except BadSignature:
        raise HTTPException(401, "Invalid partner session")
    return data["email"]


@app.post("/api/me")
async def me(partner_session: Annotated[str | None, Cookie()] = None):
    email = _session_email(partner_session)
    user = PARTNER_USERS[email]
    return {"email": email, "display_name": user["display_name"]}


@app.post("/api/start-sso", response_model=StartSSOResponse)
async def start_sso(partner_session: Annotated[str | None, Cookie()] = None):
    """User-triggered server-to-server: fetch one-time SSO token from GLChat BE."""
    email = _session_email(partner_session)
    user = PARTNER_USERS[email]

    banner(
        "POST /api/start-sso  —  partner BE mints an SSO assertion",
        color=C.MAGENTA,
        subtitle="Server-to-server: partner BE → GLChat BE /api/v1/sso/token (HMAC-signed)",
    )
    kv("user", email)
    kv("external_id", user["external_id"])

    consumer_key = os.environ.get("PARTNER_CONSUMER_KEY", "").strip()
    consumer_secret = os.environ.get("PARTNER_CONSUMER_SECRET", "").strip()
    if not consumer_key or not consumer_secret:
        err("Partner not yet registered with GLChat. Run scripts/bootstrap_partner.py.")
        raise HTTPException(
            500,
            "Partner not yet registered with GLChat. Run scripts/bootstrap_partner.py.",
        )
    kv("consumer_key", consumer_key)
    kv("consumer_secret", f"{consumer_secret[:6]}… (stored server-side, NEVER sent)")

    assertion = sign_user_assertion(
        consumer_key=consumer_key,
        consumer_secret=consumer_secret,
        user={
            "email": email,
            "external_id": user["external_id"],
            "display_name": user["display_name"],
            "role": "member",
        },
    )
    plog_app("Built HMAC-SHA256 assertion",
        f"timestamp={assertion['timestamp']} nonce={assertion['nonce'][:12]}… sig={assertion['signature'][:20]}…")

    async with httpx.AsyncClient(timeout=10.0) as client:
        plog_app("→ GLChat BE", f"POST {GLCHAT_BACKEND_URL}/api/v1/sso/token")
        resp = await client.post(f"{GLCHAT_BACKEND_URL}/api/v1/sso/token", json=assertion)

    if resp.status_code != 200:
        err(f"GLChat rejected: {resp.status_code} {resp.text}")
        raise HTTPException(resp.status_code, f"GLChat rejected SSO request: {resp.text}")

    sso_token = resp.json()["token"]
    done(f"Got one-time SSO token {sso_token[:16]}… (TTL 60s) — returning to partner FE")
    return StartSSOResponse(sso_token=sso_token, widget_url=f"{GLCHAT_WIDGET_ORIGIN}/")


@app.post("/api/logout")
async def logout(response: Response):
    response.delete_cookie("partner_session")
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
