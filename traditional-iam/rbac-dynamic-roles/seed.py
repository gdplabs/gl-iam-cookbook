"""
Provision the two tenants and the accounts the walkthrough logs in as.

Idempotent: run it as many times as you like.

Bootstrap note. Defining roles requires a PLATFORM_ADMIN caller, so the first
platform admin cannot be created *through* the API — something has to break the
cycle. It is done here by passing `roles=["platform_admin"]` to
`create_user_with_password`, which assigns roles at creation time without a
caller (the same path `gliam bootstrap-admin` uses). Everything after this
script goes through the authorized API, with a real caller checked every time.
"""

import asyncio

from config import settings
from gl_iam.core.exceptions import (
    OrganizationAlreadyExistsError,
    UserAlreadyExistsError,
)
from gl_iam.core.types import UserCreateInput
from gl_iam.providers.native import NativeConfig, NativeProvider, PasswordPolicy


async def ensure_organization(provider: NativeProvider, tenant_id: str) -> None:
    """Create a tenant organization if it isn't there yet.

    Args:
        provider: The Native provider.
        tenant_id: The organization ID to use verbatim, so URLs read
            `/orgs/hotel-bali/...` rather than carrying a generated UUID.
    """
    if await provider.get_organization(tenant_id) is not None:
        print(f"  organization {tenant_id!r} already exists")
        return

    try:
        await provider.create_organization(
            {"id": tenant_id, "name": tenant_id.replace("-", " ").title(), "slug": tenant_id}
        )
        print(f"  created organization {tenant_id!r}")
    except OrganizationAlreadyExistsError:
        print(f"  organization {tenant_id!r} already exists")


async def ensure_user(
    provider: NativeProvider,
    email: str,
    password: str,
    organization_id: str,
    roles: list[str],
) -> str:
    """Create a user with the given roles, or return the existing one's ID.

    Args:
        provider: The Native provider.
        email: The user's email, also their login identifier.
        password: Initial password. Must satisfy the configured PasswordPolicy.
        organization_id: The tenant the user belongs to.
        roles: Roles assigned at creation time — the bootstrap path described in
            this module's docstring. `org_member` arrives on its own via
            `auto_assign_default_role`.

    Returns:
        The user's ID.
    """
    existing = await provider.get_user_by_email(email, organization_id)
    if existing is not None:
        print(f"  user {email!r} already exists ({existing.id})")
        return existing.id

    try:
        user = await provider.create_user_with_password(
            user_data=UserCreateInput(
                email=email,
                display_name=email.split("@")[0].replace(".", " ").title(),
                organization_id=organization_id,
                roles=roles,
            ),
            password=password,
            organization_id=organization_id,
        )
    except UserAlreadyExistsError:
        user = await provider.get_user_by_email(email, organization_id)

    print(f"  created user {email!r} ({user.id}) roles={user.roles}")
    return user.id


async def main() -> None:
    """Provision both tenants, the platform admin, and each tenant's staff."""
    config = NativeConfig(
        database_url=settings.database_url,
        secret_key=settings.secret_key,
        enable_auth_hosting=True,
        auto_create_tables=True,
        default_org_id=settings.tenant_a_id,
        password_policy=PasswordPolicy(min_length=12, require_special=True),
    )
    provider = NativeProvider(config)
    await provider.initialize()

    try:
        print("Organizations")
        for tenant_id in settings.tenants:
            await ensure_organization(provider, tenant_id)

        print("\nPlatform admin (spans every tenant)")
        await ensure_user(
            provider,
            settings.platform_admin_email,
            settings.platform_admin_password,
            settings.tenant_a_id,
            roles=["platform_admin"],
        )

        for tenant_id in settings.tenants:
            print(f"\nStaff for {tenant_id}")
            await ensure_user(
                provider,
                settings.org_admin_email(tenant_id),
                settings.org_admin_password,
                tenant_id,
                roles=["org_admin"],
            )
            await ensure_user(
                provider,
                settings.member_email(tenant_id),
                settings.member_password,
                tenant_id,
                roles=[],
            )

        print("\nSeed complete. Next: uv run main.py, then uv run walkthrough.py")
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
