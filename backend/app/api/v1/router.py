"""Versioned API router."""

from fastapi import APIRouter

from backend.app.api.v1.health import router as health_router

router = APIRouter()
router.include_router(health_router)
