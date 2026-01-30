"""
Multi-provider configuration for RBAC Showcase.

This module provides Pydantic settings with support for both Keycloak
and StackAuth providers through a single PROVIDER_TYPE selector.
"""

from enum import Enum

from pydantic import Field
from pydantic_settings import BaseSettings


class ProviderType(str, Enum):
    """Supported authentication provider types."""

    KEYCLOAK = "keycloak"
    STACKAUTH = "stackauth"


class Settings(BaseSettings):
    """Application settings with multi-provider support."""

    # Provider selection
    provider_type: ProviderType = Field(
        default=ProviderType.KEYCLOAK,
        description="Authentication provider to use (keycloak or stackauth)",
    )

    # Keycloak configuration
    keycloak_server_url: str = Field(
        default="http://localhost:8080",
        description="Keycloak server URL",
    )
    keycloak_realm: str = Field(
        default="gl-iam-demo",
        description="Keycloak realm name",
    )
    keycloak_client_id: str = Field(
        default="glchat-backend",
        description="Keycloak client ID",
    )
    keycloak_client_secret: str = Field(
        default="glchat-backend-secret",
        description="Keycloak client secret",
    )

    # Stack Auth configuration
    stackauth_base_url: str = Field(
        default="http://localhost:8102",
        description="Stack Auth base URL",
    )
    stackauth_project_id: str | None = Field(
        default=None,
        description="Stack Auth project ID",
    )
    stackauth_publishable_client_key: str | None = Field(
        default=None,
        description="Stack Auth publishable client key",
    )
    stackauth_secret_server_key: str | None = Field(
        default=None,
        description="Stack Auth secret server key",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    def get_organization_id(self) -> str:
        """Get the organization ID based on the provider type."""
        if self.provider_type == ProviderType.KEYCLOAK:
            return self.keycloak_realm
        else:
            return self.stackauth_project_id or "default"


settings = Settings()
