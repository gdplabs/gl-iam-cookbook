"""
Asymmetric delegation signing: the ISSUER (port 8000).

This is the service that holds the private key -- GLChat, or AIP, or whatever
mints delegation tokens in your deployment. It can do two things a verifier
cannot:

1. Sign delegation tokens.
2. Publish the public half of its key at ``/.well-known/jwks.json``.

The only thing that makes this the issuer is the ``private_key`` on its
``JWTKey``. Everything else is identical to the verifier's configuration.

Run:
    uv run issuer.py          # http://localhost:8000
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from demo_agent import AGENT_ID, CONNECTOR_AUDIENCE, ISSUER_KID, ORG_ID, USER_ID, demo_agent
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from gl_iam import (
    DelegationScope,
    IAMGateway,
    JWTKey,
    SigningAlgorithm,
    SigningConfig,
    TaskContext,
)
from gl_iam.fastapi import add_exception_handlers
from gl_iam.providers.native import NativeAgentProvider, NativeConfig

load_dotenv()

PRIVATE_KEY_PATH = Path(__file__).parent / "keys" / "issuer_private.pem"

gateway: IAMGateway | None = None
signing_config: SigningConfig | None = None


def build_signing_config() -> SigningConfig:
    """Load the private key and pin the algorithm it may be used with.

    Returns:
        SigningConfig: A signing-capable config -- it can mint and verify.

    Raises:
        SystemExit: If the key pair has not been generated yet.
    """
    if not PRIVATE_KEY_PATH.exists():
        raise SystemExit(f"Missing {PRIVATE_KEY_PATH}. Run: uv run generate_keys.py")

    return SigningConfig(
        keys=[
            JWTKey(
                # The kid travels in the token header. A verifier uses it to
                # pick which configured key to try -- which is what makes
                # rotation possible without a synchronised cutover.
                kid=ISSUER_KID,
                algorithm=SigningAlgorithm.ES256,
                private_key=PRIVATE_KEY_PATH.read_text(),
                # Binding the key to an audience means a token minted with it
                # is only ever accepted by a verifier that expects that
                # audience. See the verifier for the other half.
                audience=CONNECTOR_AUDIENCE,
            )
        ]
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build one gateway configured to sign with the private key."""
    global gateway, signing_config

    signing_config = build_signing_config()

    # No database connection is ever opened: minting a delegation token is
    # stateless JWT work, and the AgentIdentity is handed in directly below.
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

    # `secret_key` takes the SigningConfig in the same slot a shared HMAC
    # string used to occupy. That is the whole migration.
    gateway = IAMGateway(agent_provider=provider, secret_key=signing_config)

    yield


app = FastAPI(
    title="Issuer - holds the private key",
    description="Mints delegation tokens and publishes its public key as JWKS",
    lifespan=lifespan,
)
add_exception_handlers(app)


class DelegateRequest(BaseModel):
    """What the caller wants the agent to be allowed to do."""

    scopes: list[str] = ["reports:read"]
    task_purpose: str = "Draft the Q3 revenue summary"


@app.get("/.well-known/jwks.json")
async def jwks() -> dict:
    """Publish the public half of the key set.

    This is the entire distribution mechanism. Verifiers read this and need
    nothing else -- no shared secret, no credential exchange, no network call
    per token.

    Returns:
        dict: A standard JWKS document. `to_jwks()` never exports private key
            material, and it omits HMAC keys entirely, so this response is
            safe to serve publicly.
    """
    assert signing_config is not None
    return signing_config.to_jwks()


@app.post("/delegate")
async def delegate(request: DelegateRequest) -> dict:
    """Mint a delegation token signed with the private key.

    Args:
        request (DelegateRequest): The scopes and task to delegate.

    Returns:
        dict: The signed token and what it grants.

    Raises:
        HTTPException: 403 when GL-IAM refuses the delegation.
    """
    assert gateway is not None

    principal = gateway.mint_principal_jwt(sub=USER_ID, ttl_seconds=300)
    if principal.is_err:
        raise HTTPException(status_code=500, detail=principal.error.message)

    result = await gateway.delegate_to_agent(
        principal_token=principal.value,
        agent_id=AGENT_ID,
        task=TaskContext(id="task-001", purpose=request.task_purpose),
        scope=DelegationScope(scopes=request.scopes, expires_in_seconds=300),
        agent=demo_agent(),
        # Stamps `aud` and selects the audience-bound signing key. A verifier
        # configured for a different audience will reject the result.
        audience=CONNECTOR_AUDIENCE,
    )
    if result.is_err:
        raise HTTPException(status_code=403, detail=result.error.message)

    delegation = result.unwrap()
    return {
        "token": delegation.token,
        "agent_id": delegation.agent_id,
        "scopes": delegation.scope.scopes,
        "audience": CONNECTOR_AUDIENCE,
        "expires_at": delegation.expires_at.isoformat(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
