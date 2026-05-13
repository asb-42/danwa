"""Argumentation Patterns router.

Provides endpoints for listing and retrieving argumentation patterns
(philosophical/sachliche Ausrichtung templates for debate roles).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_blueprint_repository
from backend.blueprints.repository import BlueprintRepository

router = APIRouter()


@router.get("/argumentation-patterns", response_model=list[str])
def list_argumentation_patterns(
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[str]:
    """List all available argumentation pattern names."""
    patterns = repo.list_argumentation_patterns()
    return patterns


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
