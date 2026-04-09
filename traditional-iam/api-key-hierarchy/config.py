"""Configuration for GL-IAM API Key Hierarchy Example.

This module provides centralized configuration using Pydantic settings.
Configuration is loaded from environment variables or .env file.

Single Responsibility Principle: This module only handles configuration.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Attributes:
        database_url: PostgreSQL connection string.
        api_key_prefix: Prefix for generated API keys (e.g., "aip" -> "aip_xxx").
        db_schema: Database schema for GL-IAM tables.
        default_organization_id: Default org ID for demo purposes.
    """

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gliam"
    api_key_prefix: str = "aip"
    db_schema: str = "gl_iam"
    default_organization_id: str = "acme-123"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton settings instance
settings = Settings()
