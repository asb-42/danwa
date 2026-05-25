"""Monitor API router — lightweight LLM activity status endpoint.

Provides real-time LLM call activity for the frontend header indicator.
"""

from __future__ import annotations

from fastapi import APIRouter

from backend.services.llm_activity import llm_activity

router = APIRouter()


@router.get("/activity")
async def get_llm_activity() -> dict:
    """Get current LLM activity status.

    Returns active calls, recent history, and token totals.
    Designed to be polled every 3-5 seconds by the frontend header.
    """
    return await llm_activity.get_status()
