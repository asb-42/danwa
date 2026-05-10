"""Role Definitions & Role Types CRUD router.

Extracted from ``backend.api.routers.blueprints`` to follow the
Single Responsibility Principle.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_blueprint_repository
from backend.api.errors import BlueprintConflictError, BlueprintNotFoundError
from backend.blueprints.models import RoleDefinition, RoleType
from backend.blueprints.repository import BlueprintRepository

router = APIRouter()


def _require_found(entity: str, obj: object, entity_id: str) -> None:
    """Raise BlueprintNotFoundError if obj is None."""
    if obj is None:
        raise BlueprintNotFoundError(entity, entity_id)


def _require_not_exists(repo: BlueprintRepository, entity: str, entity_id: str) -> None:
    """Raise BlueprintConflictError if an entity with the given ID already exists."""
    existing = None
    if entity == "RoleDefinition":
        existing = repo.get_role_definition(entity_id)
    elif entity == "RoleType":
        existing = repo.get_role_type(entity_id)
    if existing is not None:
        raise BlueprintConflictError(entity, entity_id)


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
