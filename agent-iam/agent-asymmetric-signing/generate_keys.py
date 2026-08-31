"""
Generate the issuer's signing key pair.

Run this once, before starting the services. It writes an ECDSA P-256 key
pair to ``keys/``:

* ``issuer_private.pem`` -- the **issuer** signs delegation tokens with this.
  It never leaves the issuing service.
* ``issuer_public.pem`` -- the public half. It is what ``/.well-known/jwks.json``
  publishes, and it is all a verifier ever needs.

ES256 is the default here rather than RS256 because the keys and the
resulting tokens are markedly smaller for the same security level, and
delegation tokens travel on every agent call. RS256 works identically --
swap the curve generation for ``rsa.generate_private_key(...)`` and set
``SigningAlgorithm.RS256``.
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

KEY_DIR = Path(__file__).parent / "keys"
PRIVATE_KEY_PATH = KEY_DIR / "issuer_private.pem"
PUBLIC_KEY_PATH = KEY_DIR / "issuer_public.pem"


def generate() -> None:
    """Write a fresh ES256 key pair to ``keys/``."""
    KEY_DIR.mkdir(exist_ok=True)

    private_key = ec.generate_private_key(ec.SECP256R1())

    PRIVATE_KEY_PATH.write_text(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
    )
    # 0600: the private key is the only thing standing between "can verify"
    # and "can mint". In production it belongs in a secret manager, not on disk.
    PRIVATE_KEY_PATH.chmod(0o600)

    PUBLIC_KEY_PATH.write_text(
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )

    print(f"Private key (issuer only): {PRIVATE_KEY_PATH}")
    print(f"Public key  (publishable): {PUBLIC_KEY_PATH}")


if __name__ == "__main__":
    generate()
