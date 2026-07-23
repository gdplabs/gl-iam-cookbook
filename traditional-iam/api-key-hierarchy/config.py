"""Configuration for GL-IAM API Key Hierarchy Example.

This module provides centralized configuration using Pydantic settings.
Configuration is loaded from environment variables or .env file.

Single Responsibility Principle: This module only handles configuration.
"""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# pydantic-settings' env_file loader only populates fields declared on
# Settings below - it does not export values into os.environ. GL-IAM's
# NativeConfig reads ENVIRONMENT/ENV straight from os.environ (see
# fail-secure check in NativeConfig.validate_security_settings), so we
# need python-dotenv here too to make `cp .env.example .env` actually work.
load_dotenv()


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
        # ENVIRONMENT (see .env.example) is read by GL-IAM's NativeConfig
        # directly from os.environ, not through this Settings model - ignore
        # it (and any other non-declared keys) instead of erroring.
        extra = "ignore"


# Singleton settings instance
settings = Settings()
