"""Tests for project management — ProjectStore unit tests and tenant/case API tests."""

from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.api import deps as deps_module
from backend.api.deps import (
    get_audit_service,
    get_case_store,
    get_current_user,
    get_debate_store,
    get_project_store,
    get_settings,
    get_tenant_store,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.project import ProjectConfig
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.case_store import CaseStore
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore
from backend.persistence.tenant_store import TenantStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_store(tmp_path) -> ProjectStore:
    """Isolated ProjectStore with temp directory."""
    return ProjectStore(base_dir=tmp_path / "projects")


@pytest.fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=tmp_path / "test_audit.db",
        cors_origins=["http://testserver"],
        debug=True,
    )


@pytest.fixture()
def audit_service(tmp_path) -> AuditService:
    return AuditService(db_path=tmp_path / "test_audit.db")


@pytest.fixture()
def debate_store(tmp_path) -> DebateStore:
    return DebateStore(data_dir=tmp_path / "test_debates")


@pytest.fixture()
def tenant_store(tmp_path) -> TenantStore:
    return TenantStore(db_path=tmp_path / "test_tenant.db")


@pytest.fixture()
def case_store(tmp_path) -> CaseStore:
    return CaseStore(base_dir=tmp_path / "test_cases")


@pytest.fixture()
def default_tenant(tenant_store):
    existing = tenant_store.get("_default")
    if existing:
        return existing.id
    return tenant_store.create("Default Tenant", tenant_id="_default").id


@pytest.fixture()
def app(settings, audit_service, debate_store, project_store, tenant_store, case_store, default_tenant):
    """FastAPI app with overridden dependencies."""
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
    application.dependency_overrides[get_tenant_store] = lambda: tenant_store
    application.dependency_overrides[get_case_store] = lambda: case_store

    mpatch = mock.patch.multiple(
        deps_module,
        get_project_store=mock.MagicMock(return_value=project_store),
        get_tenant_store=mock.MagicMock(return_value=tenant_store),
        get_case_store=mock.MagicMock(return_value=case_store),
    )
    mpatch.start()
    application.state._deps_monkeypatch = mpatch
    return application


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


# ===========================================================================
# ProjectStore Unit Tests
# ===========================================================================


class TestProjectStoreCreate:
    def test_create_project(self, project_store):
        project = project_store.create(name="Test Project", description="A test")
        assert project.name == "Test Project"
        assert project.description == "A test"
        assert project.is_system is False
        assert project.id  # UUID generated

    def test_create_project_with_custom_id(self, project_store):
        project = project_store.create(name="Custom", project_id="my-id")
        assert project.id == "my-id"

    def test_create_system_project(self, project_store):
        project = project_store.create(name="System", is_system=True, project_id="sys")
        assert project.is_system is True

    def test_create_persists_to_disk(self, project_store, tmp_path):
        project = project_store.create(name="Persisted")
        json_path = tmp_path / "projects" / "_default" / "cases" / project.id / "project.json"
        assert json_path.exists()

    def test_create_creates_subdirectories(self, project_store, tmp_path):
        project = project_store.create(name="Dirs")
        project_dir = tmp_path / "projects" / "_default" / "cases" / project.id
        assert (project_dir / "debates").is_dir()
        assert (project_dir / "dms").is_dir()

    def test_create_default_config(self, project_store):
        project = project_store.create(name="Config Test")
        assert project.config.language is None
        assert project.config.default_max_rounds is None
        assert project.config.search_mode is None


class TestProjectStoreGet:
    def test_get_existing_project(self, project_store):
        created = project_store.create(name="Find Me")
        found = project_store.get(created.id)
        assert found is not None
        assert found.name == "Find Me"

    def test_get_nonexistent_returns_none(self, project_store):
        assert project_store.get("nonexistent") is None


class TestProjectStoreList:
    def test_list_empty(self, project_store):
        assert project_store.list_all() == []

    def test_list_returns_newest_first(self, project_store):
        project_store.create(name="First")
        project_store.create(name="Second")
        projects = project_store.list_all()
        assert len(projects) == 2
        assert projects[0].name == "Second"
        assert projects[1].name == "First"


class TestProjectStoreUpdate:
    def test_update_name(self, project_store):
        project = project_store.create(name="Old Name")
        updated = project_store.update(project.id, name="New Name")
        assert updated is not None
        assert updated.name == "New Name"

    def test_update_description(self, project_store):
        project = project_store.create(name="Proj", description="old")
        updated = project_store.update(project.id, description="new desc")
        assert updated.description == "new desc"

    def test_update_config(self, project_store):
        project = project_store.create(name="Config")
        new_config = ProjectConfig(language="en", default_max_rounds=5)
        updated = project_store.update(project.id, config=new_config)
        assert updated.config.language == "en"
        assert updated.config.default_max_rounds == 5

    def test_update_config_as_dict(self, project_store):
        project = project_store.create(name="Dict Config")
        updated = project_store.update(project.id, config={"language": "de"})
        assert updated.config.language == "de"

    def test_update_nonexistent_returns_none(self, project_store):
        assert project_store.update("nope", name="X") is None

    def test_update_persists_to_disk(self, project_store, tmp_path):
        project = project_store.create(name="Persist Update")
        project_store.update(project.id, name="Updated")

        fresh_store = ProjectStore(base_dir=tmp_path / "projects")
        reloaded = fresh_store.get(project.id)
        assert reloaded.name == "Updated"


