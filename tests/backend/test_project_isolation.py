"""Tests for project isolation — debates in Project A must not leak into Project B.

These tests verify the core isolation guarantee: data created under one project
is invisible when querying under a different project.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api import deps as deps_module
from backend.api.deps import (
    get_audit_service,
    get_debate_store,
    get_project_store,
    get_settings,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_store(tmp_path) -> ProjectStore:
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
def app(settings, audit_service, debate_store, project_store, monkeypatch):
    """FastAPI app with overridden dependencies.

    We also monkeypatch the module-level ``get_project_store`` function because
    ``get_debate_store_for_project`` and ``get_project_id`` call it directly
    (not via FastAPI DI), and the ``@lru_cache`` would otherwise return the
    original singleton.
    """
    # Clear the lru_cache so monkeypatch takes effect
    get_project_store.cache_clear()
    monkeypatch.setattr(deps_module, "get_project_store", lambda: project_store)

    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    return application


@pytest.fixture()
def client(app) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def two_projects(client) -> tuple[str, str]:
    """Create two projects and return (project_a_id, project_b_id)."""
    resp_a = client.post(
        "/api/v1/projects",
        json={"name": "Project A", "description": "First project"},
    )
    resp_b = client.post(
        "/api/v1/projects",
        json={"name": "Project B", "description": "Second project"},
    )
    assert resp_a.status_code == 201
    assert resp_b.status_code == 201
    return resp_a.json()["id"], resp_b.json()["id"]


def _headers(project_id: str) -> dict[str, str]:
    """Build X-Project-Id header."""
    return {"X-Project-Id": project_id}


# ===========================================================================
# Debate Isolation
# ===========================================================================


class TestDebateIsolation:
    """Debates created in one project must not be visible in another."""

    def test_debate_scoped_to_project(self, client, two_projects):
        pa, pb = two_projects

        # Create debate in Project A
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Debate in project A"}},
            headers=_headers(pa),
        )
        assert create_resp.status_code == 201
        debate_id = create_resp.json()["debate_id"]

        # List debates in Project A — should contain the debate
        list_a = client.get("/api/v1/debate", headers=_headers(pa))
        assert list_a.status_code == 200
        a_ids = [d["debate_id"] for d in list_a.json()]
        assert debate_id in a_ids

        # List debates in Project B — should NOT contain the debate
        list_b = client.get("/api/v1/debate", headers=_headers(pb))
        assert list_b.status_code == 200
        b_ids = [d["debate_id"] for d in list_b.json()]
        assert debate_id not in b_ids

    def test_debate_not_found_in_wrong_project(self, client, two_projects):
        pa, pb = two_projects

        # Create debate in Project A
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Cross-project access test"}},
            headers=_headers(pa),
        )
        debate_id = create_resp.json()["debate_id"]

        # Try to get debate from Project B — should 404
        get_resp = client.get(
            f"/api/v1/debate/{debate_id}",
            headers=_headers(pb),
        )
        assert get_resp.status_code == 404

    def test_multiple_debates_isolated(self, client, two_projects):
        pa, pb = two_projects

        # Create 3 debates in A, 2 in B
        for i in range(3):
            client.post(
                "/api/v1/debate",
                json={"case": {"text": f"A debate {i}"}},
                headers=_headers(pa),
            )
        for i in range(2):
            client.post(
                "/api/v1/debate",
                json={"case": {"text": f"B debate {i}"}},
                headers=_headers(pb),
            )

        list_a = client.get("/api/v1/debate", headers=_headers(pa))
        list_b = client.get("/api/v1/debate", headers=_headers(pb))

        assert len(list_a.json()) == 3
        assert len(list_b.json()) == 2

    def test_delete_debate_in_one_project(self, client, two_projects):
        pa, pb = two_projects

        # Create debate in A
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Delete test"}},
            headers=_headers(pa),
        )
        debate_id = create_resp.json()["debate_id"]

        # Delete from A
        del_resp = client.delete(
            f"/api/v1/debate/{debate_id}",
            headers=_headers(pa),
        )
        assert del_resp.status_code == 200

        # Verify gone from A
        get_resp = client.get(
            f"/api/v1/debate/{debate_id}",
            headers=_headers(pa),
        )
        assert get_resp.status_code == 404


# ===========================================================================
# Header Validation
# ===========================================================================


class TestHeaderValidation:
    """X-Project-Id header is required for project-scoped endpoints."""

    def test_missing_header_returns_422(self, client):
        response = client.get("/api/v1/debate")
        assert response.status_code == 422

    def test_invalid_project_id_returns_404(self, client):
        response = client.get(
            "/api/v1/debate",
            headers={"X-Project-Id": "nonexistent-project"},
        )
        assert response.status_code == 404

    def test_valid_project_id_accepted(self, client, two_projects):
        pa, _ = two_projects
        response = client.get("/api/v1/debate", headers=_headers(pa))
        assert response.status_code == 200


# ===========================================================================
# Config Isolation
# ===========================================================================


class TestConfigIsolation:
    """Project configs are independent — changing one doesn't affect the other."""

    def test_independent_configs(self, client, two_projects):
        pa, pb = two_projects

        # Set config for Project A
        client.put(
            f"/api/v1/projects/{pa}/config",
            json={"config": {"language": "en", "default_max_rounds": 10}},
        )

        # Set different config for Project B
        client.put(
            f"/api/v1/projects/{pb}/config",
            json={"config": {"language": "de", "default_max_rounds": 3}},
        )

        # Verify A's config
        config_a = client.get(f"/api/v1/projects/{pa}/config").json()
        assert config_a["language"] == "en"
        assert config_a["default_max_rounds"] == 10

        # Verify B's config
        config_b = client.get(f"/api/v1/projects/{pb}/config").json()
        assert config_b["language"] == "de"
        assert config_b["default_max_rounds"] == 3

    def test_config_update_does_not_affect_other_project(self, client, two_projects):
        pa, pb = two_projects

        # Set initial config for both
        client.put(
            f"/api/v1/projects/{pa}/config",
            json={"config": {"language": "en"}},
        )
        client.put(
            f"/api/v1/projects/{pb}/config",
            json={"config": {"language": "de"}},
        )

        # Update A's config
        client.put(
            f"/api/v1/projects/{pa}/config",
            json={"config": {"language": "fr"}},
        )

        # B should still be "de"
        config_b = client.get(f"/api/v1/projects/{pb}/config").json()
        assert config_b["language"] == "de"


