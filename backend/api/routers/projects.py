"""Projects API router — CRUD for project management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_project_store
from backend.models.project import (
    ProjectConfigUpdateRequest,
    ProjectCreateRequest,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[ProjectListItem])
def list_projects(
    store=Depends(get_project_store),
) -> list[ProjectListItem]:
    """List all projects."""
    projects = store.list_all()
    return [
        ProjectListItem(
            id=p.id,
            name=p.name,
            description=p.description,
            is_system=p.is_system,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    body: ProjectCreateRequest,
    store=Depends(get_project_store),
) -> ProjectResponse:
    """Create a new project."""
    project = store.create(name=body.name, description=body.description)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        is_system=project.is_system,
        created_at=project.created_at,
        updated_at=project.updated_at,
        config=project.config,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    store=Depends(get_project_store),
) -> ProjectResponse:
    """Get project details."""
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        is_system=project.is_system,
        created_at=project.created_at,
        updated_at=project.updated_at,
        config=project.config,
    )


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    body: ProjectUpdateRequest,
    store=Depends(get_project_store),
) -> ProjectResponse:
    """Update project name/description."""
    project = store.update(
        project_id,
        name=body.name,
        description=body.description,
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        is_system=project.is_system,
        created_at=project.created_at,
        updated_at=project.updated_at,
        config=project.config,
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: str,
    store=Depends(get_project_store),
) -> dict:
    """Delete a project. System projects cannot be deleted."""
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system project")
    deleted = store.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete project")
    return {"status": "ok", "deleted": project_id}


@router.get("/{project_id}/config")
def get_project_config(
    project_id: str,
    store=Depends(get_project_store),
) -> dict:
    """Get project-specific configuration."""
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.config.model_dump(mode="json")


@router.put("/{project_id}/config")
def update_project_config(
    project_id: str,
    body: ProjectConfigUpdateRequest,
    store=Depends(get_project_store),
) -> dict:
    """Update project-specific configuration."""
    project = store.update(project_id, config=body.config)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "ok", "config": project.config.model_dump(mode="json")}
