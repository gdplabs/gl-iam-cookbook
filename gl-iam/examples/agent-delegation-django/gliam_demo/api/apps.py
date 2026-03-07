"""
App configuration for GL-IAM Agent Delegation demo.

Initializes the GL-IAM gateway with PostgreSQL provider and agent support
when the Django development server starts.
"""

import os
import sys

from django.apps import AppConfig
from dotenv import load_dotenv

load_dotenv()


class ApiConfig(AppConfig):
    """API application configuration."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "gliam_demo.api"

    def ready(self):
        """Initialize GL-IAM gateway on server startup."""
        if "runserver" not in sys.argv:
            return

        from gl_iam import IAMGateway
        from gl_iam.django import set_iam_gateway
        from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider

        default_org_id = os.getenv("DEFAULT_ORGANIZATION_ID", "default")

        config = PostgreSQLConfig(
            database_url=os.getenv("DATABASE_URL"),
            secret_key=os.getenv("SECRET_KEY"),
            enable_auth_hosting=True,
            enable_third_party_provider=False,
            auto_create_tables=True,
            default_org_id=default_org_id,
            use_null_pool=True,
        )
        provider = PostgreSQLProvider(config)

        # from_fullstack_provider auto-detects agent_provider
        gateway = IAMGateway.from_fullstack_provider(provider)
        set_iam_gateway(gateway)

        print("GL-IAM gateway initialized with PostgreSQL provider (agent support enabled)")
