"""SSO Partner Client — simulates a partner system calling the SSO receiver.

This script demonstrates the full SSO flow from the partner's perspective:
1. Register as an SSO partner (one-time setup via admin API)
2. Compute HMAC-SHA256 signature for a user payload
3. Call POST /api/v1/sso/token to get a one-time token
4. Call POST /api/v1/sso/authenticate to exchange for a JWT
5. Call GET /api/v1/me to prove the SSO session works

Usage:
    # With a running sso_receiver.py on port 8000:
    uv run partner_client.py

    # Or with a pre-existing consumer key and secret:
    uv run partner_client.py --consumer-key sso_xxx --consumer-secret yyy
"""

import argparse
import hashlib
import hmac
import json
import sys
from datetime import datetime, timezone

import httpx

BASE_URL = "http://localhost:8000"


def compute_hmac_signature(consumer_key: str, consumer_secret: str, payload: str, timestamp: str) -> str:
    """Compute HMAC-SHA256 signature matching GL-IAM's expected format.

    Format: HMAC-SHA256(secret, "timestamp|consumer_key|payload")
    """
    message = f"{timestamp}|{consumer_key}|{payload}"
    return hmac.new(
        consumer_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser(description="SSO Partner Client Simulator")
    parser.add_argument("--consumer-key", help="Pre-existing consumer key")
    parser.add_argument("--consumer-secret", help="Pre-existing consumer secret")
    parser.add_argument("--base-url", default=BASE_URL, help="SSO receiver base URL")
    args = parser.parse_args()

    base_url = args.base_url
    client = httpx.Client(base_url=base_url, timeout=30)

    print("=" * 60)
    print("SSO Partner Client — Token Exchange Flow")
    print("=" * 60)

    # Step 0: Health check
    print("\n--- Step 0: Health check ---")
    resp = client.get("/health")
    print(f"Status: {resp.status_code}, Body: {resp.json()}")
    if resp.status_code != 200:
        print("ERROR: Server is not healthy. Is sso_receiver.py running?")
        sys.exit(1)

    # Step 1: Register partner (or use pre-configured credentials)
    if args.consumer_key and args.consumer_secret:
        consumer_key = args.consumer_key
        consumer_secret = args.consumer_secret
        print(f"\n--- Step 1: Using pre-configured credentials ---")
        print(f"Consumer Key: {consumer_key}")
    else:
        print("\n--- Step 1: Register as SSO partner ---")
        resp = client.post(
            "/admin/partners",
            json={
                "partner_name": "Lokadata Portal",
                "allowed_origins": ["https://lokadata.example.com"],
                "sso_mode": "idp_initiated",
                "user_provisioning": "jit",
                "metadata": {"contact": "admin@lokadata.example.com"},
            },
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error: {resp.json()}")
            sys.exit(1)

        partner = resp.json()
        consumer_key = partner["consumer_key"]
        consumer_secret = partner["consumer_secret"]
        print(f"Partner ID: {partner['id']}")
        print(f"Consumer Key: {consumer_key}")
        print(f"Consumer Secret: {consumer_secret[:8]}... (save this!)")

    # Step 2: Prepare user payload and compute HMAC signature
    print("\n--- Step 2: Compute HMAC signature ---")
    user_payload = {
        "email": "alice@lokadata.example.com",
        "display_name": "Alice from Lokadata",
        "external_id": "lok-user-001",
        "first_name": "Alice",
        "last_name": "Smith",
    }
    payload_str = json.dumps(user_payload, separators=(",", ":"))
    timestamp = datetime.now(timezone.utc).isoformat()

    signature = compute_hmac_signature(consumer_key, consumer_secret, payload_str, timestamp)
    print(f"Payload: {payload_str}")
    print(f"Timestamp: {timestamp}")
    print(f"Signature: {signature[:16]}...")

    # Step 3: Request one-time token
    print("\n--- Step 3: Request one-time token (POST /api/v1/sso/token) ---")
    resp = client.post(
        "/api/v1/sso/token",
        json={
            "consumer_key": consumer_key,
            "signature": signature,
            "timestamp": timestamp,
            "payload": payload_str,
        },
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.json()}")
        sys.exit(1)

    token_data = resp.json()
    one_time_token = token_data["token"]
    print(f"One-time token: {one_time_token[:16]}...")
    print(f"Expires in: {token_data['expires_in']}s")

    # Step 4: Exchange token for JWT session
    print("\n--- Step 4: Exchange token for JWT (POST /api/v1/sso/authenticate) ---")
    resp = client.post(
        "/api/v1/sso/authenticate",
        json={"token": one_time_token},
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Error: {resp.json()}")
        sys.exit(1)

    auth_data = resp.json()
    jwt_token = auth_data["access_token"]
    print(f"JWT: {jwt_token[:32]}...")
    print(f"Token type: {auth_data['token_type']}")

    # Step 5: Access protected endpoint
    print("\n--- Step 5: Access /api/v1/me with JWT ---")
    resp = client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {jwt_token}"},
    )
    print(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        me = resp.json()
        print(f"User ID: {me['id']}")
        print(f"Email: {me['email']}")
        print(f"Display Name: {me['display_name']}")
    else:
        print(f"Error: {resp.json()}")

    # Verify token replay fails
    print("\n--- Step 6: Verify token replay is rejected ---")
    resp = client.post(
        "/api/v1/sso/authenticate",
        json={"token": one_time_token},
    )
    print(f"Status: {resp.status_code} (expected 401)")
    print(f"Body: {resp.json()}")

    print("\n" + "=" * 60)
    print("SSO flow completed successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
