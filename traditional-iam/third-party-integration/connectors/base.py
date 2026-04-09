"""Abstract base connector for third-party OAuth integrations.

This follows the BOSA plugin pattern (ThirdPartyIntegrationPlugin) where each
third-party service implements a connector class with standardized methods for
OAuth authorization, callback handling, and token revocation.

To add a new connector (e.g., Google, Slack), create a new class that inherits
from BaseConnector and implements all abstract methods.

References:
    - BOSA: bosa_server_plugins/common/plugin.py (ThirdPartyIntegrationPlugin)
"""

from abc import ABC, abstractmethod

from fastapi import FastAPI

from gl_iam.core.protocols.third_party import ThirdPartyIntegrationProvider


class BaseConnector(ABC):
    """Base class for third-party OAuth connectors.

    Each connector handles the OAuth flow for a specific service (GitHub, Google,
    Slack, etc.) and stores credentials via GL-IAM's ThirdPartyIntegrationProvider.

    Attributes:
        provider: The GL-IAM provider used to store/retrieve integrations.
    """

    def __init__(self, provider: ThirdPartyIntegrationProvider) -> None:
        self.provider = provider

    @property
    @abstractmethod
    def name(self) -> str:
        """Connector name used as the 'connector' field in integrations (e.g., 'github')."""

    @property
    @abstractmethod
    def scopes(self) -> list[str]:
        """OAuth scopes to request from the third-party service."""

    @abstractmethod
    async def initialize_authorization(
        self, user_id: str, org_id: str, callback_url: str
    ) -> str:
        """Start the OAuth flow by generating an authorization URL.

        Creates a CSRF state token and returns the URL to redirect the user to
        for authorization with the third-party service.

        Args:
            user_id: The GL-IAM user ID initiating the OAuth flow.
            org_id: The organization ID for multi-tenancy scope.
            callback_url: URL to redirect the user to after OAuth completes
                (the frontend URL, not the OAuth callback).

        Returns:
            The authorization URL to redirect the user to.
        """

    @abstractmethod
    async def handle_callback(self, code: str, state: str) -> str:
        """Handle the OAuth callback after the user authorizes.

        Validates the CSRF state, exchanges the authorization code for an access
        token, fetches the user's identity from the third-party service, and
        stores the integration via GL-IAM.

        Args:
            code: The authorization code from the OAuth provider.
            state: The state parameter for CSRF validation.

        Returns:
            The callback URL to redirect the user to (the frontend URL).
        """

    @abstractmethod
    async def revoke_token(self, auth_string: str) -> None:
        """Revoke a token with the third-party OAuth provider.

        Called when removing an integration to ensure the token is invalidated
        on the provider side as well.

        Args:
            auth_string: The decrypted access token to revoke.
        """

    @abstractmethod
    def register_routes(self, app: FastAPI, prefix: str) -> None:
        """Register connector-specific routes on the FastAPI app.

        At minimum, this should register the OAuth callback endpoint that the
        third-party service redirects to after authorization.

        Args:
            app: The FastAPI application instance.
            prefix: URL prefix for the connector's routes (e.g., '/connectors/github').
        """
