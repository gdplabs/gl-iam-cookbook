"""Provider factory for GL-IAM API Key operations.

This module implements the Dependency Inversion Principle by providing
a factory function that creates properly configured API key providers.

High-level business logic (services, demos) depend on the abstract
PostgreSQLApiKeyProvider interface, not on concrete configuration details.
"""

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from gl_iam.providers.postgresql import PostgreSQLApiKeyProvider, PostgreSQLConfig

from config import settings

# Module-level engine for reuse
_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Get or create the async database engine.

    Returns:
        AsyncEngine: SQLAlchemy async engine instance.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.database_url,
            echo=False,  # Set to True for SQL debugging
        )
    return _engine


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
    engine = get_engine()
    return PostgreSQLApiKeyProvider(engine=engine, config=config)


async def ensure_tables(provider: PostgreSQLApiKeyProvider) -> None:
    """Ensure all required database tables exist.

    Args:
        provider: The API key provider instance.
    """
    from sqlalchemy import text
    from gl_iam.providers.postgresql.models import Base

    engine = get_engine()
    async with engine.begin() as conn:
        # Create schema if it doesn't exist
        if settings.db_schema:
            await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {settings.db_schema}"))
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
