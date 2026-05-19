"""LLM Profiles CRUD router.

Extracted from ``backend.api.routers.blueprints`` to follow the
Single Responsibility Principle.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.models import BlueprintLLMProfile
from backend.blueprints.repository import BlueprintRepository
from backend.services.module_profile_sync import get_llm_profiles_from_modules

router = APIRouter()


def _require_found(entity: str, obj: object, entity_id: str) -> None:
    """Raise BlueprintNotFoundError if obj is None."""
    if obj is None:
        raise BlueprintNotFoundError(entity, entity_id)


def _require_not_exists(repo: BlueprintRepository, entity: str, entity_id: str) -> None:
    """Raise BlueprintConflictError if an entity with the given ID already exists."""
    existing = repo.get_llm_profile(entity_id)
    if existing is not None:
        raise BlueprintConflictError(entity, entity_id)


@router.get("")
def list_llm_profiles(
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[dict[str, Any]]:
    """List all LLM profiles with pagination, including enabled module profiles."""
    db_profiles = repo.list_llm_profiles(limit=limit, offset=offset)
    db_dicts = [p.model_dump() if hasattr(p, "model_dump") else p for p in db_profiles]
    module_profiles = get_llm_profiles_from_modules()
    return db_dicts + module_profiles


@router.get("/{profile_id}", response_model=BlueprintLLMProfile)
def get_llm_profile(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> BlueprintLLMProfile:
    """Get a single LLM profile by ID (DB or module)."""
    profile = repo.get_llm_profile(profile_id)
    if profile:
        return profile  # type: ignore[return-value]
    # Fallback: check module profiles
    module_profiles = get_llm_profiles_from_modules()
    for mp in module_profiles:
        if mp.get("id") == profile_id:
            return BlueprintLLMProfile(
                id=mp["id"],
                name=mp["name"],
                provider=mp["provider"],
                model=mp["model"],
                api_base=mp.get("api_base"),
                api_key_env=mp.get("api_key_env", "OPENROUTER_API_KEY"),
                max_tokens=mp.get("max_tokens", 4096),
                context_window=mp.get("context_window"),
                temperature=mp.get("temperature", 0.7),
                timeout=mp.get("timeout", 600),
                cost_per_1k_input=mp.get("cost_per_1k_input", 0.0),
                cost_per_1k_output=mp.get("cost_per_1k_output", 0.0),
                is_active=mp.get("is_active", True),
                service_eligible=mp.get("service_eligible", True),
            )
    _require_found("LLMProfile", None, profile_id)


@router.post("", response_model=BlueprintLLMProfile, status_code=201)
def create_llm_profile(
    profile: BlueprintLLMProfile,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> BlueprintLLMProfile:
    """Create a new LLM profile."""
    _require_not_exists(repo, "LLMProfile", profile.id)
    repo.save_llm_profile(profile)
    return profile


@router.put("/{profile_id}", response_model=BlueprintLLMProfile)
def update_llm_profile(
    profile_id: str,
    profile: BlueprintLLMProfile,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> BlueprintLLMProfile:
    """Update an existing LLM profile."""
    existing = repo.get_llm_profile(profile_id)
    _require_found("LLMProfile", existing, profile_id)
    repo.save_llm_profile(profile)
    return profile


@router.delete("/{profile_id}")
def delete_llm_profile(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete an LLM profile."""
    deleted = repo.delete_llm_profile(profile_id)
    if not deleted:
        raise BlueprintNotFoundError("LLMProfile", profile_id)
    return {"status": "ok", "deleted": profile_id}
