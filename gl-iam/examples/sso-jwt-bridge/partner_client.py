"""SSO JWT Bridge partner client — simulates a partner signing a JWT.

This script demonstrates the SSO JWT Bridge flow from the partner's perspective:
1. Sign a short-lived JWT containing user claims with the shared secret.
2. Call POST /api/v1/sso/jwt-authenticate to exchange for a session JWT.
3. Call GET /api/v1/me to prove the SSO session works.

Usage:
    # With a running sso_receiver.py on port 8000:
    uv run partner_client.py

    # Or with a custom shared secret:
    uv run partner_client.py --secret "my-shared-secret-min-32-chars-long!!"
"""

import argparse
import sys
import time

import httpx
import jwt as pyjwt

BASE_URL = "http://localhost:8000"

# Must match SSO_SHARED_SECRET in the receiver's .env
DEFAULT_SHARED_SECRET = "shared-secret-between-partner-and-glchat-min-32-chars"
DEFAULT_ISSUER = "partner-portal"


def main():
    parser = argparse.ArgumentParser(description="SSO JWT Bridge Partner Client")
    parser.add_argument("--secret", default=DEFAULT_SHARED_SECRET, help="Shared secret")
    parser.add_argument("--issuer", default=DEFAULT_ISSUER, help="JWT issuer")
    parser.add_argument("--base-url", default=BASE_URL, help="SSO receiver base URL")
    args = parser.parse_args()

    client = httpx.Client(base_url=args.base_url, timeout=30)

    print("=" * 60)
    print("SSO JWT Bridge Partner Client")
    print("=" * 60)

    # Step 0: Health check
    print("\n--- Step 0: Health check ---")
    resp = client.get("/health")
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    if resp.status_code != 200:
        print("ERROR: Server is not healthy. Is sso_receiver.py running?")
        sys.exit(1)

    # Step 1: Create a signed JWT with user claims
    print("\n--- Step 1: Sign JWT with shared secret ---")
    now = int(time.time())
    claims = {
        "iss": args.issuer,
        "sub": "lok-user-002",
        "email": "bob@lokadata.example.com",
        "display_name": "Bob from Lokadata",
        "first_name": "Bob",
        "last_name": "Johnson",
        "iat": now,
        "exp": now + 60,  # 60 second expiry
    }
    partner_jwt = pyjwt.encode(claims, args.secret, algorithm="HS256")
    print(f"JWT: {partner_jwt[:40]}...")
    print(f"Claims: sub={claims['sub']}, email={claims['email']}")
    print(f"Expires in: 60s")

    # Step 2: Exchange JWT for session
    print("\n--- Step 2: Authenticate (POST /api/v1/sso/jwt-authenticate) ---")
    resp = client.post(
        "/api/v1/sso/jwt-authenticate",
        json={"partner_jwt": partner_jwt},
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.json()}")
        sys.exit(1)

    auth_data = resp.json()
    session_jwt = auth_data["access_token"]
    print(f"Session JWT: {session_jwt[:32]}...")
    print(f"Token type: {auth_data['token_type']}")

    # Step 3: Access protected endpoint
    print("\n--- Step 3: Access /api/v1/me with session JWT ---")
    resp = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {session_jwt}"},
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        me = resp.json()
        print(f"User ID: {me['id']}")
        print(f"Email: {me['email']}")
        print(f"Display Name: {me['display_name']}")
    else:
        print(f"Error: {resp.json()}")

    print("\n" + "=" * 60)
    print("SSO JWT Bridge flow completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
