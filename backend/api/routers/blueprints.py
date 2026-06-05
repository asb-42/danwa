"""Blueprint Canvas — Agent Blueprints CRUD and Bundle management.

LLM Profiles, Role Definitions, Role Types, and Workflow Definitions have
been extracted into their own focused routers or removed (legacy role
management is now module-based).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.models import AgentBlueprint, AgentBundle, ResolvedBundle
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.resolver import BundleResolver
from backend.services.module_profile_sync import (
    get_bundles_from_modules,
)

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


@router.get("/bundles")
def list_bundles(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[dict[str, Any]]:
    """List agent bundles with optional active-only filter and pagination, including enabled module bundles."""
    db_bundles = repo.list_bundles(active_only=active_only, limit=limit, offset=offset)
    db_dicts = [b.model_dump() if hasattr(b, "model_dump") else b for b in db_bundles]
    module_bundles = get_bundles_from_modules()
    if active_only:
        module_bundles = [b for b in module_bundles if b.get("is_active", True)]

    seen_ids: set[str] = set()
    combined: list[dict[str, Any]] = []
    for entry in db_dicts + module_bundles:
        eid = entry.get("id")
        if eid not in seen_ids:
            seen_ids.add(eid)
            combined.append(entry)
    return combined


@router.get("/bundles/{bundle_id}", response_model=AgentBundle)
def get_bundle(
    bundle_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBundle:
    """Get a single agent bundle by ID — checks DB first, then modules."""
    bundle = repo.get_bundle(bundle_id)
    if bundle is not None:
        return bundle  # type: ignore[return-value]

    for mb in get_bundles_from_modules():
        if mb.get("id") == bundle_id:
            return AgentBundle(**{k: v for k, v in mb.items() if k in AgentBundle.model_fields})

    raise BlueprintNotFoundError("AgentBundle", bundle_id)


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
    from backend.blueprints.module_lookups import resolve_role_type

    if not repo.get_llm_profile(bundle.llm_profile_id):
        raise BlueprintNotFoundError("BlueprintLLMProfile", bundle.llm_profile_id)
    if not resolve_role_type(bundle.role_type_id):
        raise BlueprintNotFoundError("RoleType", bundle.role_type_id)
    if bundle.tone_profile_id and not repo.get_tone_profile(bundle.tone_profile_id):
        raise BlueprintNotFoundError("ToneProfile", bundle.tone_profile_id)


# ==================================================================
# Bundle Export / Import
# ==================================================================


@router.get("/bundles/{bundle_id}/export")
def export_bundle_endpoint(
    bundle_id: str,
    include_all_role_types: bool = False,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> dict:
    """Export a bundle as a portable JSON document with all dependencies."""
    from backend.blueprints.bundle_io import export_bundle_with_dependencies

    bundle = repo.get_bundle(bundle_id)
    _require_found("AgentBundle", bundle, bundle_id)

    try:
        data = export_bundle_with_dependencies(
            bundle_id,
            repo,
            include_all_role_types=include_all_role_types,
        )
        return data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class ImportBundleRequest(BaseModel):
    """Request body for importing a bundle."""

    data: dict
    conflict_strategy: str = "rename"  # skip | overwrite | rename


@router.post("/bundles/import", response_model=AgentBundle, status_code=201)
def import_bundle_endpoint(
    body: ImportBundleRequest,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBundle:
    """Import a bundle from an exported JSON document.

    Conflict strategies:
    - ``skip``: Skip entities that already exist by ID.
    - ``overwrite``: Replace existing entities.
    - ``rename``: Generate new IDs for conflicts (default).
    """
    from backend.blueprints.bundle_io import import_bundle

    try:
        bundle = import_bundle(
            body.data,
            repo,
            conflict_strategy=body.conflict_strategy,
        )
        return bundle
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
