"""Register the Trusted Partner with the GLChat BE and write credentials to .env.

This script demonstrates the admin flow:
  1. POST /login  → platform admin JWT
  2. POST /admin/partners  → consumer_key + consumer_secret (shown once)
  3. Write both into `.env` so partner_backend/main.py can use them.

Re-running is safe: if a partner with the same name exists, this script
just writes existing credentials if available (otherwise prints a hint).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

from glchat_backend.config import get_settings  # noqa: E402


GLCHAT_BE = os.environ.get("GLCHAT_BACKEND_URL", "http://localhost:8000")
PARTNER_NAME = "Trusted Partner"
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _update_env(consumer_key: str, consumer_secret: str) -> None:
    text = ENV_FILE.read_text()
    text = re.sub(r"^PARTNER_CONSUMER_KEY=.*$", f"PARTNER_CONSUMER_KEY={consumer_key}", text, flags=re.M)
    text = re.sub(r"^PARTNER_CONSUMER_SECRET=.*$", f"PARTNER_CONSUMER_SECRET={consumer_secret}", text, flags=re.M)
    ENV_FILE.write_text(text)
    print(f"Wrote PARTNER_CONSUMER_KEY/SECRET to {ENV_FILE}")


def main():
    settings = get_settings()
    with httpx.Client(base_url=GLCHAT_BE, timeout=15.0) as client:
        r = client.post("/login", json={
            "email": settings.bootstrap_admin_email,
            "password": settings.bootstrap_admin_password,
        })
        r.raise_for_status()
        token = r.json()["access_token"]
        auth = {"Authorization": f"Bearer {token}"}

        r = client.get("/admin/partners", headers=auth)
        r.raise_for_status()
        existing = [p for p in r.json() if p["partner_name"] == PARTNER_NAME]
        if existing:
            print(
                f"Partner '{PARTNER_NAME}' already exists (consumer_key={existing[0]['consumer_key']}).\n"
                "The secret is only shown at creation time. If you need a new one, rotate via the admin UI.",
                file=sys.stderr,
            )
            if not os.environ.get("PARTNER_CONSUMER_KEY"):
                print("Set PARTNER_CONSUMER_KEY/SECRET in .env manually, or delete DB + rerun `make up bootstrap`.")
            return

        r = client.post("/admin/partners", headers=auth, json={
            "partner_name": PARTNER_NAME,
            "allowed_origins": [settings.partner_site_origin],
            "allowed_email_domains": ["trusted-partner.example.com"],
            "allowed_source_ips": None,
            "max_users": 10,
            "allowed_roles": ["member"],
        })
        r.raise_for_status()
        data = r.json()
        print(f"Partner created: {data['consumer_key']}")
        _update_env(data["consumer_key"], data["consumer_secret"])


if __name__ == "__main__":
    main()
