"""Provider factory for GL-IAM API Key operations.

This module implements the Dependency Inversion Principle by providing
a factory function that creates properly configured API key providers.

High-level business logic (services, demos) depend on the abstract
PostgreSQLApiKeyProvider interface, not on concrete configuration details.
"""

from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider, PostgreSQLConfig

from config import settings


def create_api_key_provider() -> PostgreSQLApiKeyProvider:
    """Create and return a configured API key provider.

    This factory function encapsulates the configuration complexity,
    allowing consumers to simply request a provider without knowing
    the underlying setup details.

    Returns:
        PostgreSQLApiKeyProvider: Configured provider ready for use.

    Example:
        >>> provider = create_api_key_provider()
        >>> key, secret = await provider.create_api_key(name="my-key", ...)
    """
    config = PostgreSQLConfig(
        database_url=settings.database_url,
        db_schema=settings.db_schema,
        auto_create_tables=True,
        api_key_prefix=settings.api_key_prefix,
    )
    return PostgreSQLApiKeyProvider(config=config)


async def ensure_tables(provider: PostgreSQLApiKeyProvider) -> None:
    """Ensure all required database tables and organization exist.

    Args:
        provider: The API key provider instance.
    """
    from sqlalchemy import text
    from gl_iam.providers.postgresql.models import Base

    async with provider._engine.begin() as conn:
        if settings.db_schema:
            await conn.execute(
                text(f"CREATE SCHEMA IF NOT EXISTS {settings.db_schema}")
            )
        await conn.run_sync(Base.metadata.create_all)

        result = await conn.execute(
            text(f"SELECT id FROM {settings.db_schema}.organizations WHERE id = :id"),
            {"id": settings.default_organization_id},
        )
        if not result.scalar():
            await conn.execute(
                text(f"""
                    INSERT INTO {settings.db_schema}.organizations (id, name, slug, created_at)
                    VALUES (:id, :name, :slug, NOW())
                """),
                {
                    "id": settings.default_organization_id,
                    "name": f"Organization {settings.default_organization_id}",
                    "slug": settings.default_organization_id,
                },
            )
