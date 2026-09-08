"""Demo: Choosing the API key hash algorithm.

Validation hashes the key that was presented, and by default that hash is
bcrypt, which is slow on purpose. On a service that authenticates every request
that cost dominates the request.

The work factor is there to make guessing a *human-chosen* secret expensive.
GL-IAM generates every key itself from 256 bits of randomness and no method
accepts a key you supply, so there is no weak secret for the slowness to
protect. `HMAC_SHA256` is the opt-in alternative: same security properties for
an input of this size, but fast and deterministic, which also lets validation be
a single indexed lookup instead of a scan.

This demo runs the same key through both, so the interesting part is not the
timing but the third step: an existing bcrypt key keeps working after the switch
and rewrites its own stored hash on first use. No reissuing, no migration step.
"""

import time

from gl_iam.core.crypto_config import ApiKeyHashAlgorithm, CryptoConfig
from gl_iam.providers.native import NativeApiKeyProvider, NativeConfig
from sqlalchemy import text

from config import settings
from services import KeyCreationService


def _build_provider(algorithm: ApiKeyHashAlgorithm) -> NativeApiKeyProvider:
    """Build a provider against the same database with one algorithm chosen.

    Args:
        algorithm: The API key hash algorithm to configure.

    Returns:
        NativeApiKeyProvider: Provider ready for use.
    """
    return NativeApiKeyProvider(
        config=NativeConfig(
            database_url=settings.database_url,
            db_schema=settings.db_schema,
            auto_create_tables=False,
            api_key_prefix=settings.api_key_prefix,
            crypto_config=CryptoConfig(api_key_hash_algorithm=algorithm),
        )
    )


async def _time_validation(provider: NativeApiKeyProvider, plain_key: str) -> float:
    """Validate a key and report how long it took.

    Args:
        provider: The provider to validate through.
        plain_key: The plain API key.

    Returns:
        float: Elapsed milliseconds.

    Raises:
        RuntimeError: If the key fails to validate, which would make the timing
            meaningless.
    """
    started = time.perf_counter()
    identity = await provider.validate_api_key(plain_key)
    elapsed_ms = (time.perf_counter() - started) * 1000

    if identity is None:
        raise RuntimeError("Key failed to validate; the timing below would be meaningless")
    return elapsed_ms


async def _stored_hash(provider: NativeApiKeyProvider, key_id: str) -> str:
    """Read the stored hash directly, to show what migration actually changed.

    Args:
        provider: The provider whose engine to borrow.
        key_id: The API key's ID.

    Returns:
        str: The stored hash.
    """
    async with provider._engine.connect() as conn:
        result = await conn.execute(
            text(f"SELECT key_hash FROM {settings.db_schema}.api_keys WHERE id = :id"),
            {"id": key_id},
        )
        return result.scalar_one()


async def run_hash_algorithm_demo(organization_id: str) -> None:
    """Show what each algorithm costs, and that switching keeps existing keys working.

    Skipped, rather than failed, on an SDK without HMAC-SHA256, so that running the
    cookbook against an older gl-iam still exercises every other demo.

    Args:
        organization_id: Organization to create the demonstration key under.
    """
    print("\n" + "=" * 60)
    print("DEMO: Choosing the API Key Hash Algorithm")
    print("=" * 60)

    # Looked up rather than referenced directly: on an older gl-iam the member does
    # not exist, and naming it at import time would break every demo in this package.
    hmac_algorithm = getattr(ApiKeyHashAlgorithm, "HMAC_SHA256", None)
    if hmac_algorithm is None:
        print("\n   Skipped. This demo needs an HMAC-SHA256 capable gl-iam.")
        print("   Upgrade the pin in pyproject.toml to pick it up.")
        return

    bcrypt_provider = _build_provider(ApiKeyHashAlgorithm.BCRYPT)
    hmac_provider = _build_provider(hmac_algorithm)

    try:
        print("\n1. Creating a key the default way (bcrypt)...")
        api_key, plain_key = await KeyCreationService(bcrypt_provider).create_forever_org_key(
            name="hash-algorithm-demo",
            organization_id=organization_id,
        )
        stored = await _stored_hash(bcrypt_provider, api_key.id)
        print(f"   Stored as: {stored[:20]}...")

        print("\n2. Validating it with bcrypt...")
        print(f"   {await _time_validation(bcrypt_provider, plain_key):.1f} ms")

        print("\n3. Switching to HMAC-SHA256 and validating the SAME key...")
        print("   Nothing was reissued. The key was hashed by bcrypt and still works,")
        print("   because validation reads whichever format the row happens to hold.")
        print(f"   {await _time_validation(hmac_provider, plain_key):.1f} ms  (still bcrypt, plus the rewrite)")

        stored = await _stored_hash(hmac_provider, api_key.id)
        print(f"\n4. The row migrated itself on that first use: {stored[:20]}...")

        print("\n5. Validating again, now that it is stored as a digest...")
        print(f"   {await _time_validation(hmac_provider, plain_key):.1f} ms")

        print("\n   bcrypt stays the default. Set the algorithm only where the latency matters.")
        print("   See the GL IAM docs, Operations > Configuration, for the trade-offs.")
    finally:
        await bcrypt_provider.close()
        await hmac_provider.close()
