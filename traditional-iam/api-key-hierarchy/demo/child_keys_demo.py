"""Demo: Create limited-lifetime child keys.

This demo shows the "multiple child keys" pattern - creating
temporary keys that inherit from a parent (forever) key.

Child keys are ideal for:
- CI/CD pipelines (30-day keys)
- Partner integrations (limited scope)
- Temporary access (short lifetime)
"""

from gl_iam.core.types.api_key import ApiKey
from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider

from services import KeyCreationService


async def run_child_keys_demo(
    provider: PostgreSQLApiKeyProvider,
    organization_id: str,
    parent_key_id: str,
) -> list[tuple[ApiKey, str]]:
    """Demonstrate creating limited-lifetime child keys.

    Creates multiple child keys with different purposes:
    - CI/CD key: Execute agents, 30 days
    - Partner key: Read-only, 7 days
    - Temp key: Full access, 1 day

    Args:
        provider: The API key provider instance.
        organization_id: The organization the keys belong to.
        parent_key_id: The parent key's ID.

    Returns:
        List of (ApiKey, plain_key) tuples for each child key.
    """
    print("\n" + "=" * 60)
    print("DEMO: Limited-Lifetime Child Keys")
    print("=" * 60)

    service = KeyCreationService(provider)
    created_keys: list[tuple[ApiKey, str]] = []

    # Define child key configurations
    child_configs = [
        {
            "name": "CI/CD Pipeline Key",
            "scopes": ["agents:execute"],
            "days": 30,
            "description": "For automated deployments",
        },
        {
            "name": "Partner Integration Key",
            "scopes": ["agents:read"],
            "days": 7,
            "description": "Read-only for external partner",
        },
        {
            "name": "Temporary Debug Key",
            "scopes": ["agents:execute", "agents:read"],
            "days": 1,
            "description": "Short-term debugging access",
        },
    ]

    print(
        f"\nCreating {len(child_configs)} child keys under parent: {parent_key_id[:8]}..."
    )

    for config in child_configs:
        key, plain_key = await service.create_child_key(
            name=config["name"],
            organization_id=organization_id,
            parent_key_id=parent_key_id,
            scopes=config["scopes"],
            expires_in_days=config["days"],
        )
        created_keys.append((key, plain_key))

        print(f"\n  {config['name']}:")
        print(f"    ID:       {key.id}")
        print(f"    Parent:   {key.parent_key_id[:8]}...")
        print(f"    Scopes:   {key.scopes}")
        print(f"    Expires:  {key.expires_at.strftime('%Y-%m-%d %H:%M UTC')}")
        print(f"    Purpose:  {config['description']}")

    print("\n  Child keys created successfully!")
    print("  Note: Child scopes are a SUBSET of parent scopes.")

    return created_keys
