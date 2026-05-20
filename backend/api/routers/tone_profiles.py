"""Blueprint Canvas — CRUD router for Tone Profiles.

Endpoints:
- GET    /api/v1/tone-profiles              — List all profiles
- GET    /api/v1/tone-profiles/{id}          — Get single profile
- POST   /api/v1/tone-profiles               — Create custom profile
- PUT    /api/v1/tone-profiles/{id}           — Update custom profile
- DELETE /api/v1/tone-profiles/{id}           — Delete custom profile
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintNotFoundError
from backend.blueprints.models import ToneProfile
from backend.blueprints.repository import BlueprintRepository
from backend.services.module_profile_sync import get_tone_profiles_from_modules

router = APIRouter()


# ------------------------------------------------------------------
# CRUD Endpoints
# ------------------------------------------------------------------


@router.get("")
def list_tone_profiles(
    include_system: bool = True,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[dict[str, Any]]:
    """List all tone profiles (system + custom + modules), filterable via include_system."""
    db_profiles = repo.list_tone_profiles(include_system=include_system, limit=limit, offset=offset)
    db_dicts = [p.model_dump() if hasattr(p, "model_dump") else p for p in db_profiles]
    module_profiles = get_tone_profiles_from_modules()

    seen_ids: set[str] = set()
    combined: list[dict[str, Any]] = []
    for entry in db_dicts + module_profiles:
        eid = entry.get("id")
        if eid not in seen_ids:
            seen_ids.add(eid)
            combined.append(entry)
    return combined


@router.get("/{profile_id}", response_model=ToneProfile)
def get_tone_profile_by_id(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> ToneProfile:
    """Get a single tone profile by ID — checks DB first, then modules."""
    profile = repo.get_tone_profile(profile_id)
    if profile is not None:
        return profile

    for mp in get_tone_profiles_from_modules():
        if mp.get("id") == profile_id:
            return ToneProfile(**{k: v for k, v in mp.items() if k in ToneProfile.model_fields})

    raise BlueprintNotFoundError("ToneProfile", profile_id)


@router.post("", response_model=ToneProfile, status_code=201)
def create_tone_profile(
    profile: ToneProfile,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> ToneProfile:
    """Create a new custom tone profile.

    ``is_system`` is always forced to ``False`` for API-created profiles.
    """
    existing = repo.get_tone_profile(profile.id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"ToneProfile '{profile.id}' already exists",
        )
    profile.is_system = False
    profile.created_at = datetime.now(UTC)
    profile.updated_at = datetime.now(UTC)
    repo.save_tone_profile(profile)
    return profile


@router.put("/{profile_id}", response_model=ToneProfile)
def update_tone_profile(
    profile_id: str,
    profile: ToneProfile,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> ToneProfile:
    """Update an existing tone profile.

    System profiles cannot be updated (HTTP 403).
    """
    existing = repo.get_tone_profile(profile_id)
    if existing is None:
        raise BlueprintNotFoundError("ToneProfile", profile_id)
    if existing.is_system:
        raise HTTPException(
            status_code=403,
            detail="System tone profiles cannot be modified",
        )
    profile.id = profile_id
    profile.is_system = False
    profile.updated_at = datetime.now(UTC)
    repo.save_tone_profile(profile)
    return profile


@router.delete("/{profile_id}")
def delete_tone_profile(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a tone profile.

    System profiles cannot be deleted (HTTP 403).
    """
    existing = repo.get_tone_profile(profile_id)
    if existing is None:
        raise BlueprintNotFoundError("ToneProfile", profile_id)
    if existing.is_system:
        raise HTTPException(
            status_code=403,
            detail="System tone profiles cannot be deleted",
        )
    repo.delete_tone_profile(profile_id)
    return {"status": "ok", "deleted": profile_id}
