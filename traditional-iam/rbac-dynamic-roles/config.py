"""
Settings for the dynamic role management example.

Everything here is read from `.env` (see `.env.example`). The two tenant IDs
matter more than they look: every role, permission, and assignment in this
example is scoped to one of them, and demonstrating that boundary is the point.
"""

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Also load .env into the *process* environment, not just into Settings below.
# NativeConfig's fail-secure validator reads ENVIRONMENT via os.getenv: without
# this it sees nothing, assumes production, and rejects the dev-grade SECRET_KEY.
load_dotenv()


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/gliam"
    secret_key: str = "your-secret-key-min-32-characters-long"

    # The two tenants. Each gets its own `property_manager` role, and they mean
    # different things — that is the whole reason roles are organization-scoped.
    tenant_a_id: str = "hotel-bali"
    tenant_b_id: str = "hotel-ubud"

    # Bootstrap accounts created by seed.py.
    platform_admin_email: str = "platform-admin@example.com"
    platform_admin_password: str = "Platform@dmin1"
    org_admin_password: str = "Org@dmin1234"
    member_password: str = "Member@12345"

    api_base_url: str = "http://localhost:8000"

    @property
    def tenants(self) -> list[str]:
        """The tenant IDs this example provisions, in a stable order."""
        return [self.tenant_a_id, self.tenant_b_id]

    def org_admin_email(self, tenant_id: str) -> str:
        """Email of the seeded ORG_ADMIN for a tenant."""
        return f"admin@{tenant_id}.example.com"

    def member_email(self, tenant_id: str) -> str:
        """Email of the seeded ORG_MEMBER for a tenant."""
        return f"member@{tenant_id}.example.com"


settings = Settings()
