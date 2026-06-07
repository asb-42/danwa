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

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintNotFoundError
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    WorkflowDefinition,
    WorkflowTemplate,
)
from backend.services.module_profile_sync import get_workflow_templates_from_modules

logger = logging.getLogger(__name__)

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


@router.get("")
def list_workflow_templates(
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[dict[str, Any]]:
    """List all workflow templates (system + custom + modules), filterable by category."""
    db_templates = repo.list_workflow_templates(category=category, limit=limit, offset=offset)
    db_dicts = [t.model_dump() if hasattr(t, "model_dump") else t for t in db_templates]
    module_templates = get_workflow_templates_from_modules()
    if category:
        module_templates = [t for t in module_templates if t.get("category") == category]
    # Deduplicate: DB templates take precedence over module templates
    db_ids = {t.get("id") for t in db_dicts}
    unique_modules = [t for t in module_templates if t.get("id") not in db_ids]
    return db_dicts + unique_modules


@router.get("/{template_id}", response_model=WorkflowTemplate)
def get_workflow_template(
    template_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowTemplate:
    """Get a single workflow template by ID.

    Falls back to module workflow templates if not found in the DB.
    """
    template = repo.get_workflow_template(template_id)
    if template is None:
        # Check module workflow templates
        for mt in get_workflow_templates_from_modules():
            if mt.get("id") == template_id:
                return WorkflowTemplate(**mt)
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
    2. Resolve default_role placeholders from installed agent cores.
    3. Check for missing required placeholders.
    4. Merge defaults and instantiate.
    5. Validate blueprint_ref placeholders against the catalog.
    6. Validate the resulting graph structure.
    7. Create and persist a new WorkflowDefinition.
    """
    template = repo.get_workflow_template(template_id)
    if template is None:
        raise BlueprintNotFoundError("WorkflowTemplate", template_id)

    # --- Step 1: Load agent cores from modules (for role resolution + validation) ---
    _agent_cores_by_role: dict[str, list[dict[str, Any]]] = {}
    _agent_cores_by_id: dict[str, dict[str, Any]] = {}
    try:
        from backend.services.module_profile_sync import get_agent_personas_from_modules

        for mp in get_agent_personas_from_modules():
            _agent_cores_by_id[mp.get("id", "")] = mp
            role = mp.get("role", "")
            if role:
                _agent_cores_by_role.setdefault(role, []).append(mp)
    except Exception:
        pass

    # --- Step 2: Resolve default_role placeholders ---
    placeholder_values = dict(body.placeholder_values)
    for ph in template.placeholders:
        if ph.default_role and ph.key not in placeholder_values:
            role_cores = _agent_cores_by_role.get(ph.default_role, [])
            if role_cores:
                # Prefer cores tagged "default" or with "en" in language
                best = role_cores[0]
                for core in role_cores:
                    tags = core.get("tags", [])
                    if "default" in tags:
                        best = core
                        break
                placeholder_values[ph.key] = best.get("id", "")
            # If no core found for role, leave it missing — will be caught in step 3

    # --- Step 3: Check for missing required placeholders ---
    required_keys = {p.key for p in template.placeholders if p.default is None and p.default_role is None}
    provided = set(placeholder_values.keys())
    missing = required_keys - provided
    # Also check default_role placeholders that couldn't be resolved
    for ph in template.placeholders:
        if ph.default_role and ph.key not in placeholder_values:
            missing.add(ph.key)
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "missing_placeholders",
                "missing": sorted(missing),
                "message": f"Missing required placeholder values: {', '.join(sorted(missing))}",
            },
        )

    # --- Step 4: Merge defaults and instantiate ---
    try:
        resolved_data = template.instantiate(placeholder_values)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # --- Step 5: Validate blueprint_ref placeholders ---
    for ph in template.placeholders:
        if ph.type == "blueprint_ref":
            value = placeholder_values.get(ph.key, ph.default)
            if value is not None:
                value_str = str(value)
                bp = repo.get_blueprint(value_str)
                if bp is None and value_str not in _agent_cores_by_id:
                    raise HTTPException(
                        status_code=422,
                        detail={
                            "error": "invalid_blueprint_ref",
                            "placeholder": ph.key,
                            "value": value_str,
                            "message": f"AgentBlueprint or Agent Core '{value_str}' not found for placeholder '{ph.key}'",
                        },
                    )

    # --- Step 6: Build WorkflowDefinition ---
    now = datetime.now(UTC)
    wf_name = body.name or f"{template.name} – {now.strftime('%Y-%m-%d %H:%M')}"

    # Extract phase_configs from resolved template data.
    # Template format: {"phase-1": {"name": "...", "color": "...", ...}, ...}
    # PhaseConfig expects: phase_node_id (from key), name, color, description, roles, max_rounds
    phase_configs: dict[str, Any] = {}
    raw_phase_configs = resolved_data.get("phase_configs", {})
    if raw_phase_configs:
        from backend.blueprints.workflow_models import PhaseConfig

        for phase_node_id, pc_data in raw_phase_configs.items():
            if isinstance(pc_data, dict):
                try:
                    phase_configs[phase_node_id] = PhaseConfig(
                        phase_node_id=phase_node_id,
                        name=pc_data.get("name", "Phase"),
                        description=pc_data.get("description", ""),
                        roles=pc_data.get("roles", []),
                        max_rounds=pc_data.get("max_rounds", 3),
                        color=pc_data.get("color", "#6366f1"),
                    )
                except Exception:
                    logger.warning("Failed to parse PhaseConfig for '%s'", phase_node_id, exc_info=True)

    try:
        wf = WorkflowDefinition(
            id=str(uuid.uuid4())[:8],
            name=wf_name,
            description=f"Instantiated from template: {template.name}",
            nodes=resolved_data.get("nodes", []),
            edges=resolved_data.get("edges", []),
            entry_point=resolved_data.get("entry_point"),
            termination_conditions=resolved_data.get("termination_conditions", []),
            phase_configs=phase_configs,
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
