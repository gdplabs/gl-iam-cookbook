"""Routers for the dynamic role management example."""

from routers.auth import router as auth_router
from routers.permissions import router as permissions_router
from routers.roles import router as roles_router

__all__ = ["auth_router", "permissions_router", "roles_router"]
