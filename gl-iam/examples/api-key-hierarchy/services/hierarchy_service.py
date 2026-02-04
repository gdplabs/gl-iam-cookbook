"""Hierarchy service for key relationship operations.

This module implements the Open/Closed Principle - the service is
open for extension (new hierarchy operations) but closed for modification.

New hierarchy visualization or traversal methods can be added without
changing existing code.
"""

from gl_iam.core.types.api_key import ApiKey, ApiKeyTier
from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider


class HierarchyService:
    """Service for managing and visualizing API key hierarchy.

    This service provides operations for understanding the parent-child
    relationships between API keys.

    Attributes:
        _provider: The underlying API key provider.
    """

    def __init__(self, provider: PostgreSQLApiKeyProvider):
        """Initialize the hierarchy service.

        Args:
            provider: PostgreSQL API key provider instance.
        """
        self._provider = provider

    async def get_children(self, parent_key_id: str) -> list[ApiKey]:
        """Get all child keys of a parent key.

        Args:
            parent_key_id: The ID of the parent key.

        Returns:
            List of child ApiKey objects.

        Example:
            >>> children = await service.get_children(parent.id)
            >>> print(f"Parent has {len(children)} child keys")
        """
        all_keys = await self._provider.list_api_keys()
        return [k for k in all_keys if k.parent_key_id == parent_key_id]

    async def get_org_keys(
        self,
        organization_id: str,
        include_revoked: bool = False,
    ) -> list[ApiKey]:
        """Get all keys for an organization.

        Args:
            organization_id: The organization ID to query.
            include_revoked: Whether to include revoked keys.

        Returns:
            List of ApiKey objects for the organization.
        """
        return await self._provider.list_api_keys(
            organization_id=organization_id,
            include_revoked=include_revoked,
        )

    async def get_root_keys(self, organization_id: str) -> list[ApiKey]:
        """Get all root keys (keys without parents) for an organization.

        Root keys are the "forever keys" that serve as the primary
        API keys for an organization.

        Args:
            organization_id: The organization ID to query.

        Returns:
            List of root ApiKey objects.
        """
        org_keys = await self.get_org_keys(organization_id)
        return [k for k in org_keys if k.parent_key_id is None]

    def build_tree(self, keys: list[ApiKey]) -> dict[str, dict]:
        """Build hierarchical tree structure from flat key list.

        Organizes keys into a tree based on parent-child relationships.

        Args:
            keys: List of ApiKey objects.

        Returns:
            Dictionary mapping root key IDs to their tree structure.
            Each tree node has {"key": ApiKey, "children": [ApiKey, ...]}.

        Example:
            >>> keys = await service.get_org_keys("acme-123")
            >>> tree = service.build_tree(keys)
            >>> for key_id, node in tree.items():
            ...     print(f"Root: {node['key'].name}")
            ...     for child in node['children']:
            ...         print(f"  Child: {child.name}")
        """
        # First pass: identify root keys (no parent)
        tree: dict[str, dict] = {}
        for key in keys:
            if key.parent_key_id is None:
                tree[key.id] = {"key": key, "children": []}

        # Second pass: attach children to their parents
        for key in keys:
            if key.parent_key_id and key.parent_key_id in tree:
                tree[key.parent_key_id]["children"].append(key)

        return tree

    def format_tree_ascii(self, keys: list[ApiKey]) -> str:
        """Format the key hierarchy as ASCII art.

        Creates a human-readable tree visualization.

        Args:
            keys: List of ApiKey objects.

        Returns:
            String containing ASCII tree representation.

        Example:
            >>> print(service.format_tree_ascii(keys))
            Primary API Key (aip_abc1...) [ORGANIZATION]
            +-- CI/CD Key (aip_def2...) [ORGANIZATION] expires: 2024-03-01
            +-- Partner Key (aip_ghi3...) [ORGANIZATION] expires: 2024-02-15
        """
        tree = self.build_tree(keys)
        lines = []

        for root_id, node in tree.items():
            root_key = node["key"]
            lines.append(self._format_key_line(root_key, prefix=""))

            children = node["children"]
            for i, child in enumerate(children):
                is_last = i == len(children) - 1
                prefix = "`-- " if is_last else "+-- "
                lines.append(self._format_key_line(child, prefix=prefix))

        return "\n".join(lines)

    def _format_key_line(self, key: ApiKey, prefix: str) -> str:
        """Format a single key as a tree line.

        Args:
            key: The ApiKey to format.
            prefix: Tree prefix (empty for root, +-- or `-- for children).

        Returns:
            Formatted string for the key.
        """
        expires = ""
        if key.expires_at:
            expires = f" expires: {key.expires_at.strftime('%Y-%m-%d')}"

        scopes = ", ".join(key.scopes[:3])
        if len(key.scopes) > 3:
            scopes += f", +{len(key.scopes) - 3} more"

        return (
            f"{prefix}{key.name} ({key.key_preview}...) "
            f"[{key.tier.value.upper()}] scopes: [{scopes}]{expires}"
        )

    async def print_org_hierarchy(self, organization_id: str) -> None:
        """Print the complete key hierarchy for an organization.

        Convenience method for debugging and visualization.

        Args:
            organization_id: The organization ID to display.
        """
        keys = await self.get_org_keys(organization_id)
        if not keys:
            print(f"No keys found for organization: {organization_id}")
            return

        print(f"\nKey Hierarchy for Organization: {organization_id}")
        print("=" * 60)
        print(self.format_tree_ascii(keys))
        print("=" * 60)
