#!/usr/bin/env python3
"""Get Stack Auth access token for testing.

This script authenticates with Stack Auth using email/password and prints
the access token for use with curl commands.

Usage:
    uv run get_token.py
    uv run get_token.py --email user@example.com --password secret
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()


def get_token(email: str, password: str) -> dict | None:
    """Authenticate with Stack Auth and get access token.

    Args:
        email: User's email address.
        password: User's password.

    Returns:
        dict with access_token and refresh_token, or None on failure.
    """
    base_url = os.getenv("STACKAUTH_BASE_URL", "http://localhost:8102").rstrip("/")
    project_id = os.getenv("STACKAUTH_PROJECT_ID", "internal")
    publishable_key = os.getenv(
        "STACKAUTH_PUBLISHABLE_CLIENT_KEY",
        "this-publishable-client-key-is-for-local-development-only",
    )

    url = f"{base_url}/api/v1/auth/password/sign-in"
    headers = {
        "Content-Type": "application/json",
        "X-Stack-Access-Type": "client",
        "X-Stack-Project-Id": project_id,
        "X-Stack-Publishable-Client-Key": publishable_key,
    }
    data = {"email": email, "password": password}

    try:
        response = httpx.post(url, json=data, headers=headers, timeout=30)

        if response.status_code == 200:
            return response.json()

        print(f"Error: {response.status_code}", file=sys.stderr)
        print(response.text, file=sys.stderr)
        return None

    except httpx.RequestError as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return None


def main():
    parser = argparse.ArgumentParser(description="Get Stack Auth access token")
    parser.add_argument("--email", "-e", help="Email address")
    parser.add_argument("--password", "-p", help="Password")
    args = parser.parse_args()

    # Get credentials from args or prompt
    email = args.email or os.getenv("TEST_USER_EMAIL")
    password = args.password or os.getenv("TEST_USER_PASSWORD")

    if not email:
        email = input("Email: ")
    if not password:
        import getpass

        password = getpass.getpass("Password: ")

    print(f"\nAuthenticating {email}...", file=sys.stderr)

    result = get_token(email, password)
    if result:
        access_token = result.get("access_token")
        print("\n" + "=" * 60, file=sys.stderr)
        print("ACCESS TOKEN (copy this for curl commands):", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        print(access_token)
        print("=" * 60, file=sys.stderr)
        print("\nUsage:", file=sys.stderr)
        print(f'  export TOKEN="{access_token}"', file=sys.stderr)
        print('  curl http://localhost:8000/api/drf/me/ -H "Authorization: Bearer $TOKEN"', file=sys.stderr)
    else:
        print("\nFailed to get token", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
