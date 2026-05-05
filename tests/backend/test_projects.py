"""Tests for project management — ProjectStore unit tests and API tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import (
    get_audit_service,
    get_debate_store,
    get_project_store,
    get_settings,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.project import ProjectConfig
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore


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
def app(settings, audit_service, debate_store, project_store):
    """FastAPI app with overridden dependencies including project_store."""
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
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
        json_path = tmp_path / "projects" / project.id / "project.json"
        assert json_path.exists()

    def test_create_creates_subdirectories(self, project_store, tmp_path):
        project = project_store.create(name="Dirs")
        project_dir = tmp_path / "projects" / project.id
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
        p1 = project_store.create(name="First")
        p2 = project_store.create(name="Second")
        projects = project_store.list_all()
        assert len(projects) == 2
        # Newest first (p2 created after p1)
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

        # Reload from disk to verify persistence
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
        project_dir = tmp_path / "projects" / project.id
        assert project_dir.exists()
        project_store.delete(project.id)
        assert not project_dir.exists()

    def test_delete_system_project_refused(self, project_store):
        project = project_store.create(name="System", is_system=True, project_id="sys")
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
        expected = tmp_path / "projects" / project.id
        assert project_store.get_project_dir(project.id) == expected


class TestProjectStorePersistence:
    def test_reload_from_disk(self, project_store, tmp_path):
        project_store.create(name="Persisted", project_id="p1")
        # Create a new store instance from the same directory
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
# Projects API Tests
# ===========================================================================


class TestProjectsAPIList:
    def test_list_empty_projects(self, client):
        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_projects(self, client):
        client.post("/api/v1/projects", json={"name": "Alpha"})
        client.post("/api/v1/projects", json={"name": "Beta"})
        response = client.get("/api/v1/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {p["name"] for p in data}
        assert names == {"Alpha", "Beta"}


class TestProjectsAPICreate:
    def test_create_project_returns_201(self, client):
        response = client.post(
            "/api/v1/projects",
            json={"name": "My Project", "description": "Test desc"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Project"
        assert data["description"] == "Test desc"
        assert data["is_system"] is False
        assert "id" in data
        assert "config" in data

    def test_create_project_has_uuid(self, client):
        response = client.post("/api/v1/projects", json={"name": "UUID Test"})
        project_id = response.json()["id"]
        uuid.UUID(project_id)  # raises if invalid

    def test_create_project_minimal(self, client):
        response = client.post("/api/v1/projects", json={"name": "Minimal"})
        assert response.status_code == 201
        assert response.json()["description"] == ""

    def test_create_project_empty_name_rejected(self, client):
        response = client.post("/api/v1/projects", json={"name": ""})
        assert response.status_code == 422

    def test_create_project_missing_name_rejected(self, client):
        response = client.post("/api/v1/projects", json={})
        assert response.status_code == 422


class TestProjectsAPIGet:
    def test_get_existing_project(self, client):
        create_resp = client.post("/api/v1/projects", json={"name": "Get Test"})
        project_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Test"

    def test_get_nonexistent_returns_404(self, client):
        response = client.get("/api/v1/projects/nonexistent")
        assert response.status_code == 404


class TestProjectsAPIUpdate:
    def test_update_project_name(self, client):
        create_resp = client.post("/api/v1/projects", json={"name": "Old"})
        project_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/projects/{project_id}",
            json={"name": "New", "description": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New"
        assert response.json()["description"] == "Updated"

    def test_update_nonexistent_returns_404(self, client):
        response = client.put(
            "/api/v1/projects/nope", json={"name": "X"}
        )
        assert response.status_code == 404


class TestProjectsAPIDelete:
    def test_delete_project(self, client):
        create_resp = client.post("/api/v1/projects", json={"name": "Delete"})
        project_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/projects/{project_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] == project_id

        # Verify gone
        get_resp = client.get(f"/api/v1/projects/{project_id}")
        assert get_resp.status_code == 404

    def test_delete_system_project_refused(self, client, project_store):
        project_store.create(name="System", is_system=True, project_id="sys")
        response = client.delete("/api/v1/projects/sys")
        assert response.status_code == 403

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete("/api/v1/projects/nope")
        assert response.status_code == 404


class TestProjectsAPIConfig:
    def test_get_default_config(self, client):
        create_resp = client.post("/api/v1/projects", json={"name": "Config"})
        project_id = create_resp.json()["id"]

        response = client.get(f"/api/v1/projects/{project_id}/config")
        assert response.status_code == 200
        config = response.json()
        assert config["language"] is None
        assert config["default_max_rounds"] is None
        assert config["search_mode"] is None

    def test_update_config(self, client):
        create_resp = client.post("/api/v1/projects", json={"name": "Config Update"})
        project_id = create_resp.json()["id"]

        response = client.put(
            f"/api/v1/projects/{project_id}/config",
            json={"config": {"language": "en", "default_max_rounds": 5}},
        )
        assert response.status_code == 200
        config = response.json()["config"]
        assert config["language"] == "en"
        assert config["default_max_rounds"] == 5

    def test_update_config_persists(self, client):
        create_resp = client.post("/api/v1/projects", json={"name": "Persist Config"})
        project_id = create_resp.json()["id"]

        client.put(
            f"/api/v1/projects/{project_id}/config",
            json={"config": {"search_mode": "required"}},
        )

        get_resp = client.get(f"/api/v1/projects/{project_id}/config")
        assert get_resp.json()["search_mode"] == "required"

    def test_get_config_nonexistent_returns_404(self, client):
        response = client.get("/api/v1/projects/nope/config")
        assert response.status_code == 404

    def test_update_config_nonexistent_returns_404(self, client):
        response = client.put(
            "/api/v1/projects/nope/config",
            json={"config": {"language": "en"}},
        )
        assert response.status_code == 404
