"""LLM Profiles CRUD router.

Extracted from ``backend.api.routers.blueprints`` to follow the
Single Responsibility Principle.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.models import BlueprintLLMProfile
from backend.blueprints.repository import BlueprintRepository

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


@router.get("", response_model=list[BlueprintLLMProfile])
def list_llm_profiles(
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[BlueprintLLMProfile]:
    """List all LLM profiles with pagination."""
    return repo.list_llm_profiles(limit=limit, offset=offset)


@router.get("/{profile_id}", response_model=BlueprintLLMProfile)
def get_llm_profile(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> BlueprintLLMProfile:
    """Get a single LLM profile by ID."""
    profile = repo.get_llm_profile(profile_id)
    _require_found("LLMProfile", profile, profile_id)
    return profile  # type: ignore[return-value]


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
