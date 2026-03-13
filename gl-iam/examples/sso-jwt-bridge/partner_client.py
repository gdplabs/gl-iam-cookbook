"""SSO JWT Bridge partner client — simulates the full SSO flow.

This script plays TWO roles (since there's no real browser/iframe):
  - [PARTNER BACKEND] Lokadata's server: signs a JWT with the shared secret
  - [GLCHAT WIDGET]   GLChat's iframe JS: sends JWT to backend, uses session

In production, these are separate systems:
  Lokadata backend  → embeds JWT in iframe URL → GLChat widget page
  GLChat widget JS  → same-origin POST        → GLChat backend (exchange)

Usage:
    uv run partner_client.py
    uv run partner_client.py --secret "my-shared-secret-min-32-chars-long!!"
    uv run partner_client.py --delay 0
"""

import argparse
import json
import sys
import time

import httpx
import jwt as pyjwt

BASE_URL = "http://localhost:8000"
DEFAULT_STEP_DELAY = 2

# ANSI colors for step titles
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Color per role
ROLE_COLORS = {
    "PARTNER BACKEND": YELLOW,
    "GLCHAT WIDGET": GREEN,
}


def print_step_title(step: int, role: str, title: str):
    color = ROLE_COLORS.get(role, CYAN)
    print(f"\n{color}{BOLD}── Step {step} [{role}]: {title} ──{RESET}")


DEFAULT_SHARED_SECRET = "shared-secret-between-partner-and-glchat-min-32-chars"
DEFAULT_ISSUER = "partner-portal"


def print_request(method: str, url: str, body: dict | None = None, headers: dict | None = None):
    print(f"\n  >>> {method} {url}")
    if headers:
        for k, v in headers.items():
            print(f"      {k}: {v[:60]}{'...' if len(v) > 60 else ''}")
    if body:
        print(f"      Body: {json.dumps(body, indent=None)}")


def print_response(status: int, body: dict):
    tag = "OK" if 200 <= status < 300 else "ERROR"
    print(f"  <<< {status} {tag}")
    for k, v in body.items():
        display_v = str(v)
        if len(display_v) > 60:
            display_v = display_v[:57] + "..."
        print(f"      {k}: {display_v}")


def main():
    parser = argparse.ArgumentParser(description="SSO JWT Bridge Partner Client")
    parser.add_argument("--secret", default=DEFAULT_SHARED_SECRET, help="Shared secret")
    parser.add_argument("--issuer", default=DEFAULT_ISSUER, help="JWT issuer")
    parser.add_argument("--base-url", default=BASE_URL, help="SSO receiver base URL")
    parser.add_argument("--delay", type=int, default=DEFAULT_STEP_DELAY, help="Delay between steps (default: 2)")
    args = parser.parse_args()

    delay = args.delay

    def pause():
        if delay > 0:
            time.sleep(delay)

    client = httpx.Client(base_url=args.base_url, timeout=30)

    print("=" * 70)
    print("  SSO JWT Bridge — Full Flow Demo (Option B)")
    print()
    print("  This script simulates TWO roles:")
    print("    [PARTNER BACKEND]  Lokadata server (step 1)")
    print("    [GLCHAT WIDGET]    GLChat iframe JavaScript (steps 2-3)")
    print()
    print("  In production, the partner backend embeds the signed JWT in")
    print("  the iframe URL. The GLChat widget (same-origin JS) then")
    print("  exchanges it for a session JWT — no CORS needed.")
    print("=" * 70)

    # Step 0: Health check
    print_step_title(0, "PARTNER BACKEND", "Health check")
    print_request("GET", f"{args.base_url}/health")
    resp = client.get("/health")
    print_response(resp.status_code, resp.json())
    if resp.status_code != 200:
        print("  ERROR: Is sso_receiver.py running?")
        sys.exit(1)

    pause()

    # Step 1: Partner signs JWT
    print_step_title(1, "PARTNER BACKEND", "Sign JWT with shared secret")
    print("  User 'Bob' just logged into Lokadata.")
    print("  Signing a short-lived JWT containing his identity.")

    now = int(time.time())
    claims = {
        "iss": args.issuer,
        "sub": "lok-user-002",
        "email": "bob@lokadata.example.com",
        "display_name": "Bob from Lokadata",
        "first_name": "Bob",
        "last_name": "Johnson",
        "iat": now,
        "exp": now + 60,
    }
    partner_jwt = pyjwt.encode(claims, args.secret, algorithm="HS256")

    print(f"  Claims: sub={claims['sub']}, email={claims['email']}, exp=60s")
    print(f"  JWT: {partner_jwt[:50]}...")
    print(f"\n  Now we load the GLChat widget iframe with this JWT:")
    print(f'  <iframe src="https://glchat.com/widget?auth_token={partner_jwt[:30]}...">')

    pause()

    # Step 2: Widget exchanges JWT for session
    print_step_title(2, "GLCHAT WIDGET", "Exchange JWT for session")
    print("  The GLChat iframe JS reads auth_token from URL params")
    print("  and calls its OWN backend (same-origin, no CORS).")

    print_request("POST", f"{args.base_url}/api/v1/sso/jwt-authenticate",
                  body={"partner_jwt": f"{partner_jwt[:40]}..."})
    resp = client.post("/api/v1/sso/jwt-authenticate", json={"partner_jwt": partner_jwt})

    if resp.status_code != 200:
        print_response(resp.status_code, resp.json())
        sys.exit(1)

    auth_data = resp.json()
    session_jwt = auth_data["access_token"]
    print_response(resp.status_code, auth_data)
    print("  Widget stores the session JWT in memory (never in URL).")

    pause()

    # Step 3: Widget uses session JWT
    print_step_title(3, "GLCHAT WIDGET", "Access protected API")
    print("  Widget uses the session JWT for all subsequent API calls.")

    print_request("GET", f"{args.base_url}/api/v1/me",
                  headers={"Authorization": f"Bearer {session_jwt}"})
    resp = client.get("/api/v1/me", headers={"Authorization": f"Bearer {session_jwt}"})

    if resp.status_code == 200:
        me = resp.json()
        print_response(resp.status_code, me)
        print(f"\n  SSO complete! Bob sees: 'Welcome, {me.get('display_name')}'")
    else:
        print_response(resp.status_code, resp.json())
        sys.exit(1)

    print("\n" + "=" * 70)
    print("  Done. Bob logged in once (Lokadata) and got GLChat access.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
