"""Blueprint Canvas — CRUD + instantiation router for Workflow Templates.

Endpoints:
- GET    /api/v1/workflow-templates              — List all templates
- GET    /api/v1/workflow-templates/{id}          — Get single template
- POST   /api/v1/workflow-templates               — Create custom template
- PUT    /api/v1/workflow-templates/{id}           — Update custom template
- DELETE /api/v1/workflow-templates/{id}           — Delete custom template
- POST   /api/v1/workflow-templates/{id}/instantiate — Instantiate template
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintNotFoundError
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    WorkflowDefinition,
    WorkflowTemplate,
)

router = APIRouter()


# ------------------------------------------------------------------
# Request / Response schemas
# ------------------------------------------------------------------


class InstantiateRequest(BaseModel):
    """Request body for template instantiation."""

    name: str | None = None
    placeholder_values: dict[str, str | int | float] = Field(default_factory=dict)


# ------------------------------------------------------------------
# CRUD Endpoints
# ------------------------------------------------------------------


@router.get("", response_model=list[WorkflowTemplate])
def list_workflow_templates(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[WorkflowTemplate]:
    """List all workflow templates (system + custom), filterable by category."""
    return repo.list_workflow_templates(category=category, limit=limit, offset=offset)


@router.get("/{template_id}", response_model=WorkflowTemplate)
def get_workflow_template(
    template_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowTemplate:
    """Get a single workflow template by ID."""
    template = repo.get_workflow_template(template_id)
    if template is None:
        raise BlueprintNotFoundError("WorkflowTemplate", template_id)
    return template


@router.post("", response_model=WorkflowTemplate, status_code=201)
def create_workflow_template(
    template: WorkflowTemplate,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowTemplate:
    """Create a new custom workflow template.

    ``is_system`` is always forced to ``False`` for API-created templates.
    """
    existing = repo.get_workflow_template(template.id)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"WorkflowTemplate '{template.id}' already exists",
        )
    template.is_system = False
    template.category = "custom"
    repo.save_workflow_template(template)
    return template


@router.put("/{template_id}", response_model=WorkflowTemplate)
def update_workflow_template(
    template_id: str,
    template: WorkflowTemplate,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowTemplate:
    """Update an existing workflow template.

    System templates cannot be updated (HTTP 403).
    """
    existing = repo.get_workflow_template(template_id)
    if existing is None:
        raise BlueprintNotFoundError("WorkflowTemplate", template_id)
    if existing.is_system:
        raise HTTPException(
            status_code=403,
            detail="System templates cannot be modified",
        )
    template.id = template_id
    template.is_system = False
    template.updated_at = datetime.now(UTC)
    repo.save_workflow_template(template)
    return template


@router.delete("/{template_id}")
def delete_workflow_template(
    template_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a workflow template.

    System templates cannot be deleted (HTTP 403).
    """
    existing = repo.get_workflow_template(template_id)
    if existing is None:
        raise BlueprintNotFoundError("WorkflowTemplate", template_id)
    if existing.is_system:
        raise HTTPException(
            status_code=403,
            detail="System templates cannot be deleted",
        )
    repo.delete_workflow_template(template_id)
    return {"status": "ok", "deleted": template_id}


# ------------------------------------------------------------------
# Instantiation Endpoint
# ------------------------------------------------------------------


@router.post("/{template_id}/instantiate", response_model=WorkflowDefinition, status_code=201)
def instantiate_workflow_template(
    template_id: str,
    body: InstantiateRequest,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Instantiate a workflow template into a concrete WorkflowDefinition.

    1. Load the template.
    2. Replace all {{key}} placeholders with provided values.
    3. Validate blueprint_ref placeholders against the catalog.
    4. Validate the resulting graph structure.
    5. Create and persist a new WorkflowDefinition.
    """
    template = repo.get_workflow_template(template_id)
    if template is None:
        raise BlueprintNotFoundError("WorkflowTemplate", template_id)

    # --- Step 1: Check for missing placeholders ---
    required_keys = {p.key for p in template.placeholders if p.default is None}
    provided = set(body.placeholder_values.keys())
    missing = required_keys - provided
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "missing_placeholders",
                "missing": sorted(missing),
                "message": f"Missing required placeholder values: {', '.join(sorted(missing))}",
            },
        )

    # --- Step 2: Merge defaults and instantiate ---
    try:
        resolved_data = template.instantiate(body.placeholder_values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # --- Step 3: Validate blueprint_ref placeholders ---
    for ph in template.placeholders:
        if ph.type == "blueprint_ref":
            value = body.placeholder_values.get(ph.key, ph.default)
            if value is not None:
                bp = repo.get_blueprint(str(value))
                if bp is None:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": "invalid_blueprint_ref",
                            "placeholder": ph.key,
                            "value": str(value),
                            "message": f"AgentBlueprint '{value}' not found for placeholder '{ph.key}'",
                        },
                    )

    # --- Step 4: Build WorkflowDefinition ---
    now = datetime.now(UTC)
    wf_name = body.name or f"{template.name} – {now.strftime('%Y-%m-%d %H:%M')}"

    try:
        wf = WorkflowDefinition(
            id=str(uuid.uuid4())[:8],
            name=wf_name,
            description=f"Instantiated from template: {template.name}",
            nodes=resolved_data.get("nodes", []),
            edges=resolved_data.get("edges", []),
            entry_point=resolved_data.get("entry_point"),
            termination_conditions=resolved_data.get("termination_conditions", []),
            template_id=template_id,
            created_at=now,
            updated_at=now,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_workflow",
                "message": f"Instantiated template produces invalid workflow: {exc}",
            },
        )

    # --- Step 5: Persist ---
    repo.save_workflow_definition(wf)
    return wf
