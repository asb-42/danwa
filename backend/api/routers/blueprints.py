"""Blueprint Canvas — CRUD router for Blueprint entities.

Endpoints for LLM Profiles, Prompt Templates, Role Definitions,
Agent Blueprints, Workflow Definitions, and the bulk import trigger.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.compiler import CompilationResult, CompilerService
from backend.blueprints.importer import BlueprintImporter, ImportResult
from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
    PromptTemplate,
    RoleDefinition,
    RoleType,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import WorkflowDefinition, WorkflowTemplate

router = APIRouter()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _require_found(entity: str, obj: object, entity_id: str) -> None:
    """Raise BlueprintNotFoundError if obj is None."""
    if obj is None:
        raise BlueprintNotFoundError(entity, entity_id)


def _require_not_exists(repo: BlueprintRepository, entity: str, entity_id: str) -> None:
    """Raise BlueprintConflictError if an entity with the given ID already exists."""
    existing = None
    if entity == "LLMProfile":
        existing = repo.get_llm_profile(entity_id)
    elif entity == "PromptTemplate":
        existing = repo.get_prompt_template(entity_id)
    elif entity == "RoleDefinition":
        existing = repo.get_role_definition(entity_id)
    elif entity == "RoleType":
        existing = repo.get_role_type(entity_id)
    elif entity == "AgentBlueprint":
        existing = repo.get_blueprint(entity_id)
    elif entity == "WorkflowDefinition":
        existing = repo.get_workflow_definition(entity_id)
    if existing is not None:
        raise BlueprintConflictError(entity, entity_id)


# ==================================================================
# LLM Profiles
# ==================================================================


@router.get("/llm-profiles", response_model=list[BlueprintLLMProfile])
def list_llm_profiles(
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[BlueprintLLMProfile]:
    """List all LLM profiles with pagination."""
    return repo.list_llm_profiles(limit=limit, offset=offset)


@router.get("/llm-profiles/{profile_id}", response_model=BlueprintLLMProfile)
def get_llm_profile(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> BlueprintLLMProfile:
    """Get a single LLM profile by ID."""
    profile = repo.get_llm_profile(profile_id)
    _require_found("LLMProfile", profile, profile_id)
    return profile  # type: ignore[return-value]


@router.post("/llm-profiles", response_model=BlueprintLLMProfile, status_code=201)
def create_llm_profile(
    profile: BlueprintLLMProfile,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> BlueprintLLMProfile:
    """Create a new LLM profile."""
    _require_not_exists(repo, "LLMProfile", profile.id)
    repo.save_llm_profile(profile)
    return profile


@router.put("/llm-profiles/{profile_id}", response_model=BlueprintLLMProfile)
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


@router.delete("/llm-profiles/{profile_id}")
def delete_llm_profile(
    profile_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete an LLM profile."""
    deleted = repo.delete_llm_profile(profile_id)
    if not deleted:
        raise BlueprintNotFoundError("LLMProfile", profile_id)
    return {"status": "ok", "deleted": profile_id}


# ==================================================================
# Prompt Templates
# ==================================================================