class TestProjectStoreDelete:
    def test_delete_project(self, project_store):
        project = project_store.create(name="Delete Me")
        assert project_store.delete(project.id) is True
        assert project_store.get(project.id) is None

    def test_delete_removes_directory(self, project_store, tmp_path):
        project = project_store.create(name="Dir Delete")
        project_dir = tmp_path / "projects" / "_default" / "cases" / project.id
        assert project_dir.exists()
        project_store.delete(project.id)
        assert not project_dir.exists()

    def test_delete_system_project_refused(self, project_store):
        project_store.create(name="System", is_system=True, project_id="sys")
        assert project_store.delete("sys") is False
        assert project_store.get("sys") is not None

    def test_delete_nonexistent_returns_false(self, project_store):
        assert project_store.delete("nonexistent") is False


class TestProjectStoreHelpers:
    def test_get_or_create_default_creates(self, project_store):
        default = project_store.get_or_create_default()
        assert default.id == "_default"
        assert default.is_system is True
        assert default.name == "Default"

    def test_get_or_create_default_returns_existing(self, project_store):
        d1 = project_store.get_or_create_default()
        d2 = project_store.get_or_create_default()
        assert d1.id == d2.id

    def test_count(self, project_store):
        assert project_store.count() == 0
        project_store.create(name="A")
        assert project_store.count() == 1
        project_store.create(name="B")
        assert project_store.count() == 2

    def test_get_project_dir(self, project_store, tmp_path):
        project = project_store.create(name="Dir Test")
        expected = tmp_path / "projects" / "_default" / "cases" / project.id
        assert project_store.get_project_dir(project.id) == expected
        assert expected.is_dir()


class TestProjectStorePersistence:
    def test_reload_from_disk(self, project_store, tmp_path):
        project_store.create(name="Persisted", project_id="p1")
        fresh = ProjectStore(base_dir=tmp_path / "projects")
        assert fresh.count() == 1
        assert fresh.get("p1").name == "Persisted"

    def test_config_persists_through_reload(self, project_store, tmp_path):
        project = project_store.create(name="Config Persist", project_id="p2")
        project_store.update(
            project.id,
            config=ProjectConfig(language="en", default_max_rounds=7),
        )
        fresh = ProjectStore(base_dir=tmp_path / "projects")
        reloaded = fresh.get("p2")
        assert reloaded.config.language == "en"
        assert reloaded.config.default_max_rounds == 7


# ===========================================================================
# Cases API Tests (replaces deprecated Projects API tests)
# ===========================================================================


class TestCasesAPIList:
    def test_list_empty_cases(self, client, default_tenant):
        response = client.get(f"/api/v1/tenants/{default_tenant}/cases")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_cases(self, client, default_tenant):
        client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "Alpha", "description": ""},
        )
        client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "Beta", "description": ""},
        )
        response = client.get(f"/api/v1/tenants/{default_tenant}/cases")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        titles = {c["title"] for c in data}
        assert titles == {"Alpha", "Beta"}


class TestCasesAPICreate:
    def test_create_case_returns_201(self, client, default_tenant):
        response = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "My Case", "description": "Test desc"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Case"
        assert data["description"] == "Test desc"
        assert "id" in data

    def test_create_case_minimal(self, client, default_tenant):
        response = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "Minimal"},
        )
        assert response.status_code == 201
        assert response.json()["description"] == ""

    def test_create_case_empty_title_rejected(self, client, default_tenant):
        response = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": ""},
        )
        assert response.status_code == 422

    def test_create_case_missing_title_rejected(self, client, default_tenant):
        response = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={},
        )
        assert response.status_code == 422

    def test_create_case_system_default(self, client, default_tenant):
        response = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "System"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "System"
        assert data["status"] == "active"


class TestCasesAPIGet:
    def test_get_existing_case(self, client, default_tenant):
        create_resp = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "Get Test"},
        )
        case_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/tenants/{default_tenant}/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Get Test"

    def test_get_nonexistent_returns_404(self, client, default_tenant):
        response = client.get(f"/api/v1/tenants/{default_tenant}/cases/nonexistent")
        assert response.status_code == 404


class TestCasesAPIUpdate:
    def test_update_case(self, client, default_tenant):
        create_resp = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "Old"},
        )
        case_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/tenants/{default_tenant}/cases/{case_id}",
            json={"title": "New"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New"

    def test_update_nonexistent_returns_404(self, client, default_tenant):
        response = client.patch(
            f"/api/v1/tenants/{default_tenant}/cases/nope",
            json={"title": "X"},
        )
        assert response.status_code == 404


class TestCasesAPIDelete:
    def test_delete_case(self, client, default_tenant):
        create_resp = client.post(
            f"/api/v1/tenants/{default_tenant}/cases",
            json={"title": "Delete"},
        )
        case_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/tenants/{default_tenant}/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] == case_id

        get_resp = client.get(f"/api/v1/tenants/{default_tenant}/cases/{case_id}")
        assert get_resp.status_code == 404

    def test_delete_system_case_refused(self, client, default_tenant, case_store):
        case_store.create(
            tenant_id=default_tenant,
            title="System",
            case_id="_default",
            is_system=True,
        )
        response = client.delete(f"/api/v1/tenants/{default_tenant}/cases/_default")
        assert response.status_code == 403

    def test_delete_nonexistent_returns_404(self, client, default_tenant):
        response = client.delete(f"/api/v1/tenants/{default_tenant}/cases/nope")
        assert response.status_code == 404
