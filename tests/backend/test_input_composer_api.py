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
    async with AsyncClient(transport=transport, base_url="http://test", headers={"X-Project-Id": "_default"}) as c:
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

    async def test_list_jobs_returns_list(self, client: AsyncClient):
        """List jobs should return a list (may be empty or populated by other tests)."""
        res = await client.get("/api/v1/input/jobs")
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    async def test_list_jobs_with_filter(self, client: AsyncClient):
        """Submit a job and list it back with status filter."""
        # Submit a completed job
        res = await client.post(
            "/api/v1/input/submit",
            json={"plugin_key": "standard_text", "topic": "List test"},
        )
        assert res.status_code == 202
        job_id = res.json()["job_id"]

        # List completed jobs — should include our job
        res = await client.get("/api/v1/input/jobs?status=completed")
        assert res.status_code == 200
        jobs = res.json()
        assert len(jobs) >= 1
        assert any(j["job_id"] == job_id for j in jobs)

    async def test_list_jobs_invalid_status(self, client: AsyncClient):
        """Listing with invalid status should return 422."""
        res = await client.get("/api/v1/input/jobs?status=invalid_status")
        assert res.status_code == 422

    async def test_list_jobs_with_plugin_filter(self, client: AsyncClient):
        """List jobs filtered by plugin_key."""
        # Submit a standard_text job
        res = await client.post(
            "/api/v1/input/submit",
            json={"plugin_key": "standard_text", "topic": "Plugin filter test"},
        )
        assert res.status_code == 202
        job_id = res.json()["job_id"]

        # List with matching plugin_key — should include our job
        res = await client.get("/api/v1/input/jobs?plugin_key=standard_text")
        assert res.status_code == 200
        jobs = res.json()
        assert len(jobs) >= 1
        assert any(j["job_id"] == job_id for j in jobs)
        assert all(j["plugin_key"] == "standard_text" for j in jobs)


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


class TestLaunchWorkflowEndpoint:
    """Tests for POST /api/v1/input/launch."""

    async def test_launch_nonexistent_job(self, client: AsyncClient):
        """Launching a nonexistent job should return 404."""
        res = await client.post(
            "/api/v1/input/launch",
            json={"job_id": "nonexistent"},
        )
        assert res.status_code == 404

    async def test_launch_standard_text(self, client: AsyncClient):
        """Standard text input should complete immediately and launch a workflow."""
        from backend.blueprints.repository import BlueprintRepository
        from backend.blueprints.workflow_models import (
            WorkflowDefinition,
            WorkflowEdge,
            WorkflowNode,
        )

        # Create a minimal but valid workflow definition (needs connected
        # non-isolated nodes — the compiler rejects isolated nodes).
        repo = BlueprintRepository()
        wf = WorkflowDefinition(
            id="test-wf-launch",
            name="Test Launch Workflow",
            nodes=[
                WorkflowNode(id="input-1", type="wf-input", label="Input"),
                WorkflowNode(id="init-1", type="wf-initialize", label="Init"),
            ],
            edges=[
                WorkflowEdge(
                    id="e1",
                    source="input-1",
                    target="init-1",
                    type="sequential",
                ),
            ],
            entry_point="input-1",
        )
        repo.save_workflow_definition(wf)

        try:
            # Submit standard text input (completes immediately)
            res = await client.post(
                "/api/v1/input/submit",
                json={
                    "plugin_key": "standard_text",
                    "topic": "Is AI conscious?",
                },
            )
            assert res.status_code == 202
            job = res.json()
            assert job["status"] == "completed"

            # Launch workflow from the completed job
            res = await client.post(
                "/api/v1/input/launch",
                json={
                    "job_id": job["job_id"],
                    "workflow_id": "test-wf-launch",
                },
            )
            assert res.status_code == 200
            result = res.json()
            assert "session_id" in result
            assert result["status"] == "running"
            assert result["workflow_id"] == "test-wf-launch"
        finally:
            repo.delete_workflow_definition("test-wf-launch")

    async def test_launch_no_workflow(self, client: AsyncClient):
        """Launching without available workflows should return 422."""
        # Submit standard text input
        res = await client.post(
            "/api/v1/input/submit",
            json={
                "plugin_key": "standard_text",
                "topic": "Test",
            },
        )
        assert res.status_code == 202
        job = res.json()

        # Try to launch without specifying workflow_id
        # (may succeed if other tests created workflows, or fail with 422)
        res = await client.post(
            "/api/v1/input/launch",
            json={"job_id": job["job_id"]},
        )
        # Either 200 (auto-selected workflow) or 422 (no workflows)
        assert res.status_code in (200, 422)
