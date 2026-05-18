"""Argumentation Patterns router.

Provides endpoints for listing and retrieving argumentation patterns
(philosophical/sachliche Ausrichtung templates for debate roles).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_blueprint_repository
from backend.blueprints.repository import BlueprintRepository
from backend.services.module_profile_sync import get_argumentation_patterns_from_modules

router = APIRouter()


@router.get("/argumentation-patterns", response_model=list[str])
def list_argumentation_patterns(
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[str]:
    """List all available argumentation pattern names, including enabled module patterns."""
    db_patterns = repo.list_argumentation_patterns()
    module_patterns = get_argumentation_patterns_from_modules()
    # Merge and deduplicate
    return sorted(set(db_patterns) | set(module_patterns))


@router.get("/argumentation-patterns/{name}", response_model=dict)
def get_argumentation_pattern(
    name: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Get all role prompts for a given argumentation pattern.

    Returns a mapping of role_type_id → prompt content string.
    """
    result = repo.get_argumentation_pattern(name)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Argumentation pattern '{name}' not found",
        )
    return result
