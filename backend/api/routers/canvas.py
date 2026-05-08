"""Blueprint Canvas — CRUD router for Canvas Layouts.

Endpoints for managing canvas layout persistence (node positions, edges, viewport).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.models import CanvasLayout
from backend.blueprints.repository import BlueprintRepository

router = APIRouter()


def _require_found(entity: str, obj: object, entity_id: str) -> None:
    """Raise BlueprintNotFoundError if obj is None."""
    if obj is None:
        raise BlueprintNotFoundError(entity, entity_id)


@router.get("/layouts", response_model=list[CanvasLayout])
def list_layouts(
    project_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[CanvasLayout]:
    """List canvas layouts with optional project filter and pagination."""
    return repo.list_layouts(project_id=project_id, limit=limit, offset=offset)


@router.get("/layouts/{layout_id}", response_model=CanvasLayout)
def get_layout(
    layout_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> CanvasLayout:
    """Get a single canvas layout by ID."""
    layout = repo.get_layout(layout_id)
    _require_found("CanvasLayout", layout, layout_id)
    return layout  # type: ignore[return-value]


@router.post("/layouts", response_model=CanvasLayout, status_code=201)
def create_layout(
    layout: CanvasLayout,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> CanvasLayout:
    """Create a new canvas layout."""
    existing = repo.get_layout(layout.id)
    if existing is not None:
        raise BlueprintConflictError("CanvasLayout", layout.id)
    repo.save_layout(layout)
    return layout


@router.put("/layouts/{layout_id}", response_model=CanvasLayout)
def update_layout(
    layout_id: str,
    layout: CanvasLayout,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> CanvasLayout:
    """Update an existing canvas layout."""
    existing = repo.get_layout(layout_id)
    _require_found("CanvasLayout", existing, layout_id)
    repo.save_layout(layout)
    return layout


@router.delete("/layouts/{layout_id}")
def delete_layout(
    layout_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a canvas layout."""
    deleted = repo.delete_layout(layout_id)
    if not deleted:
        raise BlueprintNotFoundError("CanvasLayout", layout_id)
    return {"status": "ok", "deleted": layout_id}
