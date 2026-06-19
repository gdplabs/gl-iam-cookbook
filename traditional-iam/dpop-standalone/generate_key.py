"""
DPoP Key Helper - Generate and persist a client DPoP key pair.

This is identical to the dpop-keycloak example: the client owns an EC key pair.
The PRIVATE key never leaves the client; only the PUBLIC key (as a JWK
thumbprint) is bound into the access token by the issuer.

The same key is used to:
1. Bind the access token (issue_token.py reads keys/jwk.json)
2. Sign DPoP proofs for each request (create_proof.py)

Usage:
    python generate_key.py
"""

import json
import os

from cryptography.hazmat.primitives import serialization

from gl_iam.client.dpop import DPoPClient


def main():
    # Generate a new EC P-256 key pair (ES256)
    client = DPoPClient()

    keys_dir = "keys"
    os.makedirs(keys_dir, exist_ok=True)

    # Save private key (PEM). HACK: DPoPClient does not yet expose private-key
    # serialization or key loading; reach into the attribute for the demo.
    private_key_pem = client._private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(f"{keys_dir}/private_key.pem", "wb") as f:
        f.write(private_key_pem)

    # Save JWK (public key only)
    with open(f"{keys_dir}/jwk.json", "w") as f:
        json.dump(client.jwk, f, indent=2)

    print("=" * 60)
    print("DPoP client key generated (no Keycloak involved)")
    print("=" * 60)
    print(f"\nJWK Thumbprint (cnf.jkt): {client.jwk_thumbprint}")
    print("\nFiles saved:")
    print(f"  - {keys_dir}/private_key.pem   (keep secret — never send this)")
    print(f"  - {keys_dir}/jwk.json          (public — bound into the token)")
    print("\nUse the SAME key for issue_token.py and create_proof.py.")
    print("=" * 60)


if __name__ == "__main__":
    main()
