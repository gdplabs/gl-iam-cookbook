"""
Demo Authorization Server - mint a DPoP-bound (cnf.jkt) access token.

  +---------------------------------------------------------------+
  |  WHY THIS FILE EXISTS                                          |
  |                                                               |
  |  This script mints a DPoP-bound token (cnf.jkt) WITHOUT a DB, |
  |  so the example stays zero-infra. It produces exactly the     |
  |  token GL-IAM now issues first-party:                         |
  |                                                               |
  |      token = await gateway.create_dpop_bound_session(         |
  |          user, org_id, dpop_thumbprint=client.jwk_thumbprint) |
  |      # -> PostgreSQLSessionMixin.create_session adds cnf.jkt  |
  |      #    and sets token_type="DPoP"                          |
  |                                                               |
  |  Use the gateway call above in a real (DB-backed) deployment; |
  |  this inline mint is only to avoid requiring Postgres here.   |
  |  Keycloak (26.4+) binds tokens natively at its token endpoint.|
  +---------------------------------------------------------------+

Usage:
    python issue_token.py
"""

import json
import os
import time
import uuid

import jwt
from dotenv import load_dotenv

from gl_iam.dpop.thumbprint import compute_jwk_thumbprint

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set. Copy .env.example to .env first.")

TOKEN_TTL_SECONDS = 3600


def main():
    try:
        with open("keys/jwk.json", "r") as f:
            jwk = json.load(f)
    except FileNotFoundError:
        print("Error: keys/jwk.json not found. Run generate_key.py first.")
        raise SystemExit(1)

    # Bind the token to the client's public key (RFC 9449 §6: cnf.jkt).
    jkt = compute_jwk_thumbprint(jwk)

    now = int(time.time())
    claims = {
        "sub": "user-123",
        "jti": str(uuid.uuid4()),
        "org_id": "demo-org",
        "type": "access",
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        # >>> The DPoP binding. A bearer token has no cnf claim. <<<
        "cnf": {"jkt": jkt},
    }

    token = jwt.encode(claims, SECRET_KEY, algorithm="HS256")

    print("=" * 60)
    print("Minted a DPoP-BOUND access token (cnf.jkt present)")
    print("=" * 60)
    print(f"\ncnf.jkt = {jkt}")
    print("\nAccess token:\n")
    print(token)
    print("\nThe holder of this token CANNOT use it without also signing a")
    print("DPoP proof with the matching private key. Try it in the README.")
    print("=" * 60)


if __name__ == "__main__":
    main()
