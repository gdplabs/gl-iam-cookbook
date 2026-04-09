"""
DPoP Proof Generator - Create DPoP proofs using saved key.

This script loads the persisted key from files and creates DPoP proofs
using the GL-IAM DPoPClient.

Usage:
    python create_proof.py <http_method> <url> [access_token]

Examples:
    # Proof for token request (no access_token):
    python create_proof.py POST "http://localhost:8080/realms/dpop-demo/protocol/openid-connect/token"

    # Proof for resource access (with access_token for ath claim):
    python create_proof.py GET "http://localhost:8000/api/protected" "eyJ..."
"""

import sys
import json

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
        print(
            "Please run generate_key.py to generate the key files before running create_proof.py."
        )
        sys.exit(1)

    # Recreate client from loaded key
    # HACK: DPoPClient doesn't support loading existing keys yet.
    # Verify compatibility when upgrading gl-iam.
    client = DPoPClient()
    client._private_key = private_key
    client.jwk = jwk
    return client


def main():
    if len(sys.argv) < 3:
        print("Usage: python create_proof.py <http_method> <url> [access_token]")
        print("\nExamples:")
        print(
            '  python create_proof.py POST "http://localhost:8080/realms/dpop-demo/protocol/openid-connect/token"'
        )
        print(
            '  python create_proof.py GET "http://localhost:8000/api/protected" "eyJ..."'
        )
        sys.exit(1)

    http_method = sys.argv[1]
    http_url = sys.argv[2]
    access_token = sys.argv[3] if len(sys.argv) > 3 else None

    client = load_client()
    proof = client.create_proof(http_method, http_url, access_token)
    print(proof)


if __name__ == "__main__":
    main()