# ===========================================================================
# Project CRUD Isolation
# ===========================================================================


class TestProjectCRUDIsolation:
    """Project operations don't interfere with each other."""

    def test_delete_project_does_not_affect_others(self, client, two_projects):
        pa, pb = two_projects

        # Delete A
        del_resp = client.delete(f"/api/v1/projects/{pa}")
        assert del_resp.status_code == 200

        # B should still exist
        get_resp = client.get(f"/api/v1/projects/{pb}")
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Project B"

    def test_update_project_does_not_affect_others(self, client, two_projects):
        pa, pb = two_projects

        # Update A
        client.put(
            f"/api/v1/projects/{pa}",
            json={"name": "Renamed A", "description": "New desc"},
        )

        # B should be unchanged
        get_resp = client.get(f"/api/v1/projects/{pb}")
        assert get_resp.json()["name"] == "Project B"
        assert get_resp.json()["description"] == "Second project"


# ===========================================================================
# Filesystem Isolation
# ===========================================================================


class TestFilesystemIsolation:
    """Each project has its own directory structure."""

    def test_project_directories_are_separate(self, project_store, tmp_path):
        project_store.create(name="P1", project_id="proj-1")
        project_store.create(name="P2", project_id="proj-2")

        dir1 = project_store.get_project_dir("proj-1")
        dir2 = project_store.get_project_dir("proj-2")

        assert dir1 != dir2
        assert dir1.is_dir()
        assert dir2.is_dir()
        assert (dir1 / "debates").is_dir()
        assert (dir2 / "debates").is_dir()

    def test_debate_stores_are_isolated(self, tmp_path):
        """DebateStore instances for different projects use different directories."""
        store = ProjectStore(base_dir=tmp_path / "projects")
        store.create(name="P1", project_id="p1")
        store.create(name="P2", project_id="p2")

        ds1 = DebateStore(data_dir=store.get_project_dir("p1") / "debates")
        ds2 = DebateStore(data_dir=store.get_project_dir("p2") / "debates")

        # Put a debate in ds1
        ds1.put("d1", {"debate_id": "d1", "status": "pending", "case": {"text": "test"}})

        # ds2 should not see it
        assert ds1.get("d1") is not None
        assert ds2.get("d1") is None
        assert len(ds2.list_all()) == 0
