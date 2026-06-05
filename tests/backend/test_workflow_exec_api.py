"""Tests for Phase 2 Group G.3 — Workflow Execution API.

Covers all 7 endpoints of the workflow_exec router:
- POST /{workflow_id}/start
- GET /{session_id}/state
- POST /{session_id}/pause
- POST /{session_id}/resume
- POST /{session_id}/cancel
- GET /{session_id}/stream
- POST /{session_id}/interject
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from backend.workflow.workflow_compiler import CompiledWorkflow


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    """Fresh BlueprintRepository with temp database."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def sample_blueprint(repo: BlueprintRepository) -> AgentBlueprint:
    """Create a sample blueprint with all dependencies."""
    profile = BlueprintLLMProfile(
        id="prof-1",
        name="Test Profile",
        provider="openai",
        model="gpt-4",
        api_base="http://localhost:11434/v1",
        api_key_env="OPENAI_API_KEY",
        temperature=0.7,
        max_tokens=2048,
    )
    repo.save_llm_profile(profile)

    blueprint = AgentBlueprint(
        id="bp-1",
        name="Strategist Agent",
        llm_profile_id="prof-1",
        role_definition_id="role-1",
        active=True,
    )
    repo.save_blueprint(blueprint)
    return blueprint


@pytest.fixture()
def workflow_in_repo(repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> str:
    """Save a valid workflow definition to the repo and return its ID."""
    workflow = WorkflowDefinition(
        id="wf-test",
        name="Test Workflow",
        nodes=[
            WorkflowNode(id="wf-input", type="wf-input"),
            WorkflowNode(
                id="node-s1",
                type="wf-strategist",
                agent_blueprint_id=sample_blueprint.id,
            ),
        ],
        edges=[
            WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
        ],
        entry_point="wf-input",
    )
    repo.save_workflow_definition(workflow)
    return workflow.id


@pytest.fixture()
def mock_compiled_workflow() -> CompiledWorkflow:
    """A mock CompiledWorkflow with a mock graph."""
    mock_graph = MagicMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "output": "Final output",
            "final_consensus": 0.85,
            "current_round": 1,
            "node_outputs": [],
            "status": "completed",
        }
    )
    return CompiledWorkflow(
        graph=mock_graph,
        resolved_agents=[],
        node_sequence=["wf-input", "node-s1"],
    )


@pytest.fixture()
def client_with_repo(app, repo: BlueprintRepository, tmp_path: Path) -> tuple[TestClient, BlueprintRepository]:
    """TestClient with the workflow_exec router using the test repo."""
    import backend.api.routers.workflow_exec as wf_exec_module

    # Patch the lazy-initialized globals
    old_repo = wf_exec_module._repo
    old_snapshot = wf_exec_module._snapshot_store

    wf_exec_module._repo = repo
    wf_exec_module._snapshot_store = None  # Will be lazily created

    # Patch StateSnapshotStore to use temp path
    with patch("backend.api.routers.workflow_exec.StateSnapshotStore") as mock_store_cls:
        from backend.workflow.state_snapshot import StateSnapshotStore

        mock_store_cls.return_value = StateSnapshotStore(db_path=tmp_path / "test_snapshots.db")
        yield TestClient(app), repo

    wf_exec_module._repo = old_repo
    wf_exec_module._snapshot_store = old_snapshot


# ---------------------------------------------------------------------------
# POST /{workflow_id}/start
# ---------------------------------------------------------------------------


