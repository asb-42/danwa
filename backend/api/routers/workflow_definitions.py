"""Workflow Definitions CRUD router.

Extracted from ``backend.api.routers.blueprints`` to follow the
Single Responsibility Principle.  Includes workflow CRUD, compilation,
cloning, and save-as-template.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.compiler import CompilationResult, CompilerService
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import WorkflowDefinition, WorkflowTemplate

router = APIRouter()


def _require_found(entity: str, obj: object, entity_id: str) -> None:
    """Raise BlueprintNotFoundError if obj is None."""
    if obj is None:
        raise BlueprintNotFoundError(entity, entity_id)


def _require_not_exists(repo: BlueprintRepository, entity_id: str) -> None:
    """Raise BlueprintConflictError if a workflow with the given ID already exists."""
    existing = repo.get_workflow_definition(entity_id)
    if existing is not None:
        raise BlueprintConflictError("WorkflowDefinition", entity_id)


@router.get("", response_model=list[WorkflowDefinition])
def list_workflow_definitions(
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[WorkflowDefinition]:
    """List all workflow definitions with pagination."""
    return repo.list_workflow_definitions(limit=limit, offset=offset)


@router.get("/{wf_id}", response_model=WorkflowDefinition)
def get_workflow_definition(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Get a single workflow definition by ID."""
    wf = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", wf, wf_id)
    return wf  # type: ignore[return-value]


@router.post("", response_model=WorkflowDefinition, status_code=201)
def create_workflow_definition(
    wf: WorkflowDefinition,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Create a new workflow definition."""
    _require_not_exists(repo, wf.id)
    repo.save_workflow_definition(wf)
    return wf


@router.put("/{wf_id}", response_model=WorkflowDefinition)
def update_workflow_definition(
    wf_id: str,
    wf: WorkflowDefinition,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Update an existing workflow definition."""
    existing = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", existing, wf_id)
    repo.save_workflow_definition(wf)
    return wf


@router.delete("/{wf_id}")
def delete_workflow_definition(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a workflow definition."""
    deleted = repo.delete_workflow_definition(wf_id)
    if not deleted:
        raise BlueprintNotFoundError("WorkflowDefinition", wf_id)
    return {"status": "ok", "deleted": wf_id}


@router.post("/{wf_id}/compile", response_model=CompilationResult)
def compile_workflow(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> CompilationResult:
    """Compile a workflow definition — validate blueprint references."""
    wf = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", wf, wf_id)
    compiler = CompilerService(repo)
    return compiler.compile(wf)  # type: ignore[arg-type]


@router.post("/{wf_id}/clone", response_model=WorkflowDefinition, status_code=201)
def clone_workflow(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Clone a workflow definition.

    Creates a deep copy with a new ID, incremented version, and
    ``is_locked=False``.
    """
    original = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", original, wf_id)

    cloned = original.model_copy(deep=True)
    cloned.id = str(uuid.uuid4())[:8]
    cloned.name = f"{original.name} (Copy)"
    cloned.version = original.version + 1
    cloned.is_locked = False
    cloned.is_active = True
    cloned.created_at = datetime.now(UTC)
    cloned.updated_at = datetime.now(UTC)

    repo.save_workflow_definition(cloned)
    return cloned


@router.post(
    "/{wf_id}/save-as-template",
    response_model=WorkflowTemplate,
    status_code=201,
)
def save_workflow_as_template(
    wf_id: str,
    body: dict | None = None,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowTemplate:
    """Create a custom template from an existing WorkflowDefinition.

    Request body: ``{"name": "...", "description": "...", "extracted_placeholders": ["key1"]}``

    Fields listed in ``extracted_placeholders`` are replaced with
    ``{{key}}`` placeholders in the template data.
    """
    wf = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", wf, wf_id)

    name = (body or {}).get("name", f"Template from {wf.name}")
    description = (body or {}).get("description", "")
    extracted_keys = (body or {}).get("extracted_placeholders", [])

    wf_data = json.loads(wf.model_dump_json())

    for key in [
        "id",
        "name",
        "description",
        "canvas_layout_id",
        "tags",
        "is_active",
        "created_at",
        "updated_at",
        "template_id",
        "version",
        "is_locked",
    ]:
        wf_data.pop(key, None)

    placeholders: list[dict] = []
    for pkey in extracted_keys:
        value = _find_value_in_dict(wf_data, pkey)
        if value is not None:
            raw = json.dumps(wf_data, default=str)
            raw = raw.replace(json.dumps(value, default=str), '"{{' + pkey + '}}"')
            wf_data = json.loads(raw)

            ph_type = "string"
            if isinstance(value, int):
                ph_type = "integer"
            elif isinstance(value, float):
                ph_type = "float"
            if "blueprint" in pkey.lower():
                ph_type = "blueprint_ref"

            placeholders.append(
                {
                    "key": pkey,
                    "type": ph_type,
                    "description": f"Extracted from workflow field: {pkey}",
                }
            )

    now = datetime.now(UTC)

    template = WorkflowTemplate(
        id=f"tpl-{str(uuid.uuid4())[:8]}",
        name=name,
        description=description,
        category="custom",
        template_data=wf_data,
        placeholders=placeholders,
        is_system=False,
        source_workflow_id=wf_id,
        created_at=now,
        updated_at=now,
    )

    repo.save_workflow_template(template)
    return template


def _find_value_in_dict(data: object, key: str) -> str | int | float | None:
    """Recursively search for a key in nested dict/list and return its value."""
    if isinstance(data, dict):
        if key in data:
            return data[key]  # type: ignore[return-value]
        for v in data.values():
            result = _find_value_in_dict(v, key)
            if result is not None:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _find_value_in_dict(item, key)
            if result is not None:
                return result
    return None
