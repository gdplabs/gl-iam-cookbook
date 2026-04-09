"""Demo: Create forever ORGANIZATION key.

This demo shows the "1 forever key" pattern - creating a primary
API key for an organization that never expires.

Forever keys serve as the root of the key hierarchy for an organization:
- Never expire (expires_at = None)
- Can create child keys
- Should have comprehensive scopes for the organization's needs
"""

from gl_iam.core.types.api_key import ApiKey, ApiKeyTier
from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider

from services import KeyCreationService, HierarchyService


async def run_organization_demo(
    provider: PostgreSQLApiKeyProvider,
    organization_id: str,
) -> tuple[ApiKey, str]:
    """Demonstrate creating a forever ORGANIZATION key.

    This is the primary key pattern for the AI Agent Platform:
    one long-lived key per organization that can spawn child keys.

    Args:
        provider: The API key provider instance.
        organization_id: The organization to create the key for.

    Returns:
        Tuple of (ApiKey metadata, plain key string).
    """
    print("\n" + "=" * 60)
    print("DEMO: Forever ORGANIZATION Key")
    print("=" * 60)

    key_service = KeyCreationService(provider)
    hierarchy_service = HierarchyService(provider)

    # Check for existing root keys
    existing_roots = await hierarchy_service.get_root_keys(organization_id)
    if existing_roots:
        print(f"\nOrganization already has {len(existing_roots)} root key(s).")
        print("Creating another for demo purposes...")

    # Create forever organization key
    print(f"\nCreating forever key for organization: {organization_id}")

    key, plain_key = await key_service.create_forever_org_key(
        name="Primary API Key",
        organization_id=organization_id,
        scopes=[
            "agents:execute",  # Execute AI agents
            "agents:read",  # Read agent status
            "agents:write",  # Configure agents
            "keys:create",  # Create child keys
            "keys:revoke",  # Revoke child keys
        ],
    )

    print(f"\nForever Key Created:")
    print(f"  ID:           {key.id}")
    print(f"  Name:         {key.name}")
    print(f"  Tier:         {key.tier.value.upper()}")
    print(f"  Organization: {key.organization_id}")
    print(f"  Preview:      {key.key_preview}...")
    print(f"  Scopes:       {key.scopes}")
    print(f"  Expires:      Never (None)")

    print("\n  Use this key to create limited-lifetime child keys.")
    print(f"  Plain Key:    {plain_key[:20]}...")

    return key, plain_key
