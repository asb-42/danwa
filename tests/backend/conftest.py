"""Shared test fixtures for backend tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import (
    get_audit_service,
    get_current_user,
    get_debate_store,
    get_project_id,
    get_project_store,
    get_settings,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore


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
def default_project(project_store):
    """Ensure a default project exists and return its ID."""
    project = project_store.get_or_create_default()
    return project.id


@pytest.fixture()
def app(settings, audit_service, debate_store, project_store, default_project):
    """FastAPI app with overridden dependencies."""
    get_project_store.cache_clear()
    application = create_app()

    _test_user = User(
        id="test-user",
        email="test@danwa.local",
        display_name="Test User",
        password_hash="",
        role="admin",
        tenant_id="_default",
    )

    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_current_user] = lambda: _test_user
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    application.dependency_overrides[get_project_id] = lambda: default_project
    # Store for test helpers to access via client.app.state.test_project_store
    application.state.test_project_store = project_store
    return application


@pytest.fixture(autouse=True)
def _clear_dms_cache():
    """Clear the DMS instance cache between tests."""
    from backend.services.dms.service import _dms_cache

    _dms_cache.clear()
    yield
    _dms_cache.clear()


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client."""
    return TestClient(app)
