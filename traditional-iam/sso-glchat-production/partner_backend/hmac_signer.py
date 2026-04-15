"""HMAC-SHA256 signer for outbound SSO token requests.

Signs `{timestamp}|{consumer_key}|{payload}` where `payload` JSON already
includes a cryptographic `nonce` — giving the receiver replay-protection
even inside the timestamp-tolerance window.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone


def sign_user_assertion(
    consumer_key: str,
    consumer_secret: str,
    user: dict,
) -> dict:
    nonce = secrets.token_urlsafe(32)
    timestamp = datetime.now(timezone.utc).isoformat()

    payload = json.dumps({**user, "nonce": nonce}, separators=(",", ":"))
    message = f"{timestamp}|{consumer_key}|{payload}"
    signature = hmac.new(consumer_secret.encode(), message.encode(), hashlib.sha256).hexdigest()

    return {
        "consumer_key": consumer_key,
        "signature": signature,
        "timestamp": timestamp,
        "nonce": nonce,
        "payload": payload,
    }
