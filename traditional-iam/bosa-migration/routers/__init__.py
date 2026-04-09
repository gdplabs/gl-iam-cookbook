"""Router modules for BOSA Migration example."""

from routers.api_keys import router as api_keys_router
from routers.auth import router as auth_router
from routers.health import router as health_router
from routers.third_party import router as third_party_router
from routers.users import router as users_router

__all__ = [
    "api_keys_router",
    "auth_router",
    "health_router",
    "third_party_router",
    "users_router",
]
