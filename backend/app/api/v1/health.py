"""Health endpoint for service checks and local development."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Return the application health status."""

    return {"status": "ok"}
