"""Demo: Bootstrap PLATFORM key creation.

This demo shows how to create the initial PLATFORM tier key
that bootstraps the entire API key hierarchy.

PLATFORM keys are special:
- No organization or user context
- Can create keys of any tier
- Typically only one exists in the system
"""

from gl_iam.core.types.api_key import ApiKey, ApiKeyTier
from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider

from services import KeyCreationService


async def run_bootstrap_demo(provider: PostgreSQLApiKeyProvider) -> ApiKey:
    """Demonstrate PLATFORM key creation for system bootstrap.

    In a real system, this would only run once during initial setup.
    The returned key should be stored securely and never exposed.

    Args:
        provider: The API key provider instance.

    Returns:
        The created PLATFORM ApiKey (metadata only, not the secret).
    """
    print("\n" + "=" * 60)
    print("DEMO: Bootstrap PLATFORM Key")
    print("=" * 60)

    service = KeyCreationService(provider)

    # Check if a platform key already exists
    existing_keys = await provider.list_api_keys(tier=ApiKeyTier.PLATFORM)
    if existing_keys:
        print(f"\nPLATFORM key already exists: {existing_keys[0].name}")
        print("Using existing key for demo...")
        return existing_keys[0]

    # Create new PLATFORM key
    print("\nCreating PLATFORM bootstrap key...")
    key, plain_key = await service.create_platform_key(
        name="System Bootstrap Key",
        scopes=["*"],  # Full access
    )

    print(f"\nPLATFORM Key Created:")
    print(f"  ID:       {key.id}")
    print(f"  Name:     {key.name}")
    print(f"  Tier:     {key.tier.value.upper()}")
    print(f"  Preview:  {key.key_preview}...")
    print(f"  Scopes:   {key.scopes}")

    print("\n  IMPORTANT: Store this key securely!")
    print(f"  Plain Key: {plain_key[:20]}...")
    print("  (In production, store in a secrets manager)")

    return key
