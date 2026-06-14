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


# ---------------------------------------------------------------------------
# A2A DNS resolution mock
# ---------------------------------------------------------------------------
#
# backend/a2a/url_validator.py calls ``socket.getaddrinfo`` to defend against
# DNS-rebinding attacks.  This is the *correct* behaviour in production, but
# it makes the test suite order-dependent on the CI sandbox's DNS resolver:
# placeholder hostnames like ``agent.example.com`` or single-label names like
# ``ext-agent`` are not resolvable from the runner, which causes the A2A
# unit and workflow tests to fail with ``A2AValidationError: DNS resolution
# failed for ...`` *before* the pytest_httpx mock is ever consumed.
#
# This autouse-but-scoped fixture replaces ``socket.getaddrinfo`` for A2A
# tests only.  It returns a single dummy A-record so the validator's
# private-IP / public-IP branching logic still runs; tests that want a
# genuine ``gaierror`` (e.g. for negative-path coverage) can opt out by
# re-monkeypatching the symbol themselves.
#
# No production code is modified — the URL validator keeps its real DNS
# behaviour in production.
@pytest.fixture(autouse=True)
def _a2a_dns_mock(request):
    """Mock socket.getaddrinfo for A2A-related test modules only.

    Detection: the test's file path contains "a2a" (case-sensitive,
    matches the pytest test file naming convention).  We check
    ``request.node.fspath`` rather than ``request.node.module`` so
    the fixture also activates for async test coroutines and
    parametrised tests where the module attribute can be None.
    """
    test_path = str(request.node.fspath).lower()
    if "a2a" not in test_path:
        yield
        return
    # We deliberately do NOT activate for test_a2a_url_validator.py
    # because that test exercises the real socket.getaddrinfo (and
    # the gaierror path).  Match more strictly on the other A2A test
    # files we know need the mock.
    if "a2a_url_validator" in test_path:
        yield
        return

    import socket as _socket

    def _fake_getaddrinfo(host, *args, **kwargs):
        # Return a single dummy IPv4 record.  Tests that need a
        # ``gaierror`` can re-monkeypatch over this fixture.
        return [(2, 1, 6, "", ("203.0.113.10", 0))]

    original = _socket.getaddrinfo
    _socket.getaddrinfo = _fake_getaddrinfo
    try:
        yield
    finally:
        _socket.getaddrinfo = original
