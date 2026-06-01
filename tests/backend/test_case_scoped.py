"""Tests for case-scoped API router (tenant/case path-based endpoints)."""

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
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.case_store import CaseStore
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore


@pytest.fixture()
def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(base_dir=tmp_path / "test_projects")


@pytest.fixture()
def case_store(tmp_path) -> CaseStore:
    return CaseStore(base_dir=tmp_path / "test_cases")


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
def app(settings, audit_service, debate_store, project_store, case_store):
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
    application.dependency_overrides[get_case_store] = lambda: case_store
    return application


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def case_id(client) -> str:
    """Create a case and return its ID."""
    resp = client.post("/api/v1/tenants/_default/cases", json={"title": "Test Case"})
    assert resp.status_code == 201
    return resp.json()["id"]


class TestCaseDebateEndpoints:
    def test_create_debate(self, client, case_id):
        resp = client.post(
            f"/api/v1/tenants/_default/cases/{case_id}/debates",
            json={"case": {"text": "Should we?"}},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "debate_id" in data
        assert data["status"] == "pending"

    def test_list_debates_empty(self, client, case_id):
        resp = client.get(f"/api/v1/tenants/_default/cases/{case_id}/debates")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_debates_with_data(self, client, case_id):
        client.post(f"/api/v1/tenants/_default/cases/{case_id}/debates", json={"case": {"text": "D1"}})
        client.post(f"/api/v1/tenants/_default/cases/{case_id}/debates", json={"case": {"text": "D2"}})
        resp = client.get(f"/api/v1/tenants/_default/cases/{case_id}/debates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_get_debate(self, client, case_id):
        create_resp = client.post(f"/api/v1/tenants/_default/cases/{case_id}/debates", json={"case": {"text": "Get me"}})
        debate_id = create_resp.json()["debate_id"]

        resp = client.get(f"/api/v1/tenants/_default/cases/{case_id}/debates/{debate_id}")
        assert resp.status_code == 200
        assert resp.json()["debate_id"] == debate_id

    def test_delete_debate(self, client, case_id):
        create_resp = client.post(f"/api/v1/tenants/_default/cases/{case_id}/debates", json={"case": {"text": "Delete me"}})
        debate_id = create_resp.json()["debate_id"]

        resp = client.delete(f"/api/v1/tenants/_default/cases/{case_id}/debates/{debate_id}")
        assert resp.status_code == 200

        # Verify gone
        get_resp = client.get(f"/api/v1/tenants/_default/cases/{case_id}/debates/{debate_id}")
        assert get_resp.status_code == 404

    def test_case_not_found_returns_404(self, client):
        resp = client.get("/api/v1/tenants/_default/cases/nonexistent/debates")
        assert resp.status_code == 404


class TestCaseDMSEndpoints:
    def test_list_documents_empty(self, client, case_id):
        resp = client.get(f"/api/v1/tenants/_default/cases/{case_id}/dms/documents")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_case_not_found_returns_404_for_dms(self, client):
        resp = client.get("/api/v1/tenants/_default/cases/nonexistent/dms/documents")
        assert resp.status_code == 404
