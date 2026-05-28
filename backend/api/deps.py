"""Dependency injection for FastAPI routes.

Provides shared services (audit, graph, settings) as FastAPI dependencies.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from backend.blueprints.repository import BlueprintRepository
from backend.core.config import Settings, settings
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore
from backend.workflow.debate_graph import debate_graph

_SETTINGS_PATH = Path("config/settings.yaml")

_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return settings


def get_user_language() -> str:
    """Get the user's configured UI language.

    Reads from config/settings.yaml (ui.language).
    Falls back to 'de' if not configured.

    This is the single source of truth for the user's language preference.
    It is persisted across sessions and takes precedence over browser settings.
    """
    if _SETTINGS_PATH.exists():
        try:
            import yaml

            with open(_SETTINGS_PATH, encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            lang = cfg.get("ui", {}).get("language")
            if lang:
                return lang
        except Exception:
            pass
    return "de"


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


def get_debate_store_for_project(project_id: str, project_store: ProjectStore) -> DebateStore:
    """Return a project-scoped DebateStore."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    project_dir = project_store.get_project_dir(project_id)
    return DebateStore(data_dir=project_dir / "debates")


def get_profile_service_for_project(project_id: str, project_store: ProjectStore):
    """Return a ProfileService with project-specific overrides merged."""
    from backend.services.profile_service import ProfileService

    project = project_store.get(project_id)
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
    """Extract project_id from request header.

    This is a required dependency for all project-scoped endpoints.
    """
    return x_project_id


# ---------------------------------------------------------------------------
# User Store
# ---------------------------------------------------------------------------


@lru_cache
def get_user_store():
    """Singleton UserStore instance."""
    from backend.persistence.user_store import UserStore

    return UserStore()


@lru_cache
def get_tenant_store():
    """Singleton TenantStore instance."""
    from backend.persistence.tenant_store import TenantStore

    return TenantStore()


# ---------------------------------------------------------------------------
# Tenant & Project scoping
# ---------------------------------------------------------------------------


async def get_project_scoped(
    project_id: str = Depends(get_project_id),
    user=Depends(lambda: None),  # Injected below after get_current_user is defined
):
    """Validate that the authenticated user has access to the requested project.

    Returns the project if the user's tenant_id matches the project's tenant_id.
    Raises 404 (not 403) to avoid information leakage.
    """
    # If auth is disabled, skip tenant check
    if not settings.auth_enabled:
        project = get_project_store().get(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    # Lazy import to avoid circular dependency
    from backend.api.deps import get_current_user as _gcu

    current_user = user or await _gcu()
    project = get_project_store().get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.tenant_id != current_user.tenant_id and current_user.role != "admin":
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ---------------------------------------------------------------------------
# Authentication dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
):
    """Validate JWT bearer token and return the authenticated user.

    If auth_enabled is False, returns a synthetic admin user (dev mode).
    If no credentials are provided and auth is enabled, raises 401.
    """
    from backend.core.security import decode_token
    from backend.models.user import User

    if not settings.auth_enabled:
        # Dev mode: return synthetic admin user
        return User(
            id="dev-user",
            email="dev@danwa.local",
            display_name="Dev User",
            password_hash="",
            role="admin",
            tenant_id="_default",
        )

    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        token_data = decode_token(credentials.credentials)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    if token_data.token_type != "access":
        raise HTTPException(status_code=401, detail="Token is not an access token")

    user_store = get_user_store()
    user = user_store.get(token_data.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    return user


def require_role(*roles: str):
    """Dependency factory for role-based access control.

    Usage:
        @router.post("/admin-only")
        async def admin_endpoint(user = Depends(require_role("admin"))):
            ...
    """

    def _check_role(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
        return user

    return _check_role
