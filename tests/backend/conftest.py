"""Shared test fixtures for backend tests."""

from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.api import deps as deps_module
from backend.api.deps import (
    fresh_stores,
    get_audit_service,
    get_case_store,
    get_current_user,
    get_debate_store,
    get_project_id,
    get_project_store,
    get_settings,
    get_tenant_store,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.case_store import CaseStore
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore
from backend.persistence.tenant_store import TenantStore


@pytest.fixture()
def settings(tmp_path) -> Settings:
    """Test settings with temporary database path."""
    return Settings(
        db_path=tmp_path / "test_audit.db",
        cors_origins=["http://testserver"],
        debug=True,
        auth_enabled=False,
    )


@pytest.fixture()
def audit_service(tmp_path) -> AuditService:
    """Isolated AuditService with temp database."""
    return AuditService(db_path=tmp_path / "test_audit.db")


@pytest.fixture()
def debate_store(tmp_path) -> DebateStore:
    """Isolated DebateStore with temp directory."""
    return DebateStore(data_dir=tmp_path / "test_debates")


@pytest.fixture()
def project_store(tmp_path) -> ProjectStore:
    """Isolated ProjectStore with temp directory."""
    return ProjectStore(base_dir=tmp_path / "test_projects")


@pytest.fixture()
def tenant_store(tmp_path) -> TenantStore:
    """Isolated TenantStore with temp database."""
    return TenantStore(db_path=tmp_path / "test_tenant.db")


@pytest.fixture()
def case_store(tmp_path) -> CaseStore:
    """Isolated CaseStore with temp directory."""
    return CaseStore(base_dir=tmp_path / "test_cases")


@pytest.fixture()
def default_project(project_store):
    """Ensure a default project exists and return its ID."""
    project = project_store.get_or_create_default()
    return project.id


@pytest.fixture()
def default_tenant(tenant_store):
    """Ensure a default tenant exists and return its ID."""
    existing = tenant_store.get("_default")
    if existing:
        return existing.id
    return tenant_store.create("Default Tenant", tenant_id="_default").id


@pytest.fixture()
def default_case(case_store, default_tenant):
    """Ensure a default case exists for the default tenant and return its ID."""
    case = case_store.get_or_create_default(default_tenant)
    return case.id


@pytest.fixture()
def app(
    settings,
    audit_service,
    debate_store,
    project_store,
    tenant_store,
    case_store,
    default_project,
    default_tenant,
    default_case,
):
    """FastAPI app with overridden dependencies.

    Uses ``fresh_stores()`` (the cache-busting context manager from
    ``backend.api.deps``) so that every cached store factory in
    ``deps.py`` is empty on entry AND on exit. This guarantees that
    *both* directions of test isolation work:

    * The test starts with an empty cache so the ``dependency_overrides``
      and ``mock.patch.multiple`` below actually take effect.
    * The test ends with an empty cache so the *next* test does not
      accidentally inherit a cached store from us.

    See ``reports/2026-06-12_code-review.md`` section 3.1 for the
    cascade bug this resolves.
    """
    with fresh_stores():
        application = create_app()

        _test_user = User(
            id="test-user",
            email="test@danwa.local",
            display_name="Test User",
            password_hash="",
            role="admin",
            tenant_id=default_tenant,
        )

        application.dependency_overrides[get_settings] = lambda: settings
        application.dependency_overrides[get_current_user] = lambda: _test_user
        application.dependency_overrides[get_audit_service] = lambda: audit_service
        application.dependency_overrides[get_debate_store] = lambda: debate_store
        application.dependency_overrides[get_project_store] = lambda: project_store
        application.dependency_overrides[get_project_id] = lambda: default_project
        application.dependency_overrides[get_tenant_store] = lambda: tenant_store
        application.dependency_overrides[get_case_store] = lambda: case_store
        # Store for test helpers to access via client.app.state
        application.state.test_project_store = project_store
        application.state.test_tenant_store = tenant_store
        application.state.test_case_store = case_store
        application.state.test_default_tenant = default_tenant
        application.state.test_default_case = default_case

        # Monkeypatch module-level functions called outside FastAPI DI
        # (e.g. get_case_dir -> get_project_store, get_tenant_store, get_case_store)
        mpatch = mock.patch.multiple(
            deps_module,
            get_project_store=mock.MagicMock(return_value=project_store),
            get_tenant_store=mock.MagicMock(return_value=tenant_store),
            get_case_store=mock.MagicMock(return_value=case_store),
        )
        mpatch.start()
        application.state._deps_monkeypatch = mpatch
        try:
            yield application
        finally:
            mpatch.stop()
            del application.state._deps_monkeypatch
        # Note: the outer ``with fresh_stores()`` teardown re-clears the
        # cache after the test body runs, so the next test starts fresh.


@pytest.fixture(autouse=True)
def _clear_dms_cache():
    """Clear the DMS instance cache between tests."""
    from backend.services.dms.service import _dms_cache

    _dms_cache.clear()
    yield
    _dms_cache.clear()


@pytest.fixture(autouse=True)
def _disable_auth():
    """Disable auth globally for all backend tests."""
    from backend.api import deps as deps_module

    original = deps_module.settings.auth_enabled
    deps_module.settings.auth_enabled = False
    yield
    deps_module.settings.auth_enabled = original


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client."""
    return TestClient(app)
