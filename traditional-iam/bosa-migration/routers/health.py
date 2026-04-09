"""Health check endpoints.

Provides health status for all providers.
"""

from fastapi import APIRouter

from deps import api_key_provider, provider, third_party_provider
from schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check health status of all services.

    Returns:
        HealthResponse with status of database and providers.
    """
    db_healthy = await provider.health_check()
    api_key_healthy = await api_key_provider.health_check()
    third_party_healthy = (
        await third_party_provider.health_check()
        if third_party_provider
        else False
    )

    all_healthy = db_healthy and api_key_healthy

    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        database=db_healthy,
        api_key_provider=api_key_healthy,
        third_party_provider=third_party_healthy,
    )
