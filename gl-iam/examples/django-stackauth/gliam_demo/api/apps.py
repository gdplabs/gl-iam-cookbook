"""
API app configuration with GL-IAM Stack Auth gateway initialization.

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
        Stack Auth provider and set it as the global IAM gateway.
        """
        # Avoid running during management commands like migrate
        import sys
        if "runserver" not in sys.argv:
            return

        from gl_iam import IAMGateway
        from gl_iam.django import set_iam_gateway, run_sync
        from gl_iam.providers.stackauth import StackAuthConfig, StackAuthProvider

        config = StackAuthConfig(
            base_url=os.getenv("STACKAUTH_BASE_URL", "http://localhost:8102"),
            project_id=os.getenv("STACKAUTH_PROJECT_ID"),
            publishable_client_key=os.getenv("STACKAUTH_PUBLISHABLE_CLIENT_KEY"),
            secret_server_key=os.getenv("STACKAUTH_SECRET_SERVER_KEY"),
        )
        provider = StackAuthProvider(config)
        gateway = IAMGateway.from_fullstack_provider(provider)

        # Set gateway (default organization is configured in settings.py GL_IAM)
        set_iam_gateway(gateway)

        # Verify connection
        is_healthy = run_sync(provider.health_check())
        if is_healthy:
            print(f"GL-IAM gateway connected to Stack Auth at {os.getenv('STACKAUTH_BASE_URL')}")
