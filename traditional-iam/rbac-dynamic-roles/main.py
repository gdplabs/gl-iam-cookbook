"""
Multi-tenant dynamic role management with GL-IAM.

An admin API over the operations that let a tenant's role vocabulary change at
runtime: define a role, define the permissions it carries, hand it to a user,
retire it. Every route is scoped to one organization, and GL-IAM enforces the
caller's authority itself — this app never decides who is allowed to do what.

Run:
    uv run seed.py        # two tenants, a platform admin, per-tenant admins
    uv run main.py        # this server
    uv run walkthrough.py # drives the whole story against it
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from config import settings
from gl_iam import IAMGateway
from gl_iam.fastapi import add_exception_handlers, set_iam_gateway
from gl_iam.providers.native import NativeConfig, NativeProvider, PasswordPolicy
from routers import auth_router, permissions_router, roles_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Wire one Native-backed gateway for the whole process.

    One gateway serves every tenant: multi-tenancy in GL-IAM is a parameter on
    each call (`organization_id`), not a separate gateway per tenant.
    """
    config = NativeConfig(
        database_url=settings.database_url,
        secret_key=settings.secret_key,
        enable_auth_hosting=True,
        auto_create_tables=True,
        # Not the tenants themselves — just the org GL-IAM falls back to when a
        # call omits one. seed.py creates hotel-bali and hotel-ubud explicitly.
        default_org_id=settings.tenant_a_id,
        # Defaults reproduce the SDK's previous hardcoded rules; this example
        # tightens them so the policy is visible rather than implicit.
        password_policy=PasswordPolicy(min_length=12, require_special=True),
    )
    provider = NativeProvider(config)
    gateway = IAMGateway.from_fullstack_provider(provider)
    set_iam_gateway(gateway, default_organization_id=settings.tenant_a_id)

    yield

    await provider.close()


app = FastAPI(
    title="GL-IAM — Multi-Tenant Dynamic Role Management",
    description=__doc__,
    lifespan=lifespan,
)

# Maps GL-IAM exceptions onto 401/403/404/409 instead of a blanket 500. The
# RBAC handlers (RoleNotFoundError, SystemRoleError, ...) come with it.
add_exception_handlers(app)

app.include_router(auth_router)
app.include_router(roles_router)
app.include_router(permissions_router)


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Public health check."""
    return {"status": "healthy", "tenants": settings.tenants}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
