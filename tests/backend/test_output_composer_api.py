"""Tests for Output Composer API endpoints.

Uses httpx AsyncClient against the FastAPI test app.
"""

from __future__ import annotations

from unittest import mock

import pytest
from httpx import ASGITransport, AsyncClient

from backend.api import deps as deps_module
from backend.api.deps import get_current_user, get_project_id, get_project_store
from backend.main import create_app
from backend.models.user import User
from backend.persistence.project_store import ProjectStore


@pytest.fixture
def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(base_dir=tmp_path / "projects")


@pytest.fixture
def default_project(project_store):
    return project_store.get_or_create_default().id


@pytest.fixture
def app(project_store, default_project):
    application = create_app()
    _test_user = User(
        id="test-user",
        email="test@danwa.local",
        display_name="Test User",
        password_hash="",
        role="admin",
        tenant_id="_default",
    )
    application.dependency_overrides[get_current_user] = lambda: _test_user
    application.dependency_overrides[get_project_id] = lambda: default_project
    application.dependency_overrides[get_project_store] = lambda: project_store

    mpatch = mock.patch.object(deps_module, "get_project_store", return_value=project_store)
    mpatch.start()
    application.state._deps_monkeypatch = mpatch
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestOutputPluginsEndpoint:
    async def test_list_plugins(self, client: AsyncClient):
        res = await client.get("/api/v1/output-plugins")
        assert res.status_code == 200
        plugins = res.json()
        assert isinstance(plugins, list)
        keys = {p["plugin_key"] for p in plugins}
        assert "print" in keys
        assert "tts" in keys

    async def test_plugin_has_config_schema(self, client: AsyncClient):
        res = await client.get("/api/v1/output-plugins")
        plugins = res.json()
        print_plugin = next(p for p in plugins if p["plugin_key"] == "print")
        assert "config_schema" in print_plugin
        assert "properties" in print_plugin["config_schema"]
        assert "template_name" in print_plugin["config_schema"]["properties"]

    async def test_plugin_has_formats(self, client: AsyncClient):
        res = await client.get("/api/v1/output-plugins")
        plugins = res.json()
        print_plugin = next(p for p in plugins if p["plugin_key"] == "print")
        assert "pdf" in print_plugin["supported_formats"]
        assert "docx" in print_plugin["supported_formats"]
        assert "odt" in print_plugin["supported_formats"]


class TestRenderJobEndpoints:
    async def test_start_render_unknown_session(self, client: AsyncClient):
        res = await client.post(
            "/api/v1/sessions/nonexistent/render",
            json={"plugin_key": "print", "config": {}},
        )
        # Should fail because no artifact exists for "nonexistent"
        assert res.status_code in (400, 422)

    async def test_start_render_unknown_plugin(self, client: AsyncClient):
        res = await client.post(
            "/api/v1/sessions/test/render",
            json={"plugin_key": "nonexistent", "config": {}},
        )
        assert res.status_code == 400

    async def test_get_nonexistent_job(self, client: AsyncClient):
        res = await client.get("/api/v1/render-jobs/nonexistent")
        assert res.status_code == 404

    async def test_delete_nonexistent_job(self, client: AsyncClient):
        res = await client.delete("/api/v1/render-jobs/nonexistent")
        assert res.status_code == 404


class TestSessionSearchEndpoint:
    async def test_search_empty(self, client: AsyncClient, default_project):
        res = await client.get(
            "/api/v1/render-sessions?q=test",
            headers={"X-Project-Id": default_project},
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestOptimizationProposalsEndpoints:
    async def test_list_proposals_empty(self, client: AsyncClient):
        res = await client.get("/api/v1/optimization-proposals")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    async def test_get_nonexistent_proposal(self, client: AsyncClient):
        res = await client.get("/api/v1/optimization-proposals/nonexistent")
        assert res.status_code == 404

    async def test_approve_nonexistent_proposal(self, client: AsyncClient):
        res = await client.post("/api/v1/optimization-proposals/nonexistent/approve")
        assert res.status_code == 404

    async def test_reject_nonexistent_proposal(self, client: AsyncClient):
        res = await client.post("/api/v1/optimization-proposals/nonexistent/reject")
        assert res.status_code == 404

    async def test_reflect_nonexistent_workflow(self, client: AsyncClient):
        res = await client.post("/api/v1/workflows/nonexistent/reflect")
        assert res.status_code == 404
