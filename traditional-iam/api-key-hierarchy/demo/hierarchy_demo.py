"""Demo: Key hierarchy visualization.

This demo shows how to visualize and navigate the API key
hierarchy using the HierarchyService.

Understanding the hierarchy helps with:
- Auditing key usage
- Managing key lifecycles
- Debugging authorization issues
"""

from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider

from services import HierarchyService


async def run_hierarchy_demo(
    provider: PostgreSQLApiKeyProvider,
    organization_id: str,
) -> None:
    """Demonstrate key hierarchy visualization.

    Shows the complete key tree for an organization with:
    - Root keys (forever keys)
    - Child keys under each root
    - Key metadata (scopes, expiration)

    Args:
        provider: The API key provider instance.
        organization_id: The organization to visualize.
    """
    print("\n" + "=" * 60)
    print("DEMO: Key Hierarchy Visualization")
    print("=" * 60)

    service = HierarchyService(provider)

    # Get all keys for the organization
    all_keys = await service.get_org_keys(organization_id)
    print(f"\nTotal keys for organization '{organization_id}': {len(all_keys)}")

    # Show root keys (forever keys)
    root_keys = await service.get_root_keys(organization_id)
    print(f"Root keys (forever keys): {len(root_keys)}")

    # Build and display tree
    print("\n--- Key Hierarchy Tree ---\n")
    tree = service.build_tree(all_keys)

    for root_id, node in tree.items():
        root_key = node["key"]
        children = node["children"]

        # Print root key
        print(f"{root_key.name}")
        print(f"  ID: {root_key.id}")
        print(f"  Preview: {root_key.key_preview}...")
        print(f"  Tier: {root_key.tier.value.upper()}")
        print(f"  Scopes: {root_key.scopes}")
        print(
            f"  Expires: {'Never' if not root_key.expires_at else root_key.expires_at}"
        )

        # Print children
        if children:
            print(f"  Children ({len(children)}):")
            for child in children:
                prefix = "  +--"
                expires = (
                    child.expires_at.strftime("%Y-%m-%d")
                    if child.expires_at
                    else "Never"
                )
                print(f"  {prefix} {child.name}")
                print(f"       Preview: {child.key_preview}...")
                print(f"       Scopes: {child.scopes}")
                print(f"       Expires: {expires}")
        else:
            print("  Children: None")

        print()

    # Print ASCII tree summary
    print("\n--- ASCII Tree Summary ---\n")
    print(service.format_tree_ascii(all_keys))

    # Show summary statistics
    print("\n--- Summary Statistics ---")
    print(f"  Total Keys:     {len(all_keys)}")
    print(f"  Root Keys:      {len(root_keys)}")
    print(f"  Child Keys:     {len(all_keys) - len(root_keys)}")

    # Count by expiration status
    forever_count = sum(1 for k in all_keys if k.expires_at is None)
    limited_count = len(all_keys) - forever_count
    print(f"  Forever Keys:   {forever_count}")
    print(f"  Limited Keys:   {limited_count}")

    print("\n  Hierarchy demo complete!")
