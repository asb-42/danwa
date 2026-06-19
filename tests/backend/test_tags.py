"""Tests for tag management — TagStore unit tests and API tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import (
    get_audit_service,
    get_case_store,
    get_current_user,
    get_debate_store,
    get_project_store,
    get_settings,
    get_tag_store,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.case_store import CaseStore
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore
from backend.persistence.tag_store import TagStore

_TENANT = "_default"
_ALT_TENANT = "other-tenant"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tag_store(tmp_path) -> TagStore:
    return TagStore(base_dir=tmp_path / "tenants")


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
def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(base_dir=tmp_path / "projects")


@pytest.fixture()
def case_store(tmp_path) -> CaseStore:
    return CaseStore(base_dir=tmp_path / "tenants")


@pytest.fixture()
def app(settings, audit_service, debate_store, project_store, case_store, tag_store):
    application = create_app()

    _test_user = User(
        id="test-user",
        email="test@danwa.local",
        display_name="Test User",
        password_hash="",
        role="admin",
        tenant_id=_TENANT,
    )

    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_current_user] = lambda: _test_user
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    application.dependency_overrides[get_case_store] = lambda: case_store
    application.dependency_overrides[get_tag_store] = lambda: tag_store
    return application


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


# ===========================================================================
# TagStore Unit Tests
# ===========================================================================


class TestTagStoreCreate:
    def test_create_tag(self, tag_store):
        tag = tag_store.create(tenant_id=_TENANT, name="Urgent")
        assert tag.name == "Urgent"
        assert tag.color == "#6366f1"
        assert tag.parent_id is None
        assert tag.id

    def test_create_tag_with_color(self, tag_store):
        tag = tag_store.create(tenant_id=_TENANT, name="Red", color="#ff0000")
        assert tag.color == "#ff0000"

    def test_create_tag_with_parent(self, tag_store):
        parent = tag_store.create(tenant_id=_TENANT, name="Parent")
        child = tag_store.create(tenant_id=_TENANT, name="Child", parent_id=parent.id)
        assert child.parent_id == parent.id

    def test_create_persists_to_disk(self, tag_store, tmp_path):
        tag_store.create(tenant_id=_TENANT, name="Persist")
        tags_path = tmp_path / "tenants" / _TENANT / "tags.json"
        assert tags_path.exists()


class TestTagStoreGet:
    def test_get_existing_tag(self, tag_store):
        created = tag_store.create(tenant_id=_TENANT, name="Find Me")
        found = tag_store.get(_TENANT, created.id)
        assert found is not None
        assert found.name == "Find Me"

    def test_get_nonexistent_returns_none(self, tag_store):
        assert tag_store.get(_TENANT, "nonexistent") is None


class TestTagStoreList:
    def test_list_empty(self, tag_store):
        assert tag_store.list_by_tenant(_TENANT) == []

    def test_list_returns_alphabetical(self, tag_store):
        tag_store.create(tenant_id=_TENANT, name="Zebra")
        tag_store.create(tenant_id=_TENANT, name="Alpha")
        tags = tag_store.list_by_tenant(_TENANT)
        assert len(tags) == 2
        assert tags[0].name == "Alpha"
        assert tags[1].name == "Zebra"

    def test_list_tenant_isolation(self, tag_store):
        tag_store.create(tenant_id=_TENANT, name="Default")
        tag_store.create(tenant_id=_ALT_TENANT, name="Other")
        assert len(tag_store.list_by_tenant(_TENANT)) == 1
        assert len(tag_store.list_by_tenant(_ALT_TENANT)) == 1


class TestTagStoreUpdate:
    def test_update_name(self, tag_store):
        tag = tag_store.create(tenant_id=_TENANT, name="Old")
        updated = tag_store.update(_TENANT, tag.id, name="New")
        assert updated.name == "New"

    def test_update_color(self, tag_store):
        tag = tag_store.create(tenant_id=_TENANT, name="Tag")
        updated = tag_store.update(_TENANT, tag.id, color="#00ff00")
        assert updated.color == "#00ff00"

    def test_update_nonexistent_returns_none(self, tag_store):
        assert tag_store.update(_TENANT, "nope", name="X") is None

    def test_update_persists_to_disk(self, tag_store, tmp_path):
        tag = tag_store.create(tenant_id=_TENANT, name="Persist")
        tag_store.update(_TENANT, tag.id, name="Updated")
        fresh_store = TagStore(base_dir=tmp_path / "tenants")
        reloaded = fresh_store.get(_TENANT, tag.id)
        assert reloaded.name == "Updated"


class TestTagStoreDelete:
    def test_delete_tag(self, tag_store):
        tag = tag_store.create(tenant_id=_TENANT, name="Delete Me")
        assert tag_store.delete(_TENANT, tag.id) is True
        assert tag_store.get(_TENANT, tag.id) is None

    def test_delete_nonexistent_returns_false(self, tag_store):
        assert tag_store.delete(_TENANT, "nonexistent") is False


class TestTagStorePersistence:
    def test_reload_from_disk(self, tag_store, tmp_path):
        tag_store.create(tenant_id=_TENANT, name="Persisted")
        fresh = TagStore(base_dir=tmp_path / "tenants")
        assert len(fresh.list_by_tenant(_TENANT)) == 1

    def test_tenant_isolation_on_reload(self, tag_store, tmp_path):
        tag_store.create(tenant_id=_TENANT, name="Default")
        tag_store.create(tenant_id=_ALT_TENANT, name="Other")
        fresh = TagStore(base_dir=tmp_path / "tenants")
        assert len(fresh.list_by_tenant(_TENANT)) == 1
        assert len(fresh.list_by_tenant(_ALT_TENANT)) == 1


# ===========================================================================
# Tags API Tests
# ===========================================================================


class TestTagsAPIList:
    def test_list_empty(self, client):
        response = client.get(f"/api/v1/tenants/{_TENANT}/tags")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_tags(self, client):
        client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Alpha"})
        client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Beta"})
        response = client.get(f"/api/v1/tenants/{_TENANT}/tags")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        names = {t["name"] for t in data}
        assert names == {"Alpha", "Beta"}


class TestTagsAPICreate:
    def test_create_returns_201(self, client):
        response = client.post(
            f"/api/v1/tenants/{_TENANT}/tags",
            json={"name": "Urgent", "color": "#ff0000"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Urgent"
        assert data["color"] == "#ff0000"
        assert "tag_id" in data

    def test_create_default_color(self, client):
        response = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Default"})
        assert response.json()["color"] == "#6366f1"

    def test_create_with_parent(self, client):
        parent = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Parent"}).json()
        child = client.post(
            f"/api/v1/tenants/{_TENANT}/tags",
            json={"name": "Child", "parent_id": parent["tag_id"]},
        ).json()
        assert child["parent_id"] == parent["tag_id"]

    def test_create_empty_name_rejected(self, client):
        response = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": ""})
        assert response.status_code == 422

    def test_create_missing_name_rejected(self, client):
        response = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={})
        assert response.status_code == 422


class TestTagsAPIGet:
    def test_get_existing_tag(self, client):
        create_resp = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Get Me"})
        tag_id = create_resp.json()["tag_id"]
        response = client.get(f"/api/v1/tenants/{_TENANT}/tags/{tag_id}")
        assert response.status_code == 200
        assert response.json()["name"] == "Get Me"

    def test_get_nonexistent_returns_404(self, client):
        response = client.get(f"/api/v1/tenants/{_TENANT}/tags/nonexistent")
        assert response.status_code == 404


class TestTagsAPIUpdate:
    def test_update_name(self, client):
        tag = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Old"}).json()
        response = client.put(
            f"/api/v1/tenants/{_TENANT}/tags/{tag['tag_id']}",
            json={"name": "New", "color": "#00ff00"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New"
        assert response.json()["color"] == "#00ff00"

    def test_update_nonexistent_returns_404(self, client):
        response = client.put(f"/api/v1/tenants/{_TENANT}/tags/nope", json={"name": "X"})
        assert response.status_code == 404


class TestTagsAPIDelete:
    def test_delete_tag(self, client):
        tag = client.post(f"/api/v1/tenants/{_TENANT}/tags", json={"name": "Delete"}).json()
        response = client.delete(f"/api/v1/tenants/{_TENANT}/tags/{tag['tag_id']}")
        assert response.status_code == 200
        assert response.json()["deleted"] == tag["tag_id"]

        get_resp = client.get(f"/api/v1/tenants/{_TENANT}/tags/{tag['tag_id']}")
        assert get_resp.status_code == 404

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete(f"/api/v1/tenants/{_TENANT}/tags/nope")
        assert response.status_code == 404
