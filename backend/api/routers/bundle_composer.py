"""Bundle Composer API router.

Endpoints for the Builder UI's Bundle Composer feature:
- List available components (agent cores, argumentation patterns, tone profiles, prompt modifiers, LLM profiles)
- Preview assembled system prompt from component selection
- Create/update/list/get composition-based AgentBundles
- Export to and import from modules/agent-bundles/ on disk
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_blueprint_repository
from backend.blueprints.composer import BundleComposer
from backend.blueprints.models import AgentBundle
from backend.blueprints.repository import BlueprintRepository
from backend.services.composer_service import Composition

router = APIRouter()


def _get_composer(repo: BlueprintRepository = Depends(get_blueprint_repository)) -> BundleComposer:
    """Return (or lazily create) composer."""
    return BundleComposer(repo=repo)


# ==================================================================
# Components
# ==================================================================


@router.get("/components")
def list_components(
    composer: BundleComposer = Depends(_get_composer),
) -> dict[str, list[dict[str, Any]]]:
    """Return all available components across all 5 categories.

    Returns agent_cores, argumentation_patterns, tone_profiles,
    prompt_modifiers, and llm_profiles for populating dropdowns.
    """
    return composer.list_components()


# ==================================================================
# Preview
# ==================================================================


class PreviewRequest(Composition):
    """Request body for preview — same fields as Composition."""


@router.post("/preview")
def preview_prompt(
    body: PreviewRequest,
    composer: BundleComposer = Depends(_get_composer),
) -> dict[str, str]:
    """Preview the assembled system prompt without persisting.

    Accepts the four component IDs and returns the concatenated prompt.
    """
    prompt = composer.preview(body)
    return {"prompt": prompt}


# ==================================================================
# Bundle CRUD
# ==================================================================


class CreateBundleRequest(BaseModel):
    """Request body for creating a composer bundle."""

    name: str
    composition: Composition
    description: str = ""
    llm_profile_id: str = ""


class UpdateBundleRequest(BaseModel):
    """Request body for updating a composer bundle."""

    name: str | None = None
    composition: Composition | None = None
    description: str | None = None
    llm_profile_id: str | None = None


@router.post("/bundles", response_model=AgentBundle, status_code=201)
def create_bundle(
    body: CreateBundleRequest,
    composer: BundleComposer = Depends(_get_composer),
) -> AgentBundle:
    """Create a new AgentBundle from modular composition."""
    try:
        return composer.create(
            name=body.name,
            composition=body.composition,
            description=body.description,
            llm_profile_id=body.llm_profile_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/bundles", response_model=list[AgentBundle])
def list_bundles(
    active_only: bool = True,
    limit: int = 50,
    offset: int = 0,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> list[AgentBundle]:
    """List agent bundles, optionally filtering to active only."""
    return repo.list_bundles(active_only=active_only, limit=limit, offset=offset)


@router.get("/bundles/{bundle_id}", response_model=AgentBundle)
def get_bundle(
    bundle_id: str,
    repo: BlueprintRepository = Depends(get_blueprint_repository),
) -> AgentBundle:
    """Get a single agent bundle by ID."""
    bundle = repo.get_bundle(bundle_id)
    if not bundle:
        raise HTTPException(status_code=404, detail=f"Bundle '{bundle_id}' not found")
    return bundle


@router.put("/bundles/{bundle_id}", response_model=AgentBundle)
def update_bundle(
    bundle_id: str,
    body: UpdateBundleRequest,
    composer: BundleComposer = Depends(_get_composer),
) -> AgentBundle:
    """Update an existing composer bundle."""
    result = composer.update(
        bundle_id=bundle_id,
        name=body.name,
        composition=body.composition,
        description=body.description,
        llm_profile_id=body.llm_profile_id,
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Bundle '{bundle_id}' not found")
    return result


# ==================================================================
# Export / Import
# ==================================================================


@router.post("/bundles/{bundle_id}/export")
def export_bundle(
    bundle_id: str,
    to_directory: bool = False,
    composer: BundleComposer = Depends(_get_composer),
) -> dict[str, Any]:
    """Export a bundle as portable manifest + profile.

    When ``to_directory=true``, writes to modules/agent-bundles/<id>/ on disk.
    Returns the manifest and profile dicts (or the directory path).
    """
    try:
        if to_directory:
            path = composer.export_to_directory(bundle_id)
            return {"path": str(path)}
        return composer.export(bundle_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


class ImportRequest(BaseModel):
    """Request body for importing a bundle from directory."""

    module_id: str


@router.post("/import", response_model=AgentBundle, status_code=201)
def import_bundle(
    body: ImportRequest,
    composer: BundleComposer = Depends(_get_composer),
) -> AgentBundle:
    """Import a bundle from modules/agent-bundles/<module_id>/ on disk."""
    try:
        return composer.import_from_directory(body.module_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
