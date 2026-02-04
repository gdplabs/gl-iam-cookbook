"""Demo: Key validation and scope checking.

This demo shows how to validate API keys and check their
permissions using the KeyValidationService.

Validation is critical for:
- Authenticating API requests
- Authorizing specific operations
- Checking key expiration and revocation
"""

from gl_iam.core.types.api_key import ApiKey
from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider

from services import KeyValidationService


async def run_validation_demo(
    provider: PostgreSQLApiKeyProvider,
    org_plain_key: str,
    child_keys: list[tuple[ApiKey, str]],
) -> None:
    """Demonstrate key validation and scope checking.

    Tests various validation scenarios:
    - Valid key validation
    - Scope presence checking
    - Child key creation permission

    Args:
        provider: The API key provider instance.
        org_plain_key: Plain text of the organization key.
        child_keys: List of (ApiKey, plain_key) tuples for child keys.
    """
    print("\n" + "=" * 60)
    print("DEMO: Key Validation & Scope Checking")
    print("=" * 60)

    service = KeyValidationService(provider)

    # Test 1: Validate organization key
    print("\n1. Validating Organization Key...")
    identity = await service.validate(org_plain_key)
    if identity:
        print(f"   Valid! Key: {identity.name}")
        print(f"   Tier: {identity.tier.value.upper()}")
        print(f"   Organization: {identity.organization_id}")
        print(f"   Scopes: {identity.scopes}")
    else:
        print("   INVALID or EXPIRED!")

    # Test 2: Check specific scopes on org key
    print("\n2. Checking Scopes on Organization Key...")
    scopes_to_check = ["agents:execute", "agents:delete", "keys:create"]
    for scope in scopes_to_check:
        has_it = await service.has_scope(org_plain_key, scope)
        status = "YES" if has_it else "NO"
        print(f"   {scope}: {status}")

    # Test 3: Check if org key can create children
    print("\n3. Can Organization Key Create Children?")
    can_create = await service.can_create_child(org_plain_key)
    print(f"   Can create child keys: {'YES' if can_create else 'NO'}")

    # Test 4: Validate child keys
    if child_keys:
        print("\n4. Validating Child Keys...")
        for key, plain_key in child_keys:
            identity = await service.validate(plain_key)
            if identity:
                can_create = await service.can_create_child(plain_key)
                print(f"\n   {key.name}:")
                print(f"     Tier: {identity.tier.value.upper()}")
                print(f"     Scopes: {identity.scopes}")
                print(f"     Can create children: {'YES' if can_create else 'NO'}")

    # Test 5: Demonstrate invalid key
    print("\n5. Testing Invalid Key...")
    invalid_identity = await service.validate("aip_invalid_key_12345")
    if invalid_identity is None:
        print("   Correctly rejected invalid key!")
    else:
        print("   ERROR: Should have rejected invalid key!")

    print("\n  Validation demo complete!")
