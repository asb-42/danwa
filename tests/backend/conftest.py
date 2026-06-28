"""Shared test fixtures for backend tests.

.. deprecated::
    This legacy backend test suite has been superseded by danwa-core.
    Run the replacement tests with::

        cd danwa-core && python -m pytest tests/

    All fixtures below are retained for reference only.
"""

from __future__ import annotations

from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Legacy backend import guard — skip entire suite if imports fail.
# The legacy backend (backend.main) is deprecated and its create_app()
# is commented out.  Dependencies like passlib may no longer be installed.
# ---------------------------------------------------------------------------
_LEGACY_IMPORTS_OK = False
try:
    from fastapi.testclient import TestClient  # noqa: F401

    from backend.api import deps as deps_module  # noqa: F401
    from backend.api.deps import (  # noqa: F401
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
    from backend.core.config import Settings  # noqa: F401
    from backend.main import app as _app  # noqa: F401
    from backend.main import create_app  # noqa: F401
    from backend.models.user import User  # noqa: F401
    from backend.persistence.audit import AuditService  # noqa: F401
    from backend.persistence.case_store import CaseStore  # noqa: F401
    from backend.persistence.debate_store import DebateStore  # noqa: F401
    from backend.persistence.project_store import ProjectStore  # noqa: F401
    from backend.persistence.tenant_store import TenantStore  # noqa: F401

    # Verify the stub actually works (create_app raises RuntimeError = deprecated)
    _LEGACY_IMPORTS_OK = True
except ImportError:
    pass

# Even if imports succeed, the create_app() stub raises RuntimeError
# when called — treat that as deprecated too.
if _LEGACY_IMPORTS_OK:
    try:
        create_app()
    except RuntimeError:
        _LEGACY_IMPORTS_OK = False


def pytest_collection_modifyitems(config, items):
    """Skip all legacy backend tests — use danwa-core instead."""
    if _LEGACY_IMPORTS_OK:
        return
    skip_legacy = pytest.mark.skip(
        reason=("DEPRECATED: Legacy backend tests skipped. Use danwa-core instead: cd ../danwa-core && python -m pytest tests/")
    )
    for item in items:
        item.add_marker(skip_legacy)


# ---------------------------------------------------------------------------
# All fixtures below are only defined when legacy imports succeed.
# When imports fail (deprecated backend), pytest_collection_modifyitems
# skips all tests, so these fixtures are never instantiated.
# ---------------------------------------------------------------------------

if _LEGACY_IMPORTS_OK:

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
        """FastAPI app with overridden dependencies."""
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
            application.state.test_project_store = project_store
            application.state.test_tenant_store = tenant_store
            application.state.test_case_store = case_store
            application.state.test_default_tenant = default_tenant
            application.state.test_default_case = default_case

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

    @pytest.fixture(autouse=True)
    def _a2a_dns_mock(request):
        """Mock socket.getaddrinfo for A2A-related test modules only."""
        test_path = str(request.node.fspath).lower()
        if "a2a" not in test_path:
            yield
            return
        if "a2a_url_validator" in test_path:
            yield
            return

        import socket as _socket

        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("203.0.113.10", 0))]

        original = _socket.getaddrinfo
        _socket.getaddrinfo = _fake_getaddrinfo
        try:
            yield
        finally:
            _socket.getaddrinfo = original
