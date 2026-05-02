"""Health check router."""

from __future__ import annotations

from fastapi import APIRouter

from backend.api.deps import get_settings
from backend.models.schemas import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    """Return application health status."""
    settings = get_settings()
    return HealthResponse(status="ok", version=settings.app_version)
