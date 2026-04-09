"""GL-IAM API Key Hierarchy Demo - Entry Point.

This is the main orchestrator that runs all demo modules in sequence.
It demonstrates the complete API key hierarchy workflow:

1. Bootstrap: Create PLATFORM key for system initialization
2. Organization: Create forever key for an organization
3. Child Keys: Create limited-lifetime keys under the org key
4. Validation: Validate keys and check scopes
5. Hierarchy: Visualize the key tree structure

Usage:
    python main.py

    Or with uv:
    uv run python main.py
"""

import asyncio
import sys

from providers.api_key_provider import create_api_key_provider, ensure_tables
from demo import (
    run_bootstrap_demo,
    run_organization_demo,
    run_child_keys_demo,
    run_validation_demo,
    run_hierarchy_demo,
)
from config import settings


async def main() -> int:
    """Run all demos in sequence.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    print("=" * 60)
    print("GL-IAM API Key Hierarchy Demo (SOLID Architecture)")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Database: {settings.database_url[:30]}...")
    print(f"  Schema:   {settings.db_schema}")
    print(f"  Prefix:   {settings.api_key_prefix}")
    print(f"  Org ID:   {settings.default_organization_id}")

    try:
        # Initialize provider and ensure tables exist
        provider = create_api_key_provider()
        await ensure_tables(provider)

        # Run demos in order (each builds on the previous)
        _platform_key = await run_bootstrap_demo(provider)

        org_key, org_plain = await run_organization_demo(
            provider,
            settings.default_organization_id,
        )

        child_keys = await run_child_keys_demo(
            provider,
            settings.default_organization_id,
            org_key.id,
        )

        await run_validation_demo(
            provider,
            org_plain,
            child_keys,
        )

        await run_hierarchy_demo(
            provider,
            settings.default_organization_id,
        )

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Review the generated keys in your PostgreSQL database")
        print("  2. Try modifying the demo configurations in demo/*.py")
        print("  3. Integrate this pattern into your own application")
        print("\nFor more information, see:")
        print("  https://gdplabs.gitbook.io/sdk/tutorials/identity-and-access-management/api-keys")

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure PostgreSQL is running")
        print("  2. Check your DATABASE_URL in .env")
        print("  3. Verify GL-IAM is installed: pip install gl-iam")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
