"""
mTLS (Mutual TLS) Client Implementation
=======================================

This module implements OAuth 2.0 Mutual-TLS Client Authentication and
Certificate-Bound Access Tokens as specified in RFC 8705.
https://datatracker.ietf.org/doc/html/rfc8705

mTLS provides two security mechanisms:
1. Client Authentication: The client authenticates to the AS using a certificate
2. Token Binding: Access tokens can be bound to the client's certificate

Key Concepts (RFC 8705):
- PKI mTLS: Client cert is validated against a CA known to the server
- Self-Signed mTLS: Client cert is pre-registered with the AS
- cnf.x5t#S256: Certificate thumbprint in the token for binding

When to use mTLS:
- Backend services / machine-to-machine communication
- High-security environments where certificate management is feasible
- When you need channel-level security in addition to token security

Comparison with DPoP:
- mTLS: Transport-level binding, requires certificate infrastructure
- DPoP: Application-level binding, works with any client type
- Both can be combined for defense-in-depth
"""

from __future__ import annotations

import ssl
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from cryptography.hazmat.primitives.asymmetric import ec

from .dpop import build_dpop_proof


def _create_ssl_context(
    cert: Optional[str] = None,
    key: Optional[str] = None,
    ca: Optional[str] = None,
) -> Any:
    """
    Create an SSL context for mTLS connections.
    
    httpx works best with a properly configured SSL context that has the
    client certificate loaded via load_cert_chain(). This ensures the
    client certificate is sent during the TLS handshake.
    
    Args:
        cert: Path to client certificate PEM
        key: Path to client private key PEM
        ca: Path to CA certificate for server verification
    
    Returns:
        Configured SSL context, or True for default verification
    """
    if not cert or not key:
        # No client cert - use CA verification only or default
        if ca:
            ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ctx.load_verify_locations(str(Path(ca).resolve()))
            return ctx
        return True
    
    # Create SSL context with client certificate for mTLS
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    
    # Load CA for server verification
    if ca:
        ctx.load_verify_locations(str(Path(ca).resolve()))
    
    # Load client certificate and key for mTLS authentication
    # This is the key step that ensures the cert is sent during handshake
    ctx.load_cert_chain(
        certfile=str(Path(cert).resolve()),
        keyfile=str(Path(key).resolve())
    )
    
    return ctx


def request_token_mtls(
    token_url: str,
    client_id: str,
    *,
    client_secret: Optional[str] = None,
    scope: Optional[str] = None,
    cert: Optional[str] = None,
    key: Optional[str] = None,
    ca: Optional[str] = None,
    dpop_private_key: Optional[ec.EllipticCurvePrivateKey] = None,
    dpop_nonce: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Request an access token from the authorization server.
    
    This function supports multiple authentication modes:
    
    1. Client Secret Only (standard OAuth):
       - Uses client_id and client_secret
       - Token is a standard Bearer token
    
    2. mTLS Only (RFC 8705 Section 2):
       - Client authenticates via TLS client certificate
       - The AS validates the cert and may bind the token to it
       - Token may have cnf.x5t#S256 claim for certificate binding
    
    3. DPoP Only (RFC 9449):
       - Sends DPoP header with proof JWT
       - Token is bound via cnf.jkt claim
    
    4. mTLS + DPoP (Combined):
       - Both mechanisms active for defense-in-depth
       - Token bound to both certificate and DPoP key
    
    RFC 8705 Section 2 requires:
    - The TLS connection MUST use mutual TLS with client cert
    - The client_id parameter MUST be included (for AS to lookup client)
    - The AS validates the certificate against expected credentials
    
    Args:
        token_url: The token endpoint URL
        client_id: The OAuth client identifier (required per RFC 8705)
        client_secret: Optional client secret
        scope: Optional scope string
        cert: Path to client certificate PEM file (for mTLS)
        key: Path to client private key PEM file (for mTLS)
        ca: Path to CA certificate for server verification
        dpop_private_key: EC private key for DPoP proofs
        dpop_nonce: Server-provided nonce for DPoP
    
    Returns:
        The token response as a dictionary
    """
    # OAuth 2.0 client credentials grant
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,  # Required per RFC 8705 Section 2
    }
    if client_secret:
        data["client_secret"] = client_secret
    if scope:
        data["scope"] = scope

    # Build headers (add DPoP proof if requested)
    headers: Dict[str, str] = {}
    if dpop_private_key:
        # RFC 9449 Section 5: Send DPoP proof to token endpoint
        headers["DPoP"] = build_dpop_proof(
            dpop_private_key, token_url, "POST", nonce=dpop_nonce
        )

    # Create SSL context for mTLS (RFC 8705 Section 2)
    ssl_context = _create_ssl_context(cert, key, ca)
    
    with httpx.Client(verify=ssl_context) as client:
        response = client.post(token_url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()


def call_resource(
    url: str,
    access_token: str,
    dpop_private_key: ec.EllipticCurvePrivateKey,
    *,
    method: str = "GET",
    cert: Optional[str] = None,
    key: Optional[str] = None,
    ca: Optional[str] = None,
) -> httpx.Response:
    """
    Call a protected resource with DPoP-bound access token.
    
    RFC 9449 Section 7 specifies how to use DPoP with resource servers:
    
    1. Authorization header uses "DPoP" scheme (not "Bearer"):
       Authorization: DPoP <access_token>
    
    2. DPoP header contains a fresh proof with:
       - htu: The resource URL
       - htm: The HTTP method
       - ath: Hash of the access token (binds proof to specific token)
    
    RFC 8705 Section 3 (mTLS token binding):
    - If the token was bound to a certificate (cnf.x5t#S256)
    - The resource server MUST verify the same cert is used
    - If certs don't match, return 401 with invalid_token error
    
    Args:
        url: The protected resource URL
        access_token: The DPoP-bound access token
        dpop_private_key: The same key used to obtain the token
        method: HTTP method (GET, POST, etc.)
        cert: Client certificate for mTLS (if token is cert-bound)
        key: Client private key for mTLS
        ca: CA certificate for server verification
    
    Returns:
        The HTTP response from the resource server
    """
    # RFC 9449 Section 7.1: Use DPoP authentication scheme
    # Note: "DPoP" not "Bearer" - this indicates token is DPoP-bound
    headers = {
        "Authorization": f"DPoP {access_token}",
        # Fresh DPoP proof with ath (access token hash)
        "DPoP": build_dpop_proof(
            dpop_private_key, url, method, access_token=access_token
        ),
    }

    # Create SSL context for mTLS
    ssl_context = _create_ssl_context(cert, key, ca)
    
    with httpx.Client(verify=ssl_context) as client:
        response = client.request(method.upper(), url, headers=headers)
        response.raise_for_status()
        return response
