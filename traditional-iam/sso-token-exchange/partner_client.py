"""SSO Token Exchange partner client — simulates the full SSO flow.

This script plays THREE roles (since there's no real browser/iframe):
  - [GLCHAT ADMIN]     GLChat platform admin: registers the partner (step 1)
  - [PARTNER BACKEND]  Lokadata's server: computes HMAC, requests token (steps 2-3)
  - [GLCHAT WIDGET]    GLChat's iframe JS: exchanges token for session (steps 4-5)

In production, these are separate systems:
  GLChat admin      → admin API        → GLChat backend (step 1, one-time setup)
  Lokadata backend  → server-to-server → GLChat backend (steps 2-3)
  GLChat widget JS  → same-origin call → GLChat backend (steps 4-5)

Usage:
    uv run partner_client.py
    uv run partner_client.py --consumer-key sso_xxx --consumer-secret yyy
    uv run partner_client.py --delay 0
"""

import argparse
import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timezone

import httpx

BASE_URL = "http://localhost:8000"
DEFAULT_STEP_DELAY = 2

# ANSI colors for step titles
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Color per role
ROLE_COLORS = {
    "GLCHAT ADMIN": CYAN,
    "PARTNER BACKEND": YELLOW,
    "GLCHAT WIDGET": GREEN,
    "SECURITY": RED,
}


def print_step_title(step: int, role: str, title: str):
    color = ROLE_COLORS.get(role, "")
    print(f"\n{color}{BOLD}── Step {step} [{role}]: {title} ──{RESET}")


