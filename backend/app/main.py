"""Atlas AI FastAPI application entry point."""

from fastapi import FastAPI

from backend.app.api.v1.router import router as api_v1_router
from backend.app.config.settings import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the Atlas AI personal management system.",
)

app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """Provide a small landing response for local development."""

    return {"name": settings.app_name, "status": "running"}
