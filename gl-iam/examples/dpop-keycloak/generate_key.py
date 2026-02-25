"""
DPoP Key Helper - Generate and persist a DPoP key pair.

This script generates an EC key pair and saves it to files for reuse.
The same key is used for both:
1. Requesting a DPoP-bound token from Keycloak
2. Creating DPoP proofs to access protected resources

Usage:
    python generate_key.py
"""

import json
import os

from gl_iam.client.dpop import DPoPClient


def main():
    client = DPoPClient()

    keys_dir = "keys"
    os.makedirs(keys_dir, exist_ok=True)

    private_key_pem = client._private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    with open(f"{keys_dir}/private_key.pem", "wb") as f:
        f.write(private_key_pem)

    with open(f"{keys_dir}/jwk.json", "w") as f:
        json.dump(client.jwk, f, indent=2)

    print("=" * 50)
    print("DPoP Key Generated")
    print("=" * 50)
    print(f"\nJWK Thumbprint: {client.jwk_thumbprint}")
    print(f"\nFiles saved:")
    print(f"  - {keys_dir}/private_key.pem")
    print(f"  - {keys_dir}/jwk.json")
    print("\nIMPORTANT: Use the SAME key for both:")
    print("  1. Requesting DPoP-bound token from Keycloak")
    print("  2. Creating DPoP proofs for protected resources")
    print("=" * 50)


if __name__ == "__main__":
    from cryptography.hazmat.primitives import serialization

    main()