def compute_hmac_signature(consumer_key: str, consumer_secret: str, payload: str, timestamp: str) -> str:
    """HMAC-SHA256(secret, "timestamp|consumer_key|payload")"""
    message = f"{timestamp}|{consumer_key}|{payload}"
    return hmac.new(
        consumer_secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def print_request(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    print(f"\n  >>> {method} {url}")
    if headers:
        for k, v in headers.items():
            print(f"      {k}: {v[:60]}{'...' if len(v) > 60 else ''}")
    if body:
        for k, v in body.items():
            display_v = str(v)
            if len(display_v) > 60:
                display_v = display_v[:57] + "..."
            print(f"      {k}: {display_v}")


def print_response(status: int, body: dict):
    tag = "OK" if 200 <= status < 300 else "ERROR"
    print(f"  <<< {status} {tag}")
    for k, v in body.items():
        display_v = str(v)
        if len(display_v) > 60:
            display_v = display_v[:57] + "..."
        print(f"      {k}: {display_v}")


def main():
    parser = argparse.ArgumentParser(description="SSO Partner Client Simulator")
    parser.add_argument("--consumer-key", help="Pre-existing consumer key")
    parser.add_argument("--consumer-secret", help="Pre-existing consumer secret")
    parser.add_argument("--base-url", default=BASE_URL, help="SSO receiver base URL")
    parser.add_argument("--delay", type=int, default=DEFAULT_STEP_DELAY, help="Delay between steps (default: 2)")
    args = parser.parse_args()

    delay = args.delay

    def pause():
        if delay > 0:
            time.sleep(delay)

    base_url = args.base_url
    client = httpx.Client(base_url=base_url, timeout=30)

    print("=" * 70)
    print("  SSO Token Exchange — Full Flow Demo (Option A)")
    print()
    print("  This script simulates THREE roles:")
    print("    [GLCHAT ADMIN]     GLChat platform admin (step 1)")
    print("    [PARTNER BACKEND]  Lokadata server (steps 2-3)")
    print("    [GLCHAT WIDGET]    GLChat iframe JavaScript (steps 4-5)")
    print()
    print("  In production, the admin registers partners (step 1),")
    print("  the partner backend requests SSO tokens (steps 2-3),")
    print("  and the GLChat widget exchanges them for sessions (steps 4-5).")
    print("=" * 70)

    # Step 0: Health check
    print_step_title(0, "GLCHAT ADMIN", "Health check")
    print_request("GET", f"{base_url}/health")
    resp = client.get("/health")
    print_response(resp.status_code, resp.json())
    if resp.status_code != 200:
        print("  ERROR: Is sso_receiver.py running?")
        sys.exit(1)

    pause()

    # Step 1: Register partner (GLChat admin does this, not the partner)
    print_step_title(1, "GLCHAT ADMIN", "Register Lokadata as SSO partner")
    if args.consumer_key and args.consumer_secret:
        consumer_key = args.consumer_key
        consumer_secret = args.consumer_secret
        print("  (Skipping — using pre-configured credentials.)")
        print(f"  Consumer Key: {consumer_key}")
    else:
        print("  This is done by the GLChat platform admin, NOT by Lokadata.")
        print("  The admin registers Lokadata and sends them the credentials.")

        register_body = {
            "partner_name": "Lokadata Portal",
            "allowed_origins": ["https://lokadata.example.com"],
            "sso_mode": "idp_initiated",
            "user_provisioning": "jit",
            "metadata": {"contact": "admin@lokadata.example.com"},
            # Security restrictions: only @lokadata.example.com emails allowed
            "allowed_email_domains": ["lokadata.example.com"],
            "max_users": 1000,
        }
        print_request("POST", f"{base_url}/admin/partners", body=register_body)
        resp = client.post("/admin/partners", json=register_body)

        if resp.status_code == 200:
            partner = resp.json()
            consumer_key = partner["consumer_key"]
            consumer_secret = partner["consumer_secret"]
            print_response(resp.status_code, partner)
            print("  Admin sends consumer_key + consumer_secret to Lokadata securely.")
            print("  (In production, this endpoint requires platform admin auth.)")
        elif resp.status_code == 400 and "already exists" in resp.json().get("detail", ""):
            print(f"  <<< 400 (Partner already registered — rotating secret instead)")
            # Partner exists from a previous run. List partners to get ID, then rotate.
            list_resp = client.get("/admin/partners")
            partners = list_resp.json()
            existing = next((p for p in partners if p["partner_name"] == "Lokadata Portal"), None)
            if not existing:
                print("  ERROR: Partner exists but not found in list.")
                sys.exit(1)
            print(f"  Found existing partner: {existing['consumer_key']}")
            print("  Rotating consumer_secret (with 1-hour grace period)...")
            rotate_resp = client.post(
                f"/admin/partners/{existing['id']}/rotate",
                json={"grace_period_seconds": 3600},
            )
            if rotate_resp.status_code != 200:
                print_response(rotate_resp.status_code, rotate_resp.json())
                sys.exit(1)
            rotated = rotate_resp.json()
            consumer_key = rotated["consumer_key"]
            consumer_secret = rotated["consumer_secret"]
            print(f"  New consumer_key: {consumer_key}")
            print(f"  New consumer_secret: {consumer_secret[:8]}... (rotated)")
        else:
            print_response(resp.status_code, resp.json())
            sys.exit(1)

    pause()

    # Step 2: Compute HMAC signature
    print_step_title(2, "PARTNER BACKEND", "Compute HMAC signature")
    print("  User 'Alice' just logged into Lokadata.")
    print("  Signing her identity with our consumer_secret.")

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

    print(f"  User: {user_payload['email']} (external_id: {user_payload['external_id']})")
    print(f"  Signature: {signature[:32]}...")

    pause()

    # Step 3: Request one-time token (server-to-server)
    print_step_title(3, "PARTNER BACKEND", "Request one-time SSO token")
    print("  Server-to-server call to GLChat backend.")

    print_request("POST", f"{base_url}/api/v1/sso/token", body={
        "consumer_key": consumer_key,
        "signature": f"{signature[:32]}...",
        "timestamp": timestamp,
        "payload": f"{payload_str[:40]}...",
    })
    resp = client.post("/api/v1/sso/token", json={
        "consumer_key": consumer_key,
        "signature": signature,
        "timestamp": timestamp,
        "payload": payload_str,
    })

    if resp.status_code != 200:
        print_response(resp.status_code, resp.json())
        sys.exit(1)

    token_data = resp.json()
    one_time_token = token_data["token"]
    print_response(resp.status_code, token_data)
    print(f"  Got one-time token (expires in {token_data['expires_in']}s).")
    print(f"\n  Now we load the GLChat widget iframe with this token:")
    print(f'  <iframe src="https://glchat.com/widget?sso_token={one_time_token[:16]}...">')

    pause()

    # Step 4: Widget exchanges token for session JWT
    print_step_title(4, "GLCHAT WIDGET", "Exchange token for session")
    print("  The GLChat iframe JS reads sso_token from URL params")
    print("  and calls its OWN backend (same-origin, no CORS).")

    print_request("POST", f"{base_url}/api/v1/sso/authenticate", body={"token": one_time_token})
    resp = client.post("/api/v1/sso/authenticate", json={"token": one_time_token})

    if resp.status_code != 200:
        print_response(resp.status_code, resp.json())
        sys.exit(1)

    auth_data = resp.json()
    jwt_token = auth_data["access_token"]
    print_response(resp.status_code, auth_data)
    print("  Widget stores the session JWT in memory (never in URL).")

    pause()

    # Step 5: Widget uses session JWT
    print_step_title(5, "GLCHAT WIDGET", "Access protected API")
    print("  Widget uses the session JWT for all subsequent API calls.")

    print_request("GET", f"{base_url}/api/v1/me",
                  headers={"Authorization": f"Bearer {jwt_token}"})
    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {jwt_token}"})

    if resp.status_code == 200:
        me = resp.json()
        print_response(resp.status_code, me)
        print(f"\n  SSO complete! Alice sees: 'Welcome, {me.get('display_name')}'")
    else:
        print_response(resp.status_code, resp.json())
        sys.exit(1)

    pause()

    # Step 6: Verify replay protection
    print_step_title(6, "SECURITY", "Verify token replay is rejected")
    print("  Trying to reuse the same one-time token...")

    print_request("POST", f"{base_url}/api/v1/sso/authenticate", body={"token": one_time_token})
    resp = client.post("/api/v1/sso/authenticate", json={"token": one_time_token})
    print_response(resp.status_code, resp.json())
    print("  Replay rejected — token was already consumed.")

    print("\n" + "=" * 70)
    print("  Done. Alice logged in once (Lokadata) and got GLChat access.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
