"""
DPoP Standalone Demo - FastAPI Resource Server (no Keycloak, no database).

This server validates DPoP-bound access tokens using GL-IAM's
StandaloneDPoPProvider. It proves that DPoP in GL-IAM does NOT depend on
Keycloak. The proof validation, replay protection, and cnf.jkt token-binding
checks all run locally with PyJWT + cryptography.

Request shape for the protected endpoint (RFC 9449):
    Authorization: DPoP <access_token>
    DPoP: <dpop_proof_jwt>

The proof must be signed with the SAME private key whose thumbprint is in the
token's cnf.jkt claim. Steal the token alone -> rejected.
"""

import os

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from gl_iam import DPoPConfig
from gl_iam.providers.dpop import StandaloneDPoPProvider

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set. Copy .env.example to .env first.")

# The standalone DPoP engine. No Keycloak, no introspection endpoint.
# nonce_enabled=False keeps the curl demo to a single round-trip; flip it on
# (and handle the 401 + DPoP-Nonce retry) for production replay hardening.
dpop_provider = StandaloneDPoPProvider(DPoPConfig(enabled=True, required=True, nonce_enabled=False))

app = FastAPI(title="DPoP Standalone Demo (no Keycloak)")


class UserResponse(BaseModel):
    sub: str
    org_id: str
    bound_key: str


def _verify_access_token(token: str) -> dict:
    """Verify the access token signature/expiry (the resource server's job).

    In a real deployment this is your normal session/JWT validation (GL-IAM's
    session provider, your AS's JWKS, etc.). DPoP is layered ON TOP of it.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid access token: {e}") from e


async def require_dpop(
    request: Request,
    authorization: str | None = Header(default=None),
    dpop: str | None = Header(default=None),
) -> dict:
    """FastAPI dependency: enforce a valid DPoP-bound request.

    Steps (RFC 9449 §4.3 + §6), all via StandaloneDPoPProvider:
      1. Parse `Authorization: DPoP <token>` and the `DPoP: <proof>` header.
      2. Verify the access token itself.
      3. Validate the proof (signature, htm/htu, iat, ath, replay).
      4. Confirm the proof's key thumbprint matches the token's cnf.jkt.
    """
    if not authorization or not authorization.lower().startswith("dpop "):
        raise HTTPException(status_code=401, detail="Expected 'Authorization: DPoP <token>'")
    if not dpop:
        raise HTTPException(status_code=401, detail="Missing DPoP proof header")

    access_token = authorization.split(" ", 1)[1].strip()
    claims = _verify_access_token(access_token)

    http_uri = str(request.url).split("?", 1)[0]

    # 3. Validate the proof (binds it to this method + URL + token hash).
    proof_result = await dpop_provider.validate_dpop_proof(
        dpop_proof=dpop,
        http_method=request.method,
        http_uri=http_uri,
        access_token=access_token,
    )
    if proof_result.is_err:
        raise HTTPException(status_code=401, detail=f"DPoP proof rejected: {proof_result.error.message}")

    # 4. Confirm token binding: proof key thumbprint == token cnf.jkt.
    binding_result = await dpop_provider.validate_token_binding(
        access_token=access_token,
        jwk_thumbprint=proof_result.value.jwk_thumbprint,
    )
    if binding_result.is_err:
        raise HTTPException(status_code=401, detail=f"Token binding failed: {binding_result.error.message}")

    return claims


@app.get("/health")
async def health():
    """Public health check."""
    return {"status": "healthy", "dpop": "enabled", "provider": "standalone", "keycloak": False}


@app.get("/api/public")
async def public():
    """Public endpoint - no authentication."""
    return {"message": "This is a public endpoint"}


@app.get("/api/protected", response_model=UserResponse)
async def protected(claims: dict = Depends(require_dpop)):
    """DPoP-protected endpoint - requires a valid token AND a matching proof."""
    return UserResponse(
        sub=claims["sub"],
        org_id=claims.get("org_id", ""),
        bound_key=claims.get("cnf", {}).get("jkt", ""),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
