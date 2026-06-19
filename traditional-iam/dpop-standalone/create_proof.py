"""
DPoP Proof Generator - Create DPoP proofs using the saved client key.

Identical in spirit to the dpop-keycloak example, but the proof is validated
by GL-IAM's StandaloneDPoPProvider (no Keycloak introspection).

Usage:
    python create_proof.py <http_method> <url> [access_token]

Examples:
    # Proof bound to the access token (ath claim) for a resource request:
    python create_proof.py GET "http://localhost:8000/api/protected" "eyJ..."
"""

import json
import sys

from cryptography.hazmat.primitives import serialization

from gl_iam.client.dpop import DPoPClient


def load_client():
    """Load a DPoPClient from persisted key files."""
    try:
        with open("keys/private_key.pem", "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open("keys/jwk.json", "r") as f:
            jwk = json.load(f)
    except FileNotFoundError as e:
        print("Error: Required key file(s) not found.")
        if e.filename:
            print(f"Missing file: {e.filename}")
        print("Run generate_key.py first.")
        sys.exit(1)

    # HACK: DPoPClient doesn't support loading existing keys yet.
    client = DPoPClient()
    client._private_key = private_key
    client.jwk = jwk
    return client


def main():
    if len(sys.argv) < 3:
        print("Usage: python create_proof.py <http_method> <url> [access_token]")
        print('Example: python create_proof.py GET "http://localhost:8000/api/protected" "eyJ..."')
        sys.exit(1)

    http_method = sys.argv[1]
    http_url = sys.argv[2]
    access_token = sys.argv[3] if len(sys.argv) > 3 else None

    client = load_client()
    proof = client.create_proof(http_method, http_url, access_token)
    print(proof)


if __name__ == "__main__":
    main()
