"""Dependency injection for FastAPI routes.

Provides shared services (audit, graph, settings) as FastAPI dependencies.
"""

from __future__ import annotations

from functools import lru_cache

from fastapi import Header, HTTPException

from backend.blueprints.repository import BlueprintRepository
from backend.core.config import Settings, settings
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore
from backend.workflow.debate_graph import debate_graph


@lru_cache
def get_settings() -> Settings:
    return settings


@lru_cache
def get_audit_service() -> AuditService:
    return AuditService()


@lru_cache
def get_debate_store() -> DebateStore:
    """Global debate store — used only for migration."""
    return DebateStore()


@lru_cache
def get_project_store() -> ProjectStore:
    return ProjectStore()


def get_debate_store_for_project(project_id: str) -> DebateStore:
    """Return a project-scoped DebateStore."""
    store = get_project_store()
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project_dir = store.get_project_dir(project_id)
    return DebateStore(data_dir=project_dir / "debates")


def get_profile_service_for_project(project_id: str):
    """Return a ProfileService with project-specific overrides merged."""
    from backend.services.profile_service import ProfileService

    store = get_project_store()
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProfileService(project_config=project.config)


def get_prompt_service():
    from backend.services.prompt_service import PromptService

    return PromptService()


def get_debate_graph():
    return debate_graph


@lru_cache
def get_blueprint_repository() -> BlueprintRepository:
    """Singleton BlueprintRepository instance."""
    return BlueprintRepository()


async def get_project_id(
    x_project_id: str = Header(
        ...,
        description="Active project UUID",
        alias="X-Project-Id",
    ),
) -> str:
    """Extract and validate project_id from request header.

    This is a required dependency for all project-scoped endpoints.
    """
    store = get_project_store()
    project = store.get(x_project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return x_project_id
