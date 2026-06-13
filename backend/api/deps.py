"""Dependency injection for FastAPI routes.

Provides shared services (audit, graph, settings) as FastAPI dependencies.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
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

logger = logging.getLogger(__name__)

# P3.4 — Dev-mode auth guardrails.
# When auth is disabled, we emit a loud WARNING at every dependent call
# (so it cannot be silently missed in a long-running log) AND refuse to
# serve traffic in any environment that looks like production. The
# operator can acknowledge the dev-mode once-per-process with
# DANWA_DEV_AUTH_ACK=1, but cannot use that flag to bypass the prod check.
_PROD_ENV_HINTS = {"production", "prod", "live"}


def _looks_like_production() -> bool:
    """Best-effort production detector.

    Returns True if the runtime looks like production:
    * ``DANWA_ENV`` is one of ``production/prod/live`` (case-insensitive), or
    * debug is False AND settings reports a non-localhost CORS / DB path.
    """
    env = os.environ.get("DANWA_ENV", "").strip().lower()
    if env in _PROD_ENV_HINTS:
        return True
    try:
        if not settings.debug and not settings.host.startswith("127.") and settings.host != "0.0.0.0":
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _dev_auth_acknowledged() -> bool:
    return os.environ.get("DANWA_DEV_AUTH_ACK", "").strip().lower() in {"1", "true", "yes", "on"}


def _warn_dev_auth(reason: str) -> None:
    """Emit a loud, one-line dev-mode auth WARNING on every call.

    We do NOT dedupe on a per-process flag because the operator needs to
    be reminded continuously that auth is off — silent failure is the
    most dangerous failure mode for this particular setting.
    """
    logger.warning(
        "DEV-MODE AUTH ACTIVE (%s): get_current_user is returning a synthetic "
        "admin user with role='admin' and tenant_id='_default'. ANY caller can "
        "act as the first user. Set DANWA_AUTH_ENABLED=true (or unset "
        "DANWA_AUTH_ENABLED) for production. Acknowledge with "
        "DANWA_DEV_AUTH_ACK=1 to silence this warning.",
        reason,
    )


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


def get_case_dir(case_id: str) -> Path:
    """Resolve a case/project ID to its filesystem directory.

    Resolution order:
    1. Try ``ProjectStore.get_project_dir()`` (legacy project IDs).
    2. If directory doesn't exist, search ``data/tenants/*/cases/{case_id}/``
       for a CaseStore-managed case directory.
    """
    ps = get_project_store()
    try:
        project_dir = ps.get_project_dir(case_id)
    except FileNotFoundError:
        project_dir = None
    if project_dir and project_dir.exists():
        return project_dir

    # Fallback: search CaseStore tenant directories for the case_id.
    # Case IDs are UUIDs so a filesystem scan is safe and rare.
    from backend.persistence.case_store import _DEFAULT_BASE_DIR as CASE_BASE

    if CASE_BASE.is_dir():
        for tenant_dir in sorted(CASE_BASE.iterdir()):
            if not tenant_dir.is_dir():
                continue
            candidate = tenant_dir / "cases" / case_id
            if candidate.is_dir():
                return candidate

    raise HTTPException(status_code=404, detail=f"Case directory not found: {case_id}")


def get_debate_store_for_case(case_id: str) -> DebateStore:
    """Return a case-scoped DebateStore.

    .. deprecated:: Use this instead of passing ``ProjectStore`` manually.
    """
    case_dir = get_case_dir(case_id)
    return DebateStore(data_dir=case_dir / "debates")


def get_profile_service_for_case(case_id: str):
    """Return a ProfileService with case/project-specific overrides merged.

    .. deprecated:: Use this instead of passing ``ProjectStore`` manually.
    """
    from backend.services.profile_service import ProfileService

    ps = get_project_store()
    project = ps.get(case_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProfileService(project_config=project.config)


# Legacy aliases — kept for backward compatibility during Phase 5c migration.
# Callers should switch to get_debate_store_for_case / get_profile_service_for_case.
def get_debate_store_for_project(project_id: str, project_store: ProjectStore) -> DebateStore:
    """Return a project-scoped DebateStore. Use get_debate_store_for_case() instead."""
    return get_debate_store_for_case(project_id)


def get_profile_service_for_project(project_id: str, project_store: ProjectStore):
    """Return a ProfileService. Use get_profile_service_for_case() instead."""
    return get_profile_service_for_case(project_id)


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
    x_case_id: str = Header(
        default="",
        description="Active case UUID (tenant-scoped)",
        alias="X-Case-Id",
    ),
) -> str:
    """Extract case ID from request header.

    Reads ``X-Case-Id`` header. Falls back to ``"_default"`` if not set.
    """
    return x_case_id or "_default"


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
# Cache-busting helpers
# ---------------------------------------------------------------------------
# Resolves two issues from the 2026-06-12 code review:
#   3.1  the lru_cache+lru_cache+... cascade that leaks stores across tests
#   3.3  the N+1 membership-lookup pattern in get_active_tenant et al.
#
# ---- 3.1 cascade --------------------------------------------------
# The @lru_cache-decorated store factories in this module keep a single
# store instance alive for the lifetime of the process. In production this
# is the right thing (one open SQLite connection per process, amortised).
# In tests it leaks: a fixture that says "use a fresh DB" is silently
# bypassed because the cached factory returns the *previous* test's store.
#
# The fix is two helpers:
#   1. ``fresh_stores()`` -- a context manager that clears every cached
#      store factory on entry, lets the test body install new overrides,
#      and re-clears on exit so the *next* test starts from a known empty
#      cache. This is what the conftest fixture uses.
#   2. ``reset_cached_stores()`` -- a fire-and-forget variant for callers
#      that don't want the surrounding context-manager ceremony. Also
#      clears the per-user membership TTL cache (see 3.3 below).
#
# ---- 3.3 membership N+1 --------------------------------------------
# ``get_active_tenant``, ``get_tenant_context`` and ``get_case_context``
# all used to call ``membership_store.list_by_user(user.id)`` on every
# request and iterate the result linearly.  With many tenants the cost
# is O(tenants) per request.
#
# The fix:
#   * ``_user_memberships_cached(user_id)`` returns the membership list
#     for a user, served from a 30-second in-process TTL cache keyed on
#     ``user_id``.
#   * ``invalidate_user_memberships(user_id)`` removes the cached entry
#     for one user.
#   * ``reset_user_memberships_cache()`` empties the entire cache.
#   * The deps module registers ``invalidate_user_memberships`` as a
#     ``MembershipStore`` invalidation observer at import time, so
#     mutations in production immediately invalidate the right user.
#   * ``reset_cached_stores()`` also clears this TTL cache, so
#     ``fresh_stores()`` gives tests a clean slate.


# The exact set of @lru_cache-decorated store/service factories in this
# module.  Defined *after* the factories it references, so the names are
# in scope.  Adding a new cached factory here is a deliberate act: append
# it to the tuple and add a test in tests/backend/test_deps_cache.py that
# covers it.  ``get_settings`` is intentionally included so that tests
# that monkeypatch ``DANWA_*`` env vars can clear the cached
# ``Settings`` instance after the patch.
_CACHED_STORE_FACTORIES: tuple = (
    get_settings,
    get_audit_service,
    get_debate_store,
    get_project_store,
    get_case_store,
    get_tag_store,
    get_blueprint_repository,
    get_user_store,
    get_tenant_store,
    get_membership_store,
)


def reset_cached_stores() -> None:
    """Clear every @lru_cache-decorated store factory in this module.

    Idempotent. Safe to call from a test fixture's teardown. Returns
    nothing -- the next call to the factory will re-populate the cache
    lazily.

    Production code should not call this; the cached factories exist so
    that the same SQLite connection is reused across requests. Tests are
    the only legitimate caller.

    Also clears the per-user membership TTL cache (section 3.3 of the
    2026-06-12 review) so the next test starts with a known-empty
    cache, not a 30-second-stale one.
    """
    for factory in _CACHED_STORE_FACTORIES:
        cache_clear = getattr(factory, "cache_clear", None)
        if cache_clear is not None:
            cache_clear()
    reset_user_memberships_cache()


# ---------------------------------------------------------------------------
# Per-user membership TTL cache  (section 3.3 of the 2026-06-12 review)
# ---------------------------------------------------------------------------
# Resolves the N+1 membership-lookup pattern in get_active_tenant,
# get_tenant_context and get_case_context.  Each of those used to call
# ``membership_store.list_by_user(user.id)`` on every request and
# iterate the result linearly.  With many tenants per user, the cost
# is O(tenants) per request.
#
# This 30-second TTL cache keys on user_id (NOT tenant_id -- a fan-out
# per tenant would defeat the cache).  When a membership is mutated,
# the store's invalidation observer (registered at import time, below)
# drops the affected user's entry so the next request sees the new
# state immediately.

_USER_MEMBERSHIPS_CACHE: dict[str, tuple[float, list[Any]]] = {}
_USER_MEMBERSHIPS_TTL_SECONDS: float = 30.0


def _user_memberships_cached(user_id: str) -> list[Any]:
    """Return the membership list for *user_id*, served from a 30s TTL cache.

    Returns the cached value if it was written within
    ``_USER_MEMBERSHIPS_TTL_SECONDS``.  Otherwise re-fetches from the
    membership store and re-populates the cache.

    The returned list is the cached list object -- callers MUST NOT
    mutate it.  If you need to mutate, copy first.
    """
    now = time.monotonic()
    cached = _USER_MEMBERSHIPS_CACHE.get(user_id)
    if cached is not None:
        ts, memberships = cached
        if now - ts < _USER_MEMBERSHIPS_TTL_SECONDS:
            return memberships
    # Miss / expired: re-fetch from the store.  We use the module-level
    # ``get_membership_store()`` so that the cache is keyed on the
    # *process-singleton* store, exactly like the @lru_cache factories
    # above.  In tests, ``fresh_stores()`` clears the store cache (so a
    # new store is constructed) and the membership TTL cache, so the
    # fetch picks up the test's temporary SQLite file.
    memberships = list(get_membership_store().list_by_user(user_id))
    _USER_MEMBERSHIPS_CACHE[user_id] = (now, memberships)
    return memberships


def invalidate_user_memberships(user_id: str) -> None:
    """Drop the cached membership list for *user_id* (if any).

    Idempotent. Safe to call for a user that has never been cached.

    Wired up at import time as a ``MembershipStore`` invalidation
    observer, so a write to ``membership_store.add/remove/update_role``
    immediately invalidates the affected user.
    """
    _USER_MEMBERSHIPS_CACHE.pop(user_id, None)


def reset_user_memberships_cache() -> None:
    """Empty the entire per-user membership TTL cache.

    Called by ``reset_cached_stores()`` (and therefore by
    ``fresh_stores()``) so the next test starts with a known-empty
    cache, not a 30-second-stale one.
    """
    _USER_MEMBERSHIPS_CACHE.clear()


# Register the invalidation hook with the membership store.
# Done at import time via a lazy import to avoid a circular dependency
# (deps -> membership_store is one-way; if we imported
# ``membership_store`` at module top, the store's observers would have
# to import deps, which is the wrong direction).
def _register_membership_invalidator() -> None:
    from backend.persistence.membership_store import MembershipStore

    MembershipStore.add_invalidator(invalidate_user_memberships)


_register_membership_invalidator()


@contextmanager
def fresh_stores() -> Iterator[None]:
    """Bust every @lru_cache-decorated store factory for the scope of a test.

    Usage::

        def test_x(monkeypatch):
            with fresh_stores():
                # Body runs with an empty lru_cache so that any
                # ``get_*_store()`` call inside it constructs a *new*
                # store, picking up ``tmp_path`` / monkeypatched env vars.
                ...
            # After the block the cache is *still* empty: the next test
            # starts with a clean slate even if the body of the test
            # raised before the cleanup ran.

    Why a context manager and not a plain fixture: pytest fixtures cannot
    clean up after themselves if a test raises before the ``yield`` is
    reached (parametrise / collection errors).  ``fresh_stores()`` always
    runs its teardown branch, so a misbehaving test cannot poison the
    next one.
    """
    reset_cached_stores()
    try:
        yield
    finally:
        reset_cached_stores()


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

    # P4.2 -- N+1 fix: serve the membership list from the per-user TTL
    # cache (section 3.3 of the 2026-06-12 review).  The cache is
    # invalidated by ``MembershipStore.add/remove/update_role`` so we
    # always see the current state after a write.
    memberships = _user_memberships_cached(current_user.id)
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
    # P4.2 -- N+1 fix: see get_active_tenant for rationale.
    memberships = _user_memberships_cached(current_user.id)
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
        # P4.2 -- N+1 fix: see get_active_tenant for rationale.
        memberships = _user_memberships_cached(current_user.id)
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

    P3.4 — Dev-mode auth guardrails:
    * When ``settings.auth_enabled`` is False:
      - In a production-looking environment (DANWA_ENV=production / non-local
        bind AND debug=False) the request is REFUSED with 503. The
        ``DANWA_DEV_AUTH_ACK`` flag does NOT bypass this check.
      - In a non-production environment the function returns a synthetic
        admin user, but emits a loud WARNING on every call (silenceable
        for one process by setting ``DANWA_DEV_AUTH_ACK=1``).
    """
    from backend.core.security import decode_token
    from backend.models.user import User

    if not settings.auth_enabled:
        # P3.4 — refuse dev mode in production. This is the fail-closed
        # check that the 2026-06-12 review demanded.
        if _looks_like_production():
            logger.error(
                "REFUSING REQUEST: auth is disabled but the runtime looks like "
                "production (DANWA_ENV=%r, host=%r, debug=%r). Set "
                "DANWA_AUTH_ENABLED=true (or unset it) before serving traffic.",
                os.environ.get("DANWA_ENV", ""),
                settings.host,
                settings.debug,
            )
            raise HTTPException(
                status_code=503,
                detail="Authentication is disabled but the server is running in production. Set DANWA_AUTH_ENABLED=true to enable auth.",
            )

        if not _dev_auth_acknowledged():
            _warn_dev_auth(f"auth_enabled={settings.auth_enabled}")
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
