"""Blueprint Canvas — Agent Blueprints CRUD and bulk import.

LLM Profiles, Prompt Templates, Role Definitions, Role Types, and
Workflow Definitions have been extracted into their own focused routers:

- ``llm_profiles`` → ``/api/v1/blueprints/llm-profiles``
- ``role_definitions`` → ``/api/v1/blueprints/role-definitions`` + ``role-types``
- ``workflow_definitions`` → ``/api/v1/blueprints/workflows``

This router retains Agent Blueprints CRUD and the bulk import trigger.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.importer import BlueprintImporter, ImportResult
from backend.blueprints.models import AgentBlueprint, AgentBundle, PromptTemplate, ResolvedBundle
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.resolver import BundleResolver, resolve_bundle

router = APIRouter()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _require_found(entity: str, obj: object, entity_id: str) -> None:
    """Raise BlueprintNotFoundError if obj is None."""
    if obj is None:
        raise BlueprintNotFoundError(entity, entity_id)


def _require_not_exists(repo: BlueprintRepository, entity_id: str) -> None:
    """Raise BlueprintConflictError if an agent blueprint with the given ID already exists."""
    existing = repo.get_blueprint(entity_id)
    if existing is not None:
        raise BlueprintConflictError("AgentBlueprint", entity_id)


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
    _require_not_exists(repo, blueprint.id)
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
# Agent Bundles
# ==================================================================


@router.get("/bundles", response_model=list[AgentBundle])
def list_bundles(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[AgentBundle]:
    """List agent bundles with optional active-only filter and pagination."""
    return repo.list_bundles(active_only=active_only, limit=limit, offset=offset)


@router.get("/bundles/{bundle_id}", response_model=AgentBundle)
def get_bundle(
    bundle_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBundle:
    """Get a single agent bundle by ID."""
    bundle = repo.get_bundle(bundle_id)
    _require_found("AgentBundle", bundle, bundle_id)
    return bundle  # type: ignore[return-value]


@router.post("/bundles", response_model=AgentBundle, status_code=201)
def create_bundle(
    bundle: AgentBundle,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBundle:
    """Create a new agent bundle.

    Validates that all referenced entities (LLM profile, RoleType, etc.) exist.
    """
    _validate_bundle_references(repo, bundle)
    repo.save_bundle(bundle)
    return bundle


@router.put("/bundles/{bundle_id}", response_model=AgentBundle)
def update_bundle(
    bundle_id: str,
    bundle: AgentBundle,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBundle:
    """Update an existing agent bundle."""
    existing = repo.get_bundle(bundle_id)
    _require_found("AgentBundle", existing, bundle_id)
    _validate_bundle_references(repo, bundle)
    repo.save_bundle(bundle)
    return bundle


@router.delete("/bundles/{bundle_id}")
def delete_bundle(
    bundle_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Delete an agent bundle."""
    deleted = repo.delete_bundle(bundle_id)
    if not deleted:
        raise BlueprintNotFoundError("AgentBundle", bundle_id)
    return {"status": "ok", "deleted": bundle_id}


@router.get("/bundles/{bundle_id}/resolve", response_model=ResolvedBundle)
def resolve_bundle_endpoint(
    bundle_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> ResolvedBundle:
    """Resolve a bundle — load all referenced entities and assemble system prompt."""
    bundle = repo.get_bundle(bundle_id)
    _require_found("AgentBundle", bundle, bundle_id)
    resolver = BundleResolver(repo)
    return resolver.resolve(bundle)


def _validate_bundle_references(repo: BlueprintRepository, bundle: AgentBundle) -> None:
    """Validate that all required references in a bundle exist."""
    if not repo.get_llm_profile(bundle.llm_profile_id):
        raise BlueprintNotFoundError("BlueprintLLMProfile", bundle.llm_profile_id)
    if not repo.get_role_type(bundle.role_type_id):
        raise BlueprintNotFoundError("RoleType", bundle.role_type_id)
    if bundle.role_definition_id and not repo.get_role_definition(bundle.role_definition_id):
        raise BlueprintNotFoundError("RoleDefinition", bundle.role_definition_id)
    if bundle.prompt_template_id and not repo.get_prompt_template(bundle.prompt_template_id):
        raise BlueprintNotFoundError("PromptTemplate", bundle.prompt_template_id)
    if bundle.tone_profile_id and not repo.get_tone_profile(bundle.tone_profile_id):
        raise BlueprintNotFoundError("ToneProfile", bundle.tone_profile_id)


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
    existing = repo.get_prompt_template(template.id)
    if existing is not None:
        raise BlueprintConflictError("PromptTemplate", template.id)
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
# Import
# ==================================================================


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
