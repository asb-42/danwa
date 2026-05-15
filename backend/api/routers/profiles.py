"""Profile management API router.

Provides CRUD endpoints for LLM profiles, agent personas,
and prompt variants.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.config import is_service_llm_eligible, settings
from backend.core.profiles import AgentPersona, LLMProfile, PromptVariant
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
# Agent Personas
# ------------------------------------------------------------------


@router.get("/agents", response_model=list[AgentPersona])
async def list_agent_personas(
    role: str | None = Query(None, description="Filter by role"),
) -> list[AgentPersona]:
    """List all agent personas, optionally filtered by role."""
    return get_profile_service().list_agent_personas(role=role)


@router.get("/agents/{persona_id}", response_model=AgentPersona)
async def get_agent_persona(persona_id: str) -> AgentPersona:
    """Get a specific agent persona by ID."""
    persona = get_profile_service().get_agent_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Agent persona '{persona_id}' not found")
    return persona


@router.post("/agents", response_model=AgentPersona, status_code=201)
async def create_agent_persona(persona: AgentPersona) -> AgentPersona:
    """Create a new agent persona."""
    return get_profile_service().save_agent_persona(persona)


@router.put("/agents/{persona_id}", response_model=AgentPersona)
async def update_agent_persona(persona_id: str, persona: AgentPersona) -> AgentPersona:
    """Update an existing agent persona."""
    existing = get_profile_service().get_agent_persona(persona_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Agent persona '{persona_id}' not found")
    persona.id = persona_id
    return get_profile_service().save_agent_persona(persona)


@router.delete("/agents/{persona_id}")
async def delete_agent_persona(persona_id: str) -> dict:
    """Delete an agent persona."""
    if not get_profile_service().delete_agent_persona(persona_id):
        raise HTTPException(status_code=404, detail=f"Agent persona '{persona_id}' not found")
    return {"status": "ok", "deleted": persona_id}


# ------------------------------------------------------------------
# Prompt Variants
# ------------------------------------------------------------------


@router.get("/prompts", response_model=list[PromptVariant])
async def list_prompt_variants() -> list[PromptVariant]:
    """List all prompt variants."""
    return get_profile_service().list_prompt_variants()


class CreatePromptVariantRequest(BaseModel):
    """Request body for creating a prompt variant."""

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$", min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    prompts: dict[str, str] = Field(
        default_factory=dict,
        description='Role → prompt content mapping (e.g. {"strategist": "...", "critic": "..."})',
    )


@router.post("/prompts", response_model=PromptVariant, status_code=201)
async def create_prompt_variant(body: CreatePromptVariantRequest) -> PromptVariant:
    """Create a new prompt variant with per-role prompt content."""
    try:
        return get_profile_service().create_prompt_variant(
            variant_id=body.id,
            name=body.name,
            description=body.description,
            prompts=body.prompts,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/prompts/{variant_id}/preview")
async def preview_prompt_variant(
    variant_id: str,
    agent_role: str = Query(..., description="Agent role to preview"),
) -> dict:
    """Preview a prompt for a specific agent role."""
    try:
        text = get_profile_service().preview_prompt(variant_id, agent_role)
        return {"variant_id": variant_id, "agent_role": agent_role, "content": text}
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/prompts/{variant_id}")
async def delete_prompt_variant(variant_id: str) -> dict:
    """Delete a prompt variant."""
    if variant_id == "default":
        raise HTTPException(status_code=400, detail="Cannot delete the default prompt variant")
    if not get_profile_service().delete_prompt_variant(variant_id):
        raise HTTPException(status_code=404, detail=f"Prompt variant '{variant_id}' not found")
    return {"status": "ok", "deleted": variant_id}


class TranslatePromptRequest(BaseModel):
    """Request body for translating a prompt variant."""

    target_language: str = Field(..., description="Target language code (e.g. 'de')")
    force: bool = Field(default=False, description="Force re-translation")
    auto_approve: bool = Field(default=True, description="Auto-approve if quality meets threshold")


@router.post("/prompts/{variant_id}/translate")
async def translate_prompt_variant(variant_id: str, body: TranslatePromptRequest) -> dict:
    """Translate a prompt variant to a target language."""
    from backend.services.prompt_service import PromptService

    ps = PromptService()
    roles = ["strategist", "critic", "optimizer", "moderator"]
    results = []
    for role in roles:
        try:
            result = ps.translate_prompt(
                variant=variant_id,
                role=role,
                target_language=body.target_language,
                force=body.force,
                auto_approve=body.auto_approve,
            )
            results.append({"role": role, "status": result.get("status", "ok")})
        except Exception as exc:
            results.append({"role": role, "status": "error", "error": str(exc)})
    return {"variant_id": variant_id, "target_language": body.target_language, "results": results}


# ------------------------------------------------------------------
# Service LLM (Sprint 16)
# ------------------------------------------------------------------


@router.get("/llm/service-eligible")
async def list_service_eligible_llm_profiles() -> list[dict]:
    """List all LLM profiles eligible for service/background tasks."""
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


@router.get("/config/service-llm")
async def get_service_llm_config():
    """Get the current service LLM configuration."""
    return {
        "service_llm_profile_id": settings.service_llm_profile_id,
        "service_llm_min_context": settings.service_llm_min_context,
        "service_llm_blacklist": settings.service_llm_blacklist,
    }


class ServiceLLMRequest(BaseModel):
    """Request body for validating/changing service LLM."""

    profile_id: str


@router.post("/config/validate-service-llm")
async def validate_service_llm(body: ServiceLLMRequest):
    """Validate whether a given profile is suitable as service LLM."""
    ps = get_profile_service()
    profile = ps.get_llm_profile(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"LLM profile '{body.profile_id}' not found")
    eligible, reason = is_service_llm_eligible(profile)
    return {
        "profile_id": body.profile_id,
        "service_eligible": eligible,
        "reason": reason,
    }


@router.post("/config/service-llm")
async def set_service_llm(body: ServiceLLMRequest):
    """Set the service LLM profile (validated first)."""
    ps = get_profile_service()
    profile = ps.get_llm_profile(body.profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"LLM profile '{body.profile_id}' not found")
    eligible, reason = is_service_llm_eligible(profile)
    if not eligible:
        raise HTTPException(status_code=400, detail=f"Profile '{body.profile_id}' not eligible: {reason}")
    settings.service_llm_profile_id = body.profile_id
    logger.info("Service LLM changed to %s", body.profile_id)
    return {"status": "ok", "service_llm_profile_id": body.profile_id}


# ------------------------------------------------------------------
# Cost Estimation

# ------------------------------------------------------------------


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
