"""Create the initial PLATFORM_ADMIN user + set a password.

This stays in-process (no CLI subprocess) so the organization the admin is
placed in matches the one the GLChat backend will use at runtime, avoiding
org-id mismatch between the bootstrap-admin CLI and the runtime config.
"""

from __future__ import annotations

import asyncio
import sys
import uuid

from dotenv import load_dotenv

load_dotenv()

from glchat_backend.config import get_settings  # noqa: E402


async def run() -> None:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from gl_iam.core.roles.standard import StandardRole
    from gl_iam.providers.postgresql import PostgreSQLConfig, PostgreSQLProvider
    from gl_iam.providers.postgresql.models import (
        OrganizationModel,
        RoleModel,
        UserModel,
        UserRoleModel,
    )

    settings = get_settings()
    provider = PostgreSQLProvider(
        PostgreSQLConfig(
            database_url=settings.database_url,
            secret_key=settings.secret_key,
            encryption_key=settings.encryption_key,
            default_org_id=settings.default_org_id,
            enable_auth_hosting=True,
            auto_create_tables=True,
        )
    )
    try:
        # Provider lazily creates tables on first call — trigger it now so the
        # direct SQLAlchemy queries below find the tables they expect.
        await provider._ensure_tables()

        admin_role_name = StandardRole.PLATFORM_ADMIN.value
        org_id = settings.default_org_id

        async with AsyncSession(provider.engine) as session:
            # Ensure org exists
            org = (
                await session.execute(select(OrganizationModel).where(OrganizationModel.id == org_id))
            ).scalar_one_or_none()
            if org is None:
                org = OrganizationModel(id=org_id, name="GLChat", slug=org_id)
                session.add(org)
                await session.flush()
                print(f"Created org {org_id}")

            # Ensure PLATFORM_ADMIN role exists
            role = (
                await session.execute(select(RoleModel).where(RoleModel.name == admin_role_name))
            ).scalar_one_or_none()
            if role is None:
                role = RoleModel(id=str(uuid.uuid4()), name=admin_role_name, description="Platform administrator")
                session.add(role)
                await session.flush()
                print(f"Created role {admin_role_name}")
            role_id = role.id  # capture before session closes

            await session.commit()

        # Upsert admin user via provider (handles all SQLAlchemy + password hashing correctly)
        user = await provider.get_user_by_email(settings.bootstrap_admin_email, org_id)
        if user is None:
            from gl_iam.core.types import UserCreateInput

            user = await provider.create_user(
                UserCreateInput(email=settings.bootstrap_admin_email, display_name="Platform Admin"),
                organization_id=org_id,
            )
            print(f"Created admin user {user.email} (id={user.id})")
        else:
            print(f"Admin user already exists: {user.email} (id={user.id})")

        # Assign PLATFORM_ADMIN role (direct DB insert — standard assign_role requires an admin caller)
        async with AsyncSession(provider.engine) as session:
            existing = (
                await session.execute(
                    select(UserRoleModel).where(
                        UserRoleModel.user_id == user.id,
                        UserRoleModel.role_id == role_id,
                    )
                )
            ).scalar_one_or_none()
            if existing is None:
                session.add(UserRoleModel(user_id=user.id, role_id=role_id))
                await session.commit()
                print(f"Assigned {admin_role_name} to {user.email}")
            else:
                print(f"{user.email} already has {admin_role_name}")

        await provider.set_user_password(user.id, settings.bootstrap_admin_password, org_id)
        print(f"Password set for {user.email}.")

    finally:
        await provider.close()


def main():
    try:
        asyncio.run(run())
    except Exception as e:
        print(f"Bootstrap failed: {e}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
