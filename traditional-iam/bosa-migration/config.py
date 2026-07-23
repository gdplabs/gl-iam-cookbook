"""Configuration settings for BOSA Migration example.

This module defines Pydantic Settings for loading configuration from environment.
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
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gliam"

    # Authentication
    secret_key: str = "your-secret-key-min-32-characters-long"
    default_organization_id: str = "org-123"

    # Third-party integration encryption
    encryption_key: str | None = None

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    class Config:
        """Pydantic settings config."""

        env_file = ".env"
        extra = "ignore"


settings = Settings()
