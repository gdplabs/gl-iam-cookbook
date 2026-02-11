"""
DPoP (Demonstrating Proof-of-Possession) Implementation
========================================================

This module implements OAuth 2.0 DPoP as specified in RFC 9449.
https://datatracker.ietf.org/doc/html/rfc9449

DPoP provides a mechanism for sender-constraining OAuth tokens by proving
possession of a private key. Unlike Bearer tokens which can be used by anyone
who obtains them, DPoP-bound tokens require the presenter to prove they hold
the private key that was used when the token was issued.

Key Concepts:
- DPoP Proof: A signed JWT that proves possession of a key pair
- cnf.jkt: Confirmation claim in the access token containing the JWK thumbprint
- ath: Access Token Hash - used when calling resource servers

Security Benefits:
- Prevents token theft/replay: An attacker who steals a token cannot use it
  without also having the private key
- Per-request proof: Each request includes a fresh proof with unique jti
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from typing import Any, Dict, Optional

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)


def _b64url(data: bytes) -> str:
    """
    Base64url encode without padding, as required by RFC 7515 (JWS).
    
    RFC 9449 Section 4.2 requires base64url encoding for various fields
    including the JWK thumbprint and access token hash.
    """
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def generate_ec_key() -> ec.EllipticCurvePrivateKey:
    """
    Generate a new EC P-256 key pair for DPoP.
    
    RFC 9449 Section 4.2 requires asymmetric keys. EC P-256 (SECP256R1)
    is commonly used with the ES256 algorithm.
    """
    return ec.generate_private_key(ec.SECP256R1())


def save_private_pem(private_key: ec.EllipticCurvePrivateKey, path: str) -> None:
    """Save the private key in PEM format (PKCS#8)."""
    pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    with open(path, "wb") as f:
        f.write(pem)


def load_private_pem(path: str) -> ec.EllipticCurvePrivateKey:
    """Load an EC private key from a PEM file."""
    with open(path, "rb") as f:
        data = f.read()
    key = load_pem_private_key(data, password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise TypeError("Expected EC private key")
    return key


def jwk_from_public_key(public_key: ec.EllipticCurvePublicKey) -> Dict[str, str]:
    """
    Convert an EC public key to JWK format.
    
    RFC 9449 Section 4.2 requires the DPoP proof header to include the
    public key as a JWK. For EC P-256 keys, this includes:
    - kty: "EC" (key type)
    - crv: "P-256" (curve)
    - x: x-coordinate (base64url encoded)
    - y: y-coordinate (base64url encoded)
    """
    numbers = public_key.public_numbers()
    # EC P-256 coordinates are 32 bytes each
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    return {
        "kty": "EC",
        "crv": "P-256",
        "x": _b64url(x),
        "y": _b64url(y),
    }


def jwk_thumbprint(jwk: Dict[str, str]) -> str:
    """
    Calculate the JWK Thumbprint as per RFC 7638.
    
    RFC 9449 Section 6.1 specifies that the authorization server binds the
    access token to the DPoP key by including a "cnf" (confirmation) claim
    with a "jkt" (JWK Thumbprint) member.
    
    The thumbprint is computed as:
    1. Create a JSON object with required members in lexicographic order
    2. Hash with SHA-256
    3. Base64url encode the hash
    
    For EC keys, the required members are: crv, kty, x, y
    """
    if jwk.get("kty") != "EC":
        raise ValueError("Only EC P-256 keys are supported in this lab")
    # RFC 7638: Members MUST be in lexicographic order
    ordered = {
        "crv": jwk["crv"],
        "kty": jwk["kty"],
        "x": jwk["x"],
        "y": jwk["y"],
    }
    payload = json.dumps(ordered, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _b64url(hashlib.sha256(payload).digest())


def ath_hash(access_token: str) -> str:
    """
    Calculate the Access Token Hash (ath) for resource server calls.
    
    RFC 9449 Section 4.2 specifies that when calling a protected resource,
    the DPoP proof MUST include an "ath" claim containing the base64url
    encoding of the SHA-256 hash of the access token.
    
    This binds the DPoP proof to the specific access token being used.
    """
    return _b64url(hashlib.sha256(access_token.encode("ascii")).digest())


def build_dpop_proof(
    private_key: ec.EllipticCurvePrivateKey,
    htu: str,
    htm: str,
    *,
    access_token: Optional[str] = None,
    nonce: Optional[str] = None,
) -> str:
    """
    Build a DPoP proof JWT as specified in RFC 9449 Section 4.2.
    
    The DPoP proof is a JWT with the following structure:
    
    HEADER (RFC 9449 Section 4.2):
    - typ: MUST be "dpop+jwt"
    - alg: The signing algorithm (ES256 for EC P-256 keys)
    - jwk: The public key as a JWK
    
    PAYLOAD (RFC 9449 Section 4.2):
    - jti: Unique identifier to prevent replay attacks
    - htm: HTTP method of the request (e.g., "POST", "GET")
    - htu: HTTP URI of the request (the token endpoint or resource URL)
    - iat: Issued at timestamp
    - ath: Access token hash (required when calling resource servers)
    - nonce: Server-provided nonce (if required by AS/RS)
    
    Args:
        private_key: The EC private key for signing
        htu: HTTP Target URI (the URL being called)
        htm: HTTP Method (GET, POST, etc.)
        access_token: The access token (required for resource server calls)
        nonce: Server-provided nonce from DPoP-Nonce header
    
    Returns:
        The signed DPoP proof JWT
    """
    now = int(time.time())
    
    # Build the payload with required claims
    claims: Dict[str, Any] = {
        "htu": htu,                    # HTTP URI
        "htm": htm.upper(),            # HTTP Method (uppercase)
        "iat": now,                    # Issued At
        "jti": str(uuid.uuid4()),      # Unique ID (prevents replay)
    }
    
    # Add ath claim for resource server calls (RFC 9449 Section 7)
    if access_token:
        claims["ath"] = ath_hash(access_token)
    
    # Add nonce if server requires it (RFC 9449 Section 8)
    if nonce:
        claims["nonce"] = nonce

    # Build the header with public key as JWK
    public_jwk = jwk_from_public_key(private_key.public_key())
    headers = {
        "typ": "dpop+jwt",    # Required by RFC 9449
        "alg": "ES256",       # Algorithm for EC P-256
        "jwk": public_jwk,    # Public key for verification
    }
    
    return jwt.encode(claims, private_key, algorithm="ES256", headers=headers)
