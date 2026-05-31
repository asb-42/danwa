"""Tests for case management — CaseStore unit tests and API tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import (
    get_audit_service,
    get_case_store,
    get_current_user,
    get_debate_store,
    get_project_store,
    get_settings,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.case_store import CaseStore
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore

_TENANT = "_default"
_ALT_TENANT = "other-tenant"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def case_store(tmp_path) -> CaseStore:
    """Isolated CaseStore with temp directory."""
    return CaseStore(base_dir=tmp_path / "tenants")


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
def app(settings, audit_service, debate_store, project_store, case_store):
    """FastAPI app with overridden dependencies."""
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
    return application


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


# ===========================================================================
# CaseStore Unit Tests
# ===========================================================================


class TestCaseStoreCreate:
    def test_create_case(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Test Case", description="A test")
        assert case.title == "Test Case"
        assert case.description == "A test"
        assert case.status == "active"
        assert case.tags == []
        assert case.id

    def test_create_case_with_custom_id(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Custom", case_id="my-case")
        assert case.id == "my-case"

    def test_create_case_with_tags(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Tagged", tags=["tag1", "tag2"])
        assert case.tags == ["tag1", "tag2"]

    def test_create_persists_to_disk(self, case_store, tmp_path):
        case = case_store.create(tenant_id=_TENANT, title="Persisted")
        json_path = tmp_path / "tenants" / _TENANT / "cases" / case.id / "case.json"
        assert json_path.exists()

    def test_create_creates_subdirectories(self, case_store, tmp_path):
        case = case_store.create(tenant_id=_TENANT, title="Dirs")
        case_dir = tmp_path / "tenants" / _TENANT / "cases" / case.id
        assert (case_dir / "debates").is_dir()
        assert (case_dir / "dms").is_dir()

    def test_create_in_alt_tenant(self, case_store, tmp_path):
        case = case_store.create(tenant_id=_ALT_TENANT, title="Other")
        json_path = tmp_path / "tenants" / _ALT_TENANT / "cases" / case.id / "case.json"
        assert json_path.exists()


class TestCaseStoreGet:
    def test_get_existing_case(self, case_store):
        created = case_store.create(tenant_id=_TENANT, title="Find Me")
        found = case_store.get(_TENANT, created.id)
        assert found is not None
        assert found.title == "Find Me"

    def test_get_nonexistent_returns_none(self, case_store):
        assert case_store.get(_TENANT, "nonexistent") is None

    def test_get_wrong_tenant_returns_none(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Wrong Tenant")
        assert case_store.get(_ALT_TENANT, case.id) is None


class TestCaseStoreList:
    def test_list_empty(self, case_store):
        assert case_store.list_by_tenant(_TENANT) == []

    def test_list_returns_newest_first(self, case_store):
        case_store.create(tenant_id=_TENANT, title="First")
        case_store.create(tenant_id=_TENANT, title="Second")
        cases = case_store.list_by_tenant(_TENANT)
        assert len(cases) == 2
        assert cases[0].title == "Second"
        assert cases[1].title == "First"

    def test_list_tenant_isolation(self, case_store):
        case_store.create(tenant_id=_TENANT, title="Default")
        case_store.create(tenant_id=_ALT_TENANT, title="Other")
        assert len(case_store.list_by_tenant(_TENANT)) == 1
        assert len(case_store.list_by_tenant(_ALT_TENANT)) == 1


class TestCaseStoreUpdate:
    def test_update_title(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Old Title")
        updated = case_store.update(_TENANT, case.id, title="New Title")
        assert updated is not None
        assert updated.title == "New Title"

    def test_update_tags(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Tagged")
        updated = case_store.update(_TENANT, case.id, tags=["a", "b"])
        assert updated.tags == ["a", "b"]

    def test_update_status(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Status")
        updated = case_store.update(_TENANT, case.id, status="archived")
        assert updated.status == "archived"

    def test_update_nonexistent_returns_none(self, case_store):
        assert case_store.update(_TENANT, "nope", title="X") is None

    def test_update_persists_to_disk(self, case_store, tmp_path):
        case = case_store.create(tenant_id=_TENANT, title="Persist Update")
        case_store.update(_TENANT, case.id, title="Updated")
        fresh_store = CaseStore(base_dir=tmp_path / "tenants")
        reloaded = fresh_store.get(_TENANT, case.id)
        assert reloaded.title == "Updated"


class TestCaseStoreDelete:
    def test_delete_case(self, case_store):
        case = case_store.create(tenant_id=_TENANT, title="Delete Me")
        assert case_store.delete(_TENANT, case.id) is True
        assert case_store.get(_TENANT, case.id) is None

    def test_delete_removes_directory(self, case_store, tmp_path):
        case = case_store.create(tenant_id=_TENANT, title="Dir Delete")
        case_dir = tmp_path / "tenants" / _TENANT / "cases" / case.id
        assert case_dir.exists()
        case_store.delete(_TENANT, case.id)
        assert not case_dir.exists()

    def test_delete_default_case_refused(self, case_store):
        case_store.get_or_create_default(_TENANT)
        assert case_store.delete(_TENANT, "_default") is False
        assert case_store.get(_TENANT, "_default") is not None

    def test_delete_nonexistent_returns_false(self, case_store):
        assert case_store.delete(_TENANT, "nonexistent") is False


class TestCaseStoreHelpers:
    def test_get_or_create_default_creates(self, case_store):
        default = case_store.get_or_create_default(_TENANT)
        assert default.id == "_default"
        assert default.title == "Default"

    def test_get_or_create_default_returns_existing(self, case_store):
        d1 = case_store.get_or_create_default(_TENANT)
        d2 = case_store.get_or_create_default(_TENANT)
        assert d1.id == d2.id

    def test_count(self, case_store):
        assert case_store.count(_TENANT) == 0
        case_store.create(tenant_id=_TENANT, title="A")
        assert case_store.count(_TENANT) == 1
        case_store.create(tenant_id=_TENANT, title="B")
        assert case_store.count(_TENANT) == 2

    def test_get_case_dir(self, case_store, tmp_path):
        case = case_store.create(tenant_id=_TENANT, title="Dir Test")
        expected = tmp_path / "tenants" / _TENANT / "cases" / case.id
        assert case_store.get_case_dir(_TENANT, case.id) == expected


class TestCaseStorePersistence:
    def test_reload_from_disk(self, case_store, tmp_path):
        case_store.create(tenant_id=_TENANT, title="Persisted", case_id="c1")
        fresh = CaseStore(base_dir=tmp_path / "tenants")
        assert fresh.count(_TENANT) == 1
        assert fresh.get(_TENANT, "c1").title == "Persisted"

    def test_tenant_isolation_on_reload(self, case_store, tmp_path):
        case_store.create(tenant_id=_TENANT, title="Default", case_id="c1")
        case_store.create(tenant_id=_ALT_TENANT, title="Other", case_id="c1")
        fresh = CaseStore(base_dir=tmp_path / "tenants")
        assert fresh.get(_TENANT, "c1").title == "Default"
        assert fresh.get(_ALT_TENANT, "c1").title == "Other"


# ===========================================================================
# Cases API Tests
# ===========================================================================


class TestCasesAPIList:
    def test_list_empty(self, client):
        response = client.get(f"/api/v1/tenants/{_TENANT}/cases")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_cases(self, client):
        client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "Alpha"})
        client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "Beta"})
        response = client.get(f"/api/v1/tenants/{_TENANT}/cases")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        titles = {p["title"] for p in data}
        assert titles == {"Alpha", "Beta"}


class TestCasesAPICreate:
    def test_create_returns_201(self, client):
        response = client.post(
            f"/api/v1/tenants/{_TENANT}/cases",
            json={"title": "My Case", "description": "Test desc"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "My Case"
        assert data["description"] == "Test desc"
        assert data["status"] == "active"
        assert data["tags"] == []
        assert "id" in data

    def test_create_with_tags(self, client):
        response = client.post(
            f"/api/v1/tenants/{_TENANT}/cases",
            json={"title": "Tagged", "tags": ["urgent", "compliance"]},
        )
        assert response.status_code == 201
        assert response.json()["tags"] == ["urgent", "compliance"]

    def test_create_has_uuid(self, client):
        response = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "UUID Test"})
        uuid.UUID(response.json()["id"])

    def test_create_empty_title_rejected(self, client):
        response = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": ""})
        assert response.status_code == 422

    def test_create_missing_title_rejected(self, client):
        response = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={})
        assert response.status_code == 422


class TestCasesAPIGet:
    def test_get_existing_case(self, client):
        create_resp = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "Get Test"})
        case_id = create_resp.json()["id"]
        response = client.get(f"/api/v1/tenants/{_TENANT}/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["title"] == "Get Test"

    def test_get_nonexistent_returns_404(self, client):
        response = client.get(f"/api/v1/tenants/{_TENANT}/cases/nonexistent")
        assert response.status_code == 404


class TestCasesAPIUpdate:
    def test_update_title(self, client):
        create_resp = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "Old"})
        case_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/tenants/{_TENANT}/cases/{case_id}",
            json={"title": "New", "description": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["title"] == "New"
        assert response.json()["description"] == "Updated"

    def test_update_tags(self, client):
        create_resp = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "Tags"})
        case_id = create_resp.json()["id"]

        response = client.patch(
            f"/api/v1/tenants/{_TENANT}/cases/{case_id}",
            json={"tags": ["compliance"]},
        )
        assert response.status_code == 200
        assert response.json()["tags"] == ["compliance"]

    def test_update_nonexistent_returns_404(self, client):
        response = client.patch(f"/api/v1/tenants/{_TENANT}/cases/nope", json={"title": "X"})
        assert response.status_code == 404


class TestCasesAPIDelete:
    def test_delete_case(self, client):
        create_resp = client.post(f"/api/v1/tenants/{_TENANT}/cases", json={"title": "Delete"})
        case_id = create_resp.json()["id"]

        response = client.delete(f"/api/v1/tenants/{_TENANT}/cases/{case_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] == case_id

        get_resp = client.get(f"/api/v1/tenants/{_TENANT}/cases/{case_id}")
        assert get_resp.status_code == 404

    def test_delete_default_case_refused(self, client, case_store):
        case_store.get_or_create_default(_TENANT)
        response = client.delete(f"/api/v1/tenants/{_TENANT}/cases/_default")
        assert response.status_code == 403

    def test_delete_nonexistent_returns_404(self, client):
        response = client.delete(f"/api/v1/tenants/{_TENANT}/cases/nope")
        assert response.status_code == 404
