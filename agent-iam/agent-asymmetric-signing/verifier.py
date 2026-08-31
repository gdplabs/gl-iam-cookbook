"""
Asymmetric delegation signing: the VERIFIER (port 8001).

This is a service at a credential-holding boundary -- GL Connectors, or any
service that must independently check an agent's authority before doing
something irreversible.

It is configured entirely from the issuer's public JWKS. That gives it one
property a shared HMAC secret cannot: **it can verify, and it cannot mint**.
Compromising it yields no ability to forge a delegation for any agent.

`GET /can-i-mint` proves it, by asking this gateway to sign something and
showing the refusal.

Run:
    uv run verifier.py        # http://localhost:8001
"""

import os
from contextlib import asynccontextmanager

import httpx
from demo_agent import CONNECTOR_AUDIENCE, ORG_ID
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import IAMGateway, SigningConfig
from gl_iam.fastapi import add_exception_handlers
from gl_iam.providers.native import NativeAgentProvider, NativeConfig

load_dotenv()

ISSUER_URL = os.getenv("ISSUER_URL", "http://localhost:8000")

gateway: IAMGateway | None = None


async def fetch_verification_config() -> SigningConfig:
    """Build a verification-only config from the issuer's published JWKS.

    Every key imported from a JWKS is public-only -- that is the point, and it
    is not something the caller has to remember to ask for.

    Returns:
        SigningConfig: A config that can verify and cannot sign.

    Raises:
        SystemExit: If the issuer is not reachable.
    """
    url = f"{ISSUER_URL}/.well-known/jwks.json"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            document = response.json()
    except httpx.HTTPError as exc:
        raise SystemExit(f"Could not fetch {url}: {exc}. Start the issuer first.") from exc

    # JWKS is a standard public-key document and has no audience member, so the
    # binding cannot travel in it. Expecting a particular audience is this
    # verifier's own policy, declared here.
    return SigningConfig.from_jwks(document, audience=CONNECTOR_AUDIENCE)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Fetch the issuer's public keys once, at startup."""
    global gateway

    verification_config = await fetch_verification_config()

    provider = NativeAgentProvider(
        NativeConfig(
            database_url=os.getenv(
                "DATABASE_URL",
                "postgresql+asyncpg://postgres:postgres@localhost:5432/gliam",
            ),
            default_org_id=ORG_ID,
            enable_third_party_provider=False,
            # This provider hosts no user login, only agents. Leaving auth
            # hosting on would make NativeConfig demand a `secret_key` for
            # session access tokens that are never issued here -- and this
            # example deliberately has no shared secret anywhere.
            enable_auth_hosting=False,
        )
    )
    gateway = IAMGateway.for_agent_auth(
        agent_provider=provider,
        secret_key=verification_config,
    )

    print(f"Loaded {len(verification_config.keys)} public key(s) from {ISSUER_URL}")
    print(f"Pinned algorithms: {verification_config.algorithms}")
    print(f"Can this service mint tokens? {verification_config.can_sign}")

    yield


app = FastAPI(
    title="Verifier - holds only the public key",
    description="Validates delegation tokens and cannot issue them",
    lifespan=lifespan,
)
add_exception_handlers(app)


class ToolCallRequest(BaseModel):
    """A tool call presented with the agent's delegation token."""

    token: str
    recipient: str = "finance@example.com"


@app.post("/tools/send-email")
async def send_email(request: ToolCallRequest) -> dict:
    """Validate the delegation token, then enforce the scope it carries.

    Validation establishes that the token is authentic and unexpired. It does
    not decide whether *this* call is allowed -- that is the scope check
    below, and it is always the calling service's job.

    Args:
        request (ToolCallRequest): The token and the email recipient.

    Returns:
        dict: What the verifier established, and the simulated tool result.

    Raises:
        HTTPException: 401 when the token does not validate, 403 when it
            validates but does not carry `email:send`.
    """
    assert gateway is not None

    result = await gateway.validate_delegation_token(token=request.token)
    if result.is_err:
        raise HTTPException(
            status_code=401,
            detail=f"{result.error.code}: {result.error.message}",
        )

    delegation = result.unwrap()

    if "email:send" not in delegation.scope.scopes:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Token is authentic but carries {delegation.scope.scopes}, "
                "not 'email:send'."
            ),
        )

    return {
        "sent_to": request.recipient,
        "on_behalf_of": delegation.chain.root_principal.principal_id,
        "agent": delegation.agent_id,
        "scopes": delegation.scope.scopes,
        "task": delegation.task.purpose,
    }


@app.get("/can-i-mint")
async def can_i_mint() -> dict:
    """Show that this process cannot issue a token, only check one.

    Returns:
        dict: The refusal from GL-IAM, which is the security property this
            recipe exists to demonstrate.
    """
    assert gateway is not None

    result = gateway.mint_principal_jwt(sub="user:mallory")
    if result.is_ok:
        return {"can_mint": True, "warning": "Unexpected -- check the configuration."}

    return {
        "can_mint": False,
        "error_code": str(result.error.code),
        "detail": result.error.message,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
