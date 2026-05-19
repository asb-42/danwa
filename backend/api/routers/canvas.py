"""Blueprint Canvas — CRUD router for Canvas Layouts.

Endpoints for managing canvas layout persistence (node positions, edges, viewport),
and converting layouts to executable WorkflowDefinitions.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.canvas_to_workflow import CanvasToWorkflowConverter, ConversionError
from backend.blueprints.models import CanvasLayout
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import WorkflowDefinition

logger = logging.getLogger(__name__)

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
    # Ensure the layout uses the URL's ID, not a newly generated one
    layout.id = layout_id
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


# ---------------------------------------------------------------------------
# Canvas → Workflow conversion
# ---------------------------------------------------------------------------


class ConvertToWorkflowRequest(BaseModel):
    """Request body for converting a canvas layout to a workflow definition."""

    name: str | None = Field(
        default=None,
        description="Workflow name (defaults to layout name)",
    )
    description: str = Field(
        default="",
        description="Optional workflow description",
    )
    max_rounds: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Default max rounds for termination condition",
    )
    consensus_threshold: float = Field(
        default=0.9,
        ge=0.0,
        le=1.0,
        description="Default consensus threshold for termination condition",
    )


@router.post(
    "/layouts/{layout_id}/to-workflow",
    response_model=WorkflowDefinition,
    status_code=201,
)
def convert_layout_to_workflow(
    layout_id: str,
    body: ConvertToWorkflowRequest | None = None,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Convert a canvas layout to a WorkflowDefinition and persist it.

    Takes the canvas layout's ``layout_data`` (nodes + edges with positions)
    and transforms it into a structured ``WorkflowDefinition`` with typed
    nodes, edges, entry point, and termination conditions.

    The resulting WorkflowDefinition is saved to the repository and can then
    be compiled and executed via ``POST /workflow-exec/{wf_id}/start``.
    """
    layout = repo.get_layout(layout_id)
    _require_found("CanvasLayout", layout, layout_id)

    params = body or ConvertToWorkflowRequest()

    try:
        converter = CanvasToWorkflowConverter(repo)
        wf = converter.convert(
            layout=layout,  # type: ignore[arg-type]
            name=params.name,
            description=params.description,
            max_rounds=params.max_rounds,
            consensus_threshold=params.consensus_threshold,
        )
    except ConversionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # Check if a workflow already exists for this layout — update instead of duplicate
    existing_wfs = repo.list_workflow_definitions(limit=100)
    for existing in existing_wfs:
        if existing.canvas_layout_id == layout_id:
            # Update existing workflow
            wf.id = existing.id
            wf.version = existing.version + 1
            wf.created_at = existing.created_at
            logger.info(
                "Updating existing workflow '%s' from layout '%s' (v%d → v%d)",
                existing.id,
                layout_id,
                existing.version,
                wf.version,
            )
            repo.save_workflow_definition(wf)
            return wf

    # Create new workflow
    repo.save_workflow_definition(wf)
    logger.info("Created new workflow '%s' from layout '%s'", wf.id, layout_id)
    return wf
