"""Integration smoke test for the local Keycloak DPoP and mTLS lab."""

from __future__ import annotations

import base64

import httpx
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes

from keycloak_dpop_mtls.dpop import (
    build_dpop_proof,
    generate_ec_key,
    jwk_from_public_key,
    jwk_thumbprint,
)
from keycloak_dpop_mtls.mtls_client import _create_ssl_context, request_token_mtls


TOKEN_URL = "https://localhost:8443/realms/dpop-lab/protocol/openid-connect/token"
USERINFO_URL = (
    "https://localhost:8443/realms/dpop-lab/protocol/openid-connect/userinfo"
)
CA = "certs/ca.crt"
CERT = "certs/client.crt"
KEY = "certs/client.key"


def _claims(token_response: dict[str, object]) -> dict[str, object]:
    return jwt.decode(
        str(token_response["access_token"]),
        options={"verify_signature": False, "verify_aud": False},
    )


def _certificate_thumbprint() -> str:
    with open(CERT, "rb") as certificate_file:
        certificate = x509.load_pem_x509_certificate(certificate_file.read())
    digest = certificate.fingerprint(hashes.SHA256())
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def main() -> None:
    dpop_key = generate_ec_key()
    expected_jkt = jwk_thumbprint(jwk_from_public_key(dpop_key.public_key()))
    expected_x5t = _certificate_thumbprint()

    baseline = request_token_mtls(
        TOKEN_URL, "lab-client", client_secret="lab-secret", ca=CA
    )
    dpop = request_token_mtls(
        TOKEN_URL,
        "dpop-client",
        client_secret="dpop-secret",
        scope="openid profile",
        ca=CA,
        dpop_private_key=dpop_key,
    )
    mtls = request_token_mtls(
        TOKEN_URL,
        "mtls-client",
        client_secret="mtls-secret",
        scope="openid profile",
        cert=CERT,
        key=KEY,
        ca=CA,
    )
    combined = request_token_mtls(
        TOKEN_URL,
        "combined-client",
        scope="openid profile",
        cert=CERT,
        key=KEY,
        ca=CA,
        dpop_private_key=dpop_key,
    )

    assert baseline["token_type"].lower() == "bearer"
    assert _claims(baseline).get("cnf") is None
    assert dpop["token_type"].lower() == "dpop"
    assert _claims(dpop)["cnf"]["jkt"] == expected_jkt
    assert mtls["token_type"].lower() == "bearer"
    assert _claims(mtls)["cnf"] == {"x5t#S256": expected_x5t}
    assert combined["token_type"].lower() == "dpop"
    assert _claims(combined)["cnf"]["jkt"] == expected_jkt

    plain = httpx.Client(verify=_create_ssl_context(ca=CA))
    certificate_client = httpx.Client(
        verify=_create_ssl_context(cert=CERT, key=KEY, ca=CA)
    )
    try:
        grant = {"grant_type": "client_credentials"}
        missing_dpop = plain.post(
            TOKEN_URL,
            data={
                **grant,
                "client_id": "dpop-client",
                "client_secret": "dpop-secret",
            },
        )
        missing_mtls = plain.post(
            TOKEN_URL,
            data={
                **grant,
                "client_id": "mtls-client",
                "client_secret": "mtls-secret",
            },
        )
        combined_without_cert = plain.post(
            TOKEN_URL,
            data={**grant, "client_id": "combined-client"},
            headers={"DPoP": build_dpop_proof(dpop_key, TOKEN_URL, "POST")},
        )
        combined_without_dpop = certificate_client.post(
            TOKEN_URL,
            data={**grant, "client_id": "combined-client"},
        )

        dpop_access_token = str(dpop["access_token"])
        valid_dpop = plain.get(
            USERINFO_URL,
            headers={
                "Authorization": f"DPoP {dpop_access_token}",
                "DPoP": build_dpop_proof(
                    dpop_key,
                    USERINFO_URL,
                    "GET",
                    access_token=dpop_access_token,
                ),
            },
        )
        missing_dpop_at_resource = plain.get(
            USERINFO_URL,
            headers={"Authorization": f"DPoP {dpop_access_token}"},
        )
        wrong_dpop_at_resource = plain.get(
            USERINFO_URL,
            headers={
                "Authorization": f"DPoP {dpop_access_token}",
                "DPoP": build_dpop_proof(
                    generate_ec_key(),
                    USERINFO_URL,
                    "GET",
                    access_token=dpop_access_token,
                ),
            },
        )

        mtls_access_token = str(mtls["access_token"])
        valid_mtls = certificate_client.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {mtls_access_token}"},
        )
        missing_mtls_at_resource = plain.get(
            USERINFO_URL,
            headers={"Authorization": f"Bearer {mtls_access_token}"},
        )
    finally:
        plain.close()
        certificate_client.close()

    assert missing_dpop.status_code == 400
    assert missing_mtls.status_code == 400
    assert combined_without_cert.status_code == 401
    assert combined_without_dpop.status_code == 400
    assert valid_dpop.status_code == 200
    assert missing_dpop_at_resource.status_code == 401
    assert wrong_dpop_at_resource.status_code == 401
    assert valid_mtls.status_code == 200
    assert missing_mtls_at_resource.status_code == 401

    print("PASS: token bindings and negative enforcement checks succeeded")


if __name__ == "__main__":
    main()
