import jwt

from keycloak_dpop_mtls.dpop import ath_hash, build_dpop_proof, generate_ec_key


def test_dpop_proof_roundtrip():
    key = generate_ec_key()
    proof = build_dpop_proof(key, "https://example.com/token", "POST")
    headers = jwt.get_unverified_header(proof)
    assert headers["typ"] == "dpop+jwt"
    assert headers["alg"] == "ES256"
    assert "jwk" in headers

    claims = jwt.decode(
        proof,
        key.public_key(),
        algorithms=["ES256"],
        options={"verify_aud": False},
    )
    assert claims["htu"] == "https://example.com/token"
    assert claims["htm"] == "POST"
    assert "jti" in claims
    assert "iat" in claims


def test_ath_hash():
    assert ath_hash("abc") == "ungWv48Bz-pBQUDeXa4iI7ADYaOWF3qctBD_YfIAFa0"


def test_ath_included_in_proof():
    key = generate_ec_key()
    proof = build_dpop_proof(
        key, "https://example.com/resource", "GET", access_token="abc"
    )
    claims = jwt.decode(
        proof,
        key.public_key(),
        algorithms=["ES256"],
        options={"verify_aud": False},
    )
    assert claims["ath"] == ath_hash("abc")