@router.get("/prompt-templates", response_model=list[PromptTemplate])
def list_prompt_templates(
    role: str | None = None,
    variant: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[PromptTemplate]:
    """List prompt templates with optional filtering and pagination."""
    return repo.list_prompt_templates(role=role, variant=variant, limit=limit, offset=offset)


@router.get("/prompt-templates/{template_id}", response_model=PromptTemplate)
def get_prompt_template(
    template_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> PromptTemplate:
    """Get a single prompt template by ID."""
    template = repo.get_prompt_template(template_id)
    _require_found("PromptTemplate", template, template_id)
    return template  # type: ignore[return-value]


@router.post("/prompt-templates", response_model=PromptTemplate, status_code=201)
def create_prompt_template(
    template: PromptTemplate,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> PromptTemplate:
    """Create a new prompt template."""
    _require_not_exists(repo, "PromptTemplate", template.id)
    repo.save_prompt_template(template)
    return template


@router.put("/prompt-templates/{template_id}", response_model=PromptTemplate)
def update_prompt_template(
    template_id: str,
    template: PromptTemplate,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> PromptTemplate:
    """Update an existing prompt template."""
    existing = repo.get_prompt_template(template_id)
    _require_found("PromptTemplate", existing, template_id)
    repo.save_prompt_template(template)
    return template


@router.delete("/prompt-templates/{template_id}")
def delete_prompt_template(
    template_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a prompt template."""
    deleted = repo.delete_prompt_template(template_id)
    if not deleted:
        raise BlueprintNotFoundError("PromptTemplate", template_id)
    return {"status": "ok", "deleted": template_id}


# ==================================================================
# Role Definitions
# ==================================================================


@router.get("/role-definitions", response_model=list[RoleDefinition])
def list_role_definitions(
    role: str | None = None,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[RoleDefinition]:
    """List role definitions with optional filtering and pagination."""
    return repo.list_role_definitions(role=role, limit=limit, offset=offset)


@router.get("/role-definitions/{role_id}", response_model=RoleDefinition)
def get_role_definition(
    role_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> RoleDefinition:
    """Get a single role definition by ID."""
    role_def = repo.get_role_definition(role_id)
    _require_found("RoleDefinition", role_def, role_id)
    return role_def  # type: ignore[return-value]


@router.post("/role-definitions", response_model=RoleDefinition, status_code=201)
def create_role_definition(
    role_def: RoleDefinition,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> RoleDefinition:
    """Create a new role definition."""
    _require_not_exists(repo, "RoleDefinition", role_def.id)
    repo.save_role_definition(role_def)
    return role_def


@router.put("/role-definitions/{role_id}", response_model=RoleDefinition)
def update_role_definition(
    role_id: str,
    role_def: RoleDefinition,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> RoleDefinition:
    """Update an existing role definition."""
    existing = repo.get_role_definition(role_id)
    _require_found("RoleDefinition", existing, role_id)
    repo.save_role_definition(role_def)
    return role_def


@router.delete("/role-definitions/{role_id}")
def delete_role_definition(
    role_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a role definition."""
    deleted = repo.delete_role_definition(role_id)
    if not deleted:
        raise BlueprintNotFoundError("RoleDefinition", role_id)
    return {"status": "ok", "deleted": role_id}


# ==================================================================
# Agent Blueprints
# ==================================================================


@router.get("/agent-blueprints", response_model=list[AgentBlueprint])
def list_agent_blueprints(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[AgentBlueprint]:
    """List agent blueprints with optional active-only filter and pagination."""
    return repo.list_blueprints(active_only=active_only, limit=limit, offset=offset)


@router.get("/agent-blueprints/{blueprint_id}", response_model=AgentBlueprint)
def get_agent_blueprint(
    blueprint_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBlueprint:
    """Get a single agent blueprint by ID."""
    bp = repo.get_blueprint(blueprint_id)
    _require_found("AgentBlueprint", bp, blueprint_id)
    return bp  # type: ignore[return-value]


@router.post("/agent-blueprints", response_model=AgentBlueprint, status_code=201)
def create_agent_blueprint(
    blueprint: AgentBlueprint,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBlueprint:
    """Create a new agent blueprint."""
    _require_not_exists(repo, "AgentBlueprint", blueprint.id)
    repo.save_blueprint(blueprint)
    return blueprint


@router.put("/agent-blueprints/{blueprint_id}", response_model=AgentBlueprint)
def update_agent_blueprint(
    blueprint_id: str,
    blueprint: AgentBlueprint,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBlueprint:
    """Update an existing agent blueprint."""
    existing = repo.get_blueprint(blueprint_id)
    _require_found("AgentBlueprint", existing, blueprint_id)
    repo.save_blueprint(blueprint)
    return blueprint


@router.delete("/agent-blueprints/{blueprint_id}")
def delete_agent_blueprint(
    blueprint_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete an agent blueprint."""
    deleted = repo.delete_blueprint(blueprint_id)
    if not deleted:
        raise BlueprintNotFoundError("AgentBlueprint", blueprint_id)
    return {"status": "ok", "deleted": blueprint_id}


# ==================================================================
# Role Types
# ==================================================================


@router.get("/role-types", response_model=list[RoleType])
def list_role_types(
    limit: int = 100,
    offset: int = 0,
    active_only: bool = False,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[RoleType]:
    """List all role types with pagination."""
    return repo.list_role_types(limit=limit, offset=offset, active_only=active_only)


@router.get("/role-types/{role_type_id}", response_model=RoleType)
def get_role_type(
    role_type_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> RoleType:
    """Get a single role type by ID."""
    rt = repo.get_role_type(role_type_id)
    _require_found("RoleType", rt, role_type_id)
    return rt


@router.post("/role-types", response_model=RoleType, status_code=201)
def create_role_type(
    role_type: RoleType,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> RoleType:
    """Create a new role type."""
    _require_not_exists(repo, "RoleType", role_type.id)
    repo.save_role_type(role_type)
    return role_type


@router.put("/role-types/{role_type_id}", response_model=RoleType)
def update_role_type(
    role_type_id: str,
    role_type: RoleType,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> RoleType:
    """Update an existing role type."""
    existing = repo.get_role_type(role_type_id)
    _require_found("RoleType", existing, role_type_id)
    repo.save_role_type(role_type)
    return role_type


@router.delete("/role-types/{role_type_id}")
def delete_role_type(
    role_type_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a role type."""
    deleted = repo.delete_role_type(role_type_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"RoleType '{role_type_id}' not found")
    return {"status": "ok", "deleted": role_type_id}


# ==================================================================
# Workflow Definitions
# ==================================================================


class SaveAsTemplateRequest:
    """Request body for saving a workflow as a template."""

    def __init__(self, name: str, description: str = "", extracted_placeholders: list[str] | None = None) -> None:
        self.name = name
        self.description = description
        self.extracted_placeholders = extracted_placeholders or []




@router.get("/workflows", response_model=list[WorkflowDefinition])
def list_workflow_definitions(
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[WorkflowDefinition]:
    """List all workflow definitions with pagination."""
    return repo.list_workflow_definitions(limit=limit, offset=offset)


@router.get("/workflows/{wf_id}", response_model=WorkflowDefinition)
def get_workflow_definition(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Get a single workflow definition by ID."""
    wf = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", wf, wf_id)
    return wf  # type: ignore[return-value]


@router.post("/workflows", response_model=WorkflowDefinition, status_code=201)
def create_workflow_definition(
    wf: WorkflowDefinition,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Create a new workflow definition."""
    _require_not_exists(repo, "WorkflowDefinition", wf.id)
    repo.save_workflow_definition(wf)
    return wf


@router.put("/workflows/{wf_id}", response_model=WorkflowDefinition)
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


@router.delete("/workflows/{wf_id}")
def delete_workflow_definition(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete a workflow definition."""
    deleted = repo.delete_workflow_definition(wf_id)
    if not deleted:
        raise BlueprintNotFoundError("WorkflowDefinition", wf_id)
    return {"status": "ok", "deleted": wf_id}


@router.post("/workflows/{wf_id}/compile", response_model=CompilationResult)
def compile_workflow(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> CompilationResult:
    """Compile a workflow definition — validate blueprint references."""
    wf = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", wf, wf_id)
    compiler = CompilerService(repo)
    return compiler.compile(wf)  # type: ignore[arg-type]


@router.post("/workflows/{wf_id}/clone", response_model=WorkflowDefinition, status_code=201)
def clone_workflow(
    wf_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> WorkflowDefinition:
    """Clone a workflow definition.

    Creates a deep copy with a new ID, incremented version, and
    ``is_locked=False``.
    """
    import copy
    import uuid

    original = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", original, wf_id)

    # Deep copy and assign new identity
    cloned = original.model_copy(deep=True)
    cloned.id = str(uuid.uuid4())[:8]
    cloned.name = f"{original.name} (Copy)"
    cloned.version = original.version + 1
    cloned.is_locked = False
    cloned.is_active = True

    from datetime import UTC, datetime

    cloned.created_at = datetime.now(UTC)
    cloned.updated_at = datetime.now(UTC)

    repo.save_workflow_definition(cloned)
    return cloned


@router.post(
    "/workflows/{wf_id}/save-as-template",
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
    from backend.blueprints.workflow_models import WorkflowTemplate

    wf = repo.get_workflow_definition(wf_id)
    _require_found("WorkflowDefinition", wf, wf_id)

    name = (body or {}).get("name", f"Template from {wf.name}")
    description = (body or {}).get("description", "")
    extracted_keys = (body or {}).get("extracted_placeholders", [])

    # Serialize workflow to dict
    wf_data = json.loads(wf.model_dump_json())

    # Remove metadata fields that don't belong in template_data
    for key in [
        "id", "name", "description", "canvas_layout_id", "tags",
        "is_active", "created_at", "updated_at", "template_id",
        "version", "is_locked",
    ]:
        wf_data.pop(key, None)

    # Extract placeholders: replace concrete values with {{key}}
    from backend.blueprints.workflow_models import WorkflowTemplate as _WT

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

            placeholders.append({
                "key": pkey,
                "type": ph_type,
                "description": f"Extracted from workflow field: {pkey}",
            })

    import uuid as _uuid
    from datetime import UTC, datetime
    now = datetime.now(UTC)

    template = WorkflowTemplate(
        id=f"tpl-{str(_uuid.uuid4())[:8]}",
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


# ==================================================================
# Import
# ==================================================================


class ImportRequest:
    """Request body for the import endpoint."""

    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run


@router.post("/import", response_model=ImportResult)
def run_import(
    body: dict | None = None,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> ImportResult:
    """Trigger an idempotent import of all blueprint entities.

    Accepts optional ``{"dry_run": true}`` to preview without persisting.
    """
    dry_run = False
    if body and isinstance(body, dict):
        dry_run = body.get("dry_run", False)

    importer = BlueprintImporter(
        repo=repo,
        profile_dir=Path("profiles"),
        archive_dir=Path("archive/config"),
    )
    return importer.import_all(dry_run=dry_run)
