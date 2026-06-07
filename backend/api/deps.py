"""Dependency injection for FastAPI routes.

Provides shared services (audit, graph, settings) as FastAPI dependencies.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

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
    """Retrieve and return audit service."""
    return AuditService()


@lru_cache
def get_debate_store() -> DebateStore:
    """Global debate store — used only for migration."""
    return DebateStore()


@lru_cache
def get_project_store() -> ProjectStore:
    """Retrieve and return project store."""
    return ProjectStore()


@lru_cache
def get_case_store():
    """Singleton CaseStore instance."""
    from backend.persistence.case_store import CaseStore

    return CaseStore()


@lru_cache
def get_tag_store():
    """Singleton TagStore instance."""
    from backend.persistence.tag_store import TagStore

    return TagStore()


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
    """Retrieve and return prompt service."""
    from backend.services.prompt_service import PromptService

    return PromptService()


def get_debate_graph():
    """Retrieve and return debate graph."""
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


@lru_cache
def get_membership_store():
    """Singleton MembershipStore instance."""
    from backend.persistence.membership_store import MembershipStore

    return MembershipStore()


# ---------------------------------------------------------------------------
# Tenant & Project scoping
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tenant & Case context dependencies
# ---------------------------------------------------------------------------


async def get_active_tenant(
    user=Depends(lambda: None),
    tenant_id_header: str | None = Header(None, alias="X-Tenant-Id"),
) -> str:
    """Resolve the active tenant for the current request.

    Priority:
    1. X-Tenant-Id header (if provided, validates membership)
    2. user.tenant_id from JWT (default active tenant)
    """
    if not settings.auth_enabled:
        return tenant_id_header or "_default"

    from backend.api.deps import get_current_user as _gcu

    current_user = user or await _gcu()
    tid = tenant_id_header or current_user.tenant_id

    membership_store = get_membership_store()
    memberships = membership_store.list_by_user(current_user.id)
    if not any(m.tenant_id == tid for m in memberships):
        if any(m.tenant_id == current_user.tenant_id for m in memberships):
            return current_user.tenant_id
        raise HTTPException(status_code=403, detail=f"Not a member of tenant '{tid}'")
    return tid


async def get_tenant_context(
    tid: str,
    user=Depends(lambda: None),
) -> str:
    """Validate user membership for a tenant from a path parameter.

    Usage in routers with ``/tenants/{tid}/...`` paths.
    """
    if not settings.auth_enabled:
        return tid

    from backend.api.deps import get_current_user as _gcu

    current_user = user or await _gcu()
    membership_store = get_membership_store()
    memberships = membership_store.list_by_user(current_user.id)
    if not any(m.tenant_id == tid for m in memberships):
        raise HTTPException(status_code=403, detail=f"Not a member of tenant '{tid}'")
    return tid


async def get_case_context(
    tid: str,
    cid: str,
    user=Depends(lambda: None),
) -> Any:
    """Load and validate a case from tenant/case path parameters.

    Raises 404 if case doesn't exist. If auth is enabled, validates
    that the current user is a member of the tenant.
    """
    if settings.auth_enabled:
        from backend.api.deps import get_current_user as _gcu

        current_user = user or await _gcu()
        membership_store = get_membership_store()
        memberships = membership_store.list_by_user(current_user.id)
        if not any(m.tenant_id == tid for m in memberships):
            raise HTTPException(status_code=403, detail=f"Not a member of tenant '{tid}'")

    case_store = get_case_store()
    case = case_store.get(tid, cid)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


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
