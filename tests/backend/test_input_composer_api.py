"""Tests for Input Composer API endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure plugins are registered before app creation
import backend.services.input.plugins  # noqa: F401
from backend.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestInputPluginsEndpoint:
    async def test_list_plugins(self, client: AsyncClient):
        res = await client.get("/api/v1/input-plugins")
        assert res.status_code == 200
        plugins = res.json()
        assert isinstance(plugins, list)
        keys = {p["plugin_key"] for p in plugins}
        assert "standard_text" in keys
        assert "stt" in keys
        assert "a2a_inbound" in keys
        assert "mcp" in keys

    async def test_mcp_is_not_available(self, client: AsyncClient):
        res = await client.get("/api/v1/input-plugins")
        plugins = res.json()
        mcp = next(p for p in plugins if p["plugin_key"] == "mcp")
        assert mcp["ui_hints"]["is_available"] is False
        assert mcp["ui_hints"]["coming_soon"] is True

    async def test_plugin_has_config_schema(self, client: AsyncClient):
        res = await client.get("/api/v1/input-plugins")
        plugins = res.json()
        std = next(p for p in plugins if p["plugin_key"] == "standard_text")
        assert "config_schema" in std
        assert "properties" in std["config_schema"]


class TestSubmitInputEndpoint:
    async def test_submit_standard_text(self, client: AsyncClient):
        res = await client.post(
            "/api/v1/input/submit",
            json={
                "plugin_key": "standard_text",
                "topic": "Should AI be regulated?",
            },
        )
        assert res.status_code == 202
        data = res.json()
        assert data["plugin_key"] == "standard_text"
        assert data["status"] == "completed"

    async def test_submit_stt(self, client: AsyncClient):
        res = await client.post(
            "/api/v1/input/submit",
            json={
                "plugin_key": "stt",
                "config": {"llm_profile_id": "whisper-1"},
            },
        )
        assert res.status_code == 202
        data = res.json()
        assert data["status"] == "processing"

    async def test_submit_unknown_plugin(self, client: AsyncClient):
        res = await client.post(
            "/api/v1/input/submit",
            json={"plugin_key": "nonexistent", "topic": "test"},
        )
        assert res.status_code == 400


class TestInputJobEndpoints:
    async def test_get_nonexistent_job(self, client: AsyncClient):
        res = await client.get("/api/v1/input/jobs/nonexistent")
        assert res.status_code == 404

    async def test_delete_nonexistent_job(self, client: AsyncClient):
        res = await client.delete("/api/v1/input/jobs/nonexistent")
        assert res.status_code == 404

    async def test_submit_and_get_job(self, client: AsyncClient):
        # Submit a job
        res = await client.post(
            "/api/v1/input/submit",
            json={"plugin_key": "standard_text", "topic": "Test"},
        )
        job_id = res.json()["job_id"]

        # Get job status
        res = await client.get(f"/api/v1/input/jobs/{job_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["processed_input"]["topic"] == "Test"


class TestMCPEndpoint:
    async def test_mcp_not_implemented(self, client: AsyncClient):
        res = await client.post("/api/v1/mcp/tools/call")
        assert res.status_code == 501


class TestA2AApprovalEndpoints:
    async def test_approve_nonexistent(self, client: AsyncClient):
        res = await client.post("/api/v1/input/a2a/nonexistent/approve")
        assert res.status_code == 404

    async def test_reject_nonexistent(self, client: AsyncClient):
        res = await client.post("/api/v1/input/a2a/nonexistent/reject")
        assert res.status_code == 404

    async def test_submit_a2a_and_approve(self, client: AsyncClient):
        # Submit A2A with approval required
        res = await client.post(
            "/api/v1/input/submit",
            json={
                "plugin_key": "a2a_inbound",
                "config": {"require_approval": True},
                "topic": "From external agent",
            },
        )
        assert res.status_code == 202
        data = res.json()
        job_id = data["job_id"]
        assert data["status"] == "pending_approval"

        # Approve
        res = await client.post(f"/api/v1/input/a2a/{job_id}/approve")
        assert res.status_code == 200
        assert res.json()["status"] == "processing"

    async def test_submit_a2a_and_reject(self, client: AsyncClient):
        # Submit A2A with approval required
        res = await client.post(
            "/api/v1/input/submit",
            json={
                "plugin_key": "a2a_inbound",
                "config": {"require_approval": True},
                "topic": "From external agent",
            },
        )
        job_id = res.json()["job_id"]

        # Reject
        res = await client.post(f"/api/v1/input/a2a/{job_id}/reject")
        assert res.status_code == 200
        assert res.json()["status"] == "failed"
