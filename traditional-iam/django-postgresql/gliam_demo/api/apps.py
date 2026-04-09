"""
API app configuration with GL-IAM gateway initialization.

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
        PostgreSQL provider and set it as the global IAM gateway.
        """
        import sys

        if "runserver" not in sys.argv:
            return

        from gl_iam import IAMGateway
        from gl_iam.django import set_iam_gateway
        from gl_iam.providers.postgresql import (
            PostgreSQLProvider,
            PostgreSQLConfig,
        )

        default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

        config = PostgreSQLConfig(
            database_url=os.getenv("DATABASE_URL"),
            secret_key=os.getenv("SECRET_KEY"),
            enable_auth_hosting=True,
            auto_create_tables=True,
            default_org_id=default_org_id,
            use_null_pool=True,
        )
        provider = PostgreSQLProvider(config)
        gateway = IAMGateway.from_fullstack_provider(provider)

        set_iam_gateway(gateway)

        print("GL-IAM gateway initialized with PostgreSQL provider")