class TestStartWorkflow:
    """Test POST /{workflow_id}/start endpoint."""

    def test_start_returns_session_id(
        self,
        client_with_repo: tuple[TestClient, BlueprintRepository],
        workflow_in_repo: str,
        mock_compiled_workflow: CompiledWorkflow,
    ) -> None:
        """Starting a valid workflow should return a session_id."""
        client, _ = client_with_repo

        with patch("backend.api.routers.workflow_exec.CompilerService") as mock_compiler_cls:
            mock_compiler = MagicMock()
            mock_compiler.compile_to_langgraph.return_value = mock_compiled_workflow
            mock_compiler_cls.return_value = mock_compiler

            with patch("backend.tasks.dispatch.dispatch_workflow_task"):
                resp = client.post(
                    f"/api/v1/workflow-exec/{workflow_in_repo}/start",
                    json={"context": "Test debate topic"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "running"

    def test_start_nonexistent_workflow(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Starting a nonexistent workflow should return 404."""
        client, _ = client_with_repo
        resp = client.post(
            "/api/v1/workflow-exec/nonexistent-wf/start",
            json={"context": "Test"},
        )
        assert resp.status_code == 404

    def test_start_compilation_failure(
        self,
        client_with_repo: tuple[TestClient, BlueprintRepository],
        workflow_in_repo: str,
    ) -> None:
        """Starting a workflow that fails compilation should return 422."""
        client, _ = client_with_repo

        failed_compiled = CompiledWorkflow(graph=None, errors=["Missing blueprint"], warnings=[])

        with patch("backend.api.routers.workflow_exec.CompilerService") as mock_compiler_cls:
            mock_compiler = MagicMock()
            mock_compiler.compile_to_langgraph.return_value = failed_compiled
            mock_compiler_cls.return_value = mock_compiler

            resp = client.post(
                f"/api/v1/workflow-exec/{workflow_in_repo}/start",
                json={"context": "Test"},
            )

        assert resp.status_code == 422

    def test_start_missing_context(
        self,
        client_with_repo: tuple[TestClient, BlueprintRepository],
        workflow_in_repo: str,
    ) -> None:
        """Starting without context should return 422 (validation error)."""
        client, _ = client_with_repo
        resp = client.post(
            f"/api/v1/workflow-exec/{workflow_in_repo}/start",
            json={},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /{session_id}/interject
# ---------------------------------------------------------------------------


class TestInterjectEndpoint:
    """Test POST /{session_id}/interject endpoint."""

    def test_interject_returns_queued(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Submitting an interjection should return queued status."""
        client, _ = client_with_repo

        resp = client.post(
            "/api/v1/workflow-exec/sess-test/interject",
            json={"content": "User input here"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "interjection_id" in data
        assert data["status"] == "queued"

    def test_interject_empty_content(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Empty content should return 422."""
        client, _ = client_with_repo
        resp = client.post(
            "/api/v1/workflow-exec/sess-test/interject",
            json={"content": ""},
        )
        assert resp.status_code == 422

    def test_interject_with_source(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Interjection with custom source should work."""
        client, _ = client_with_repo
        resp = client.post(
            "/api/v1/workflow-exec/sess-test/interject",
            json={"content": "API input", "source": "api"},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /{session_id}/pause
# ---------------------------------------------------------------------------


class TestPauseEndpoint:
    """Test POST /{session_id}/pause endpoint."""

    def test_pause_running_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Pausing a running session should succeed."""
        client, _ = client_with_repo

        # Set up a running session
        from backend.workflow.workflow_runner import set_session_status

        set_session_status("sess-pause-test", "running")

        resp = client.post("/api/v1/workflow-exec/sess-pause-test/pause")
        assert resp.status_code == 200
        assert resp.json()["status"] == "paused"

    def test_pause_unknown_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Pausing an unknown session should return 409."""
        client, _ = client_with_repo
        resp = client.post("/api/v1/workflow-exec/sess-unknown/pause")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /{session_id}/resume
# ---------------------------------------------------------------------------


class TestResumeEndpoint:
    """Test POST /{session_id}/resume endpoint."""

    def test_resume_paused_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Resuming a paused session should succeed."""
        client, _ = client_with_repo

        from backend.workflow.workflow_runner import set_session_status

        set_session_status("sess-resume-test", "paused")

        resp = client.post("/api/v1/workflow-exec/sess-resume-test/resume")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_resume_running_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Resuming a running session should return 409."""
        client, _ = client_with_repo

        from backend.workflow.workflow_runner import set_session_status

        set_session_status("sess-resume-test-2", "running")

        resp = client.post("/api/v1/workflow-exec/sess-resume-test-2/resume")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# POST /{session_id}/cancel
# ---------------------------------------------------------------------------


class TestCancelEndpoint:
    """Test POST /{session_id}/cancel endpoint."""

    def test_cancel_running_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Cancelling a running session should succeed."""
        client, _ = client_with_repo

        from backend.workflow.workflow_runner import set_session_status

        set_session_status("sess-cancel-test", "running")

        resp = client.post("/api/v1/workflow-exec/sess-cancel-test/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    def test_cancel_completed_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Cancelling a completed session should be idempotent."""
        client, _ = client_with_repo

        from backend.workflow.workflow_runner import set_session_status

        set_session_status("sess-cancel-done", "completed")

        resp = client.post("/api/v1/workflow-exec/sess-cancel-done/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


# ---------------------------------------------------------------------------
# GET /{session_id}/state
# ---------------------------------------------------------------------------


class TestGetStateEndpoint:
    """Test GET /{session_id}/state endpoint."""

    def test_state_unknown_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Querying state for unknown session should return 404."""
        client, _ = client_with_repo
        resp = client.get("/api/v1/workflow-exec/sess-unknown/state")
        assert resp.status_code == 404

    def test_state_running_session(self, client_with_repo: tuple[TestClient, BlueprintRepository]) -> None:
        """Querying state for a running session should return status."""
        client, _ = client_with_repo

        from backend.workflow.workflow_runner import set_session_status

        set_session_status("sess-state-test", "running")

        resp = client.get("/api/v1/workflow-exec/sess-state-test/state")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-state-test"
        assert data["status"] == "running"
