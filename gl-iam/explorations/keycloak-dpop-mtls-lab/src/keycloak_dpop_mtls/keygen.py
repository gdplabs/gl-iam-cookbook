from __future__ import annotations

import json
from pathlib import Path

from .dpop import generate_ec_key, jwk_from_public_key, save_private_pem


def generate_and_save(private_key_path: str, public_jwk_path: str) -> None:
    private_key = generate_ec_key()
    save_private_pem(private_key, private_key_path)
    jwk = jwk_from_public_key(private_key.public_key())
    Path(public_jwk_path).write_text(json.dumps(jwk, indent=2))

