"""
API app configuration with GL-IAM Keycloak gateway initialization.

Unlike FastAPI's lifespan context manager, Django uses AppConfig.ready()
to initialize the GL-IAM gateway when the application starts.
"""

import os

from django.apps import AppConfig


class ApiConfig(AppConfig):
    """Configuration for the API app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "gliam_demo.api"

    def ready(self):
        """
        Initialize GL-IAM gateway when Django starts.

        This is called once when Django starts up. We configure the
        Keycloak provider and set it as the global IAM gateway.
        """
        # Avoid running during management commands like migrate
        import sys
        if "runserver" not in sys.argv:
            return

        from gl_iam import IAMGateway
        from gl_iam.django import set_iam_gateway, run_sync
        from gl_iam.providers.keycloak import KeycloakConfig, KeycloakProvider

        config = KeycloakConfig(
            server_url=os.getenv("KEYCLOAK_SERVER_URL"),
            realm=os.getenv("KEYCLOAK_REALM"),
            client_id=os.getenv("KEYCLOAK_CLIENT_ID"),
            client_secret=os.getenv("KEYCLOAK_CLIENT_SECRET"),
        )
        provider = KeycloakProvider(config=config)
        gateway = IAMGateway.from_fullstack_provider(provider)

        # Set gateway (default organization is configured in settings.py GL_IAM)
        set_iam_gateway(gateway)

        # Verify connection
        is_healthy = run_sync(provider.health_check())
        if is_healthy:
            print(f"GL-IAM gateway connected to Keycloak at {os.getenv('KEYCLOAK_SERVER_URL')}")
