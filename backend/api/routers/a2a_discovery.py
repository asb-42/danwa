"""A2A Discovery — API router for A2A agent discovery and capability storage (Phase 8).

Endpoints:
- POST /api/v1/a2a/discover — discover A2A agent capabilities
- POST /api/v1/a2a/capabilities/{profile_id} — store discovered capabilities
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.a2a.adapter import A2AAdapter
from backend.a2a.exceptions import A2AError
from backend.a2a.url_validator import validate_a2a_url
from backend.blueprints.repository import BlueprintRepository
from backend.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["a2a-discovery"])


class DiscoverRequest(BaseModel):
    """Request body for A2A discovery."""

    endpoint_url: str = Field(..., description="A2A agent endpoint URL")


class CapabilitiesRequest(BaseModel):
    """Request body for storing A2A capabilities."""

    capabilities: dict[str, Any] = Field(..., description="Discovered capabilities from A2A agent")


@router.post("/discover")
async def discover_a2a_agent(body: DiscoverRequest) -> dict[str, Any]:
    """Discover the capabilities of an external A2A agent.

    Fetches the agent's Agent Card and returns structured capability info.

    Returns:
        Dict with name, description, version, capabilities, skills,
        input_modes, output_modes.

    Raises:
        HTTP 400: Invalid URL format.
        HTTP 403: Private IP blocked.
        HTTP 502: Agent unreachable.
        HTTP 504: Discovery timed out.
    """
    # Validate URL
    try:
        validate_a2a_url(body.endpoint_url, settings.a2a_allow_private_ips)
    except A2AError as exc:
        error_msg = str(exc).lower()
        if "private ip" in error_msg:
            raise HTTPException(status_code=403, detail=str(exc))
        raise HTTPException(status_code=400, detail=str(exc))

    # Discover
    try:
        adapter = A2AAdapter(
            a2a_endpoint=body.endpoint_url,
            timeout=30,
            allow_private_ips=settings.a2a_allow_private_ips,
        )
        capabilities = await adapter.discover()
    except A2AError as exc:
        error_msg = str(exc).lower()
        if "timeout" in error_msg:
            raise HTTPException(status_code=504, detail=f"A2A discovery timed out: {exc}")
        raise HTTPException(status_code=502, detail=f"A2A agent unreachable: {exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"A2A discovery failed: {exc}")

    return capabilities


@router.post("/capabilities/{profile_id}")
async def store_a2a_capabilities(
    profile_id: str,
    body: CapabilitiesRequest,
) -> dict[str, Any]:
    """Store discovered A2A capabilities in a blueprint LLM profile.

    Args:
        profile_id: The blueprint LLM profile ID to update.
        body: The discovered capabilities.

    Returns:
        Dict with status and profile_id.

    Raises:
        HTTP 404: Profile not found.
    """
    repo = BlueprintRepository()
    profile = repo.get_llm_profile(profile_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail=f"LLM profile '{profile_id}' not found",
        )

    # Update the a2a_config field
    profile.a2a_config = body.capabilities
    repo.save_llm_profile(profile)

    logger.info("Stored A2A capabilities for profile %s", profile_id)
    return {"status": "ok", "profile_id": profile_id}
