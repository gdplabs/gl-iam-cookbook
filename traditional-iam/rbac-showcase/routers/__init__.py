"""
RBAC Showcase routers package.

This package contains the FastAPI routers for:
- auth: Authentication endpoints (token retrieval)
- rbac: RBAC demonstration endpoints
- admin: Role management endpoints
"""

from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.rbac import router as rbac_router

__all__ = ["auth_router", "rbac_router", "admin_router"]
