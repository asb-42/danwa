"""Profile management API router.

Provides CRUD endpoints for LLM profiles and utility endpoints
for composition components and cost estimation.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.core.config import is_service_llm_eligible
from backend.core.profiles import LLMProfile
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level service instance
_profile_service: ProfileService | None = None


def get_profile_service() -> ProfileService:
    """Get or create the profile service singleton."""
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service


# ------------------------------------------------------------------
# LLM Profiles
# ------------------------------------------------------------------


@router.get("/llm/service-eligible")
async def list_service_eligible_llm_profiles() -> list[dict]:
    """List all LLM profiles eligible for utility/background tasks."""
    ps = get_profile_service()
    all_profiles = ps.list_llm_profiles()
    eligible = []
    for p in all_profiles:
        elig, reason = is_service_llm_eligible(p)
        eligible.append(
            {
                "id": p.id,
                "name": p.name,
                "model": p.model,
                "provider": p.provider.value,
                "service_eligible": elig,
                "eligibility_reason": reason,
                "context_window": p.context_window,
            }
        )
    eligible.sort(key=lambda x: (0 if x["service_eligible"] else 1, -(x["context_window"] or 0)))
    return eligible


@router.get("/llm", response_model=list[LLMProfile])
async def list_llm_profiles() -> list[LLMProfile]:
    """List all available LLM profiles."""
    return get_profile_service().list_llm_profiles()


@router.get("/llm/{profile_id}", response_model=LLMProfile)
async def get_llm_profile(profile_id: str) -> LLMProfile:
    """Get a specific LLM profile by ID."""
    profile = get_profile_service().get_llm_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"LLM profile '{profile_id}' not found")
    return profile


@router.post("/llm", response_model=LLMProfile, status_code=201)
async def create_llm_profile(profile: LLMProfile) -> LLMProfile:
    """Create a new LLM profile."""
    return get_profile_service().save_llm_profile(profile)


@router.put("/llm/{profile_id}", response_model=LLMProfile)
async def update_llm_profile(profile_id: str, profile: LLMProfile) -> LLMProfile:
    """Update an existing LLM profile."""
    existing = get_profile_service().get_llm_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"LLM profile '{profile_id}' not found")
    # Ensure the ID in the URL matches the body
    profile.id = profile_id
    return get_profile_service().save_llm_profile(profile)


@router.delete("/llm/{profile_id}")
async def delete_llm_profile(profile_id: str) -> dict:
    """Delete an LLM profile."""
    if not get_profile_service().delete_llm_profile(profile_id):
        raise HTTPException(status_code=404, detail=f"LLM profile '{profile_id}' not found")
    return {"status": "ok", "deleted": profile_id}


# ------------------------------------------------------------------
# Composition Components (Phase 2 — Composer Architecture)
# ------------------------------------------------------------------


@router.get("/composition/components")
async def list_composition_components() -> dict:
    """List all available components for the Prompt Composer UI.

    Returns all four component types in a single call:
      - agent_cores: functional role definitions
      - argumentation_patterns: argumentation methodologies
      - tone_profiles: communication style profiles
      - prompt_modifiers: output formatting modifiers
    """
    from backend.services.composer_service import ComposerService

    cs = ComposerService()
    return {
        "agent_cores": cs.list_agent_cores(),
        "argumentation_patterns": cs.list_argumentation_patterns(),
        "tone_profiles": cs.list_tone_profiles(),
        "prompt_modifiers": cs.list_prompt_modifiers(),
    }


@router.get("/cost-estimate")
async def estimate_cost(
    llm_profile_id: str = Query(..., description="LLM profile ID"),
    num_agents: int = Query(4, description="Number of agents"),
    num_rounds: int = Query(3, description="Number of rounds"),
) -> dict:
    """Estimate the cost of a debate run."""
    cost = get_profile_service().estimate_debate_cost(
        llm_profile_id=llm_profile_id,
        num_agents=num_agents,
        num_rounds=num_rounds,
    )
    return {
        "llm_profile_id": llm_profile_id,
        "num_agents": num_agents,
        "num_rounds": num_rounds,
        "estimated_cost_usd": cost,
    }
