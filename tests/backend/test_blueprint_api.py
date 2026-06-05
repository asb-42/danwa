"""Tests for the Blueprint Canvas API.

Covers all CRUD endpoints for LLM Profiles, Agent Blueprints,
Canvas Layouts, Workflow Definitions, and centralized error handling.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import (
    get_audit_service,
    get_blueprint_repository,
    get_debate_store,
    get_project_id,
    get_project_store,
    get_settings,
)
from backend.blueprints.models import RoleDefinition, RoleType
from backend.blueprints.repository import BlueprintRepository
from backend.core.config import Settings
from backend.main import create_app
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore


def _db_only(items: list) -> list:
    """Filter out module-sourced items (those with _source_module key)."""
    return [item for item in items if not item.get("_source_module")]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def blueprint_repo(tmp_path) -> BlueprintRepository:
    """Isolated BlueprintRepository with temp database."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def settings(tmp_path) -> Settings:
    """Test settings with temporary database path."""
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
    return ProjectStore(base_dir=tmp_path / "test_projects")


@pytest.fixture()
def default_project(project_store):
    project = project_store.get_or_create_default()
    return project.id


@pytest.fixture()
def app(settings, audit_service, debate_store, project_store, default_project, blueprint_repo):
    """FastAPI app with all dependency overrides including blueprint repo."""
    get_project_store.cache_clear()
    get_blueprint_repository.cache_clear()
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    application.dependency_overrides[get_project_id] = lambda: default_project
    application.dependency_overrides[get_blueprint_repository] = lambda: blueprint_repo
    yield application
    get_blueprint_repository.cache_clear()


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Sample data factories
# ---------------------------------------------------------------------------


def _sample_llm_profile(profile_id: str = "test-llm") -> dict:
    return {
        "id": profile_id,
        "name": "Test LLM",
        "provider": "openrouter",
        "model": "test/model-v1",
        "max_tokens": 2048,
        "temperature": 0.5,
    }


def _sample_blueprint(
    blueprint_id: str = "test-bp",
    llm_profile_id: str = "test-llm",
    role_definition_id: str = "test-role",
) -> dict:
    return {
        "id": blueprint_id,
        "name": "Test Blueprint",
        "description": "A test agent blueprint",
        "llm_profile_id": llm_profile_id,
        "role_definition_id": role_definition_id,
    }


def _sample_layout(layout_id: str = "test-layout") -> dict:
    return {
        "id": layout_id,
        "name": "Test Layout",
        "description": "A test canvas layout",
        "layout_data": {
            "nodes": [
                {"id": "n1", "type": "agent-blueprint", "x": 100, "y": 200},
            ],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


def _seed_prerequisites(client: TestClient) -> None:
    """Create the LLM profile required by blueprint references."""
    client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile("test-llm"))


# ===================================================================
# LLM Profile CRUD
# ===================================================================


class TestLLMProfileAPI:
    """Tests for /api/v1/blueprints/llm-profiles endpoints."""

    def test_list_empty(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/llm-profiles")
        assert response.status_code == 200
        # Module fallback data may be present; assert no DB items
        data = response.json()
        db_items = [item for item in data if not item.get("_source_module")]
        assert db_items == []

    def test_create(self, client: TestClient) -> None:
        payload = _sample_llm_profile()
        response = client.post("/api/v1/blueprints/llm-profiles", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "test-llm"
        assert data["name"] == "Test LLM"
        assert data["provider"] == "openrouter"

    def test_get_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        response = client.get("/api/v1/blueprints/llm-profiles/test-llm")
        assert response.status_code == 200
        assert response.json()["id"] == "test-llm"

    def test_list_after_create(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile("p1"))
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile("p2"))
        response = client.get("/api/v1/blueprints/llm-profiles")
        assert response.status_code == 200
        assert len(_db_only(response.json())) == 2

    def test_update(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        updated = _sample_llm_profile()
        updated["name"] = "Updated LLM"
        response = client.put("/api/v1/blueprints/llm-profiles/test-llm", json=updated)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated LLM"

    def test_delete(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        response = client.delete("/api/v1/blueprints/llm-profiles/test-llm")
        assert response.status_code == 200
        assert response.json()["deleted"] == "test-llm"
        # Verify gone
        response = client.get("/api/v1/blueprints/llm-profiles/test-llm")
        assert response.status_code == 404

    def test_get_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/llm-profiles/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_conflict(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        response = client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_update_not_found(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/blueprints/llm-profiles/nonexistent",
            json=_sample_llm_profile("nonexistent"),
        )
        assert response.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        response = client.delete("/api/v1/blueprints/llm-profiles/nonexistent")
        assert response.status_code == 404

    def test_pagination(self, client: TestClient) -> None:
        for i in range(5):
            client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile(f"p{i}"))
        response = client.get("/api/v1/blueprints/llm-profiles?limit=2&offset=0")
        assert response.status_code == 200
        assert len(_db_only(response.json())) == 2
        response = client.get("/api/v1/blueprints/llm-profiles?limit=2&offset=4")
        assert response.status_code == 200
        assert len(_db_only(response.json())) == 1


# ===================================================================
# Agent Blueprint CRUD (prompt-template/role-definition endpoints removed)
# ===================================================================
# ===================================================================
# Agent Blueprint CRUD
# ===================================================================


class TestAgentBlueprintAPI:
    """Tests for /api/v1/blueprints/agent-blueprints endpoints."""

    def test_list_empty(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        response = client.get("/api/v1/blueprints/agent-blueprints")
        assert response.status_code == 200
        assert response.json() == []

    def test_create(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        payload = _sample_blueprint()
        response = client.post("/api/v1/blueprints/agent-blueprints", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "test-bp"
        assert data["llm_profile_id"] == "test-llm"
        assert data["is_active"] is True

    def test_get_by_id(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        client.post("/api/v1/blueprints/agent-blueprints", json=_sample_blueprint())
        response = client.get("/api/v1/blueprints/agent-blueprints/test-bp")
        assert response.status_code == 200
        assert response.json()["id"] == "test-bp"

    def test_update(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        client.post("/api/v1/blueprints/agent-blueprints", json=_sample_blueprint())
        updated = _sample_blueprint()
        updated["name"] = "Updated Blueprint"
        response = client.put("/api/v1/blueprints/agent-blueprints/test-bp", json=updated)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Blueprint"

    def test_delete(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        client.post("/api/v1/blueprints/agent-blueprints", json=_sample_blueprint())
        response = client.delete("/api/v1/blueprints/agent-blueprints/test-bp")
        assert response.status_code == 200
        response = client.get("/api/v1/blueprints/agent-blueprints/test-bp")
        assert response.status_code == 404

    def test_list_active_only(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        active_bp = _sample_blueprint("bp-active")
        client.post("/api/v1/blueprints/agent-blueprints", json=active_bp)
        inactive_bp = _sample_blueprint("bp-inactive")
        inactive_bp["is_active"] = False
        client.post("/api/v1/blueprints/agent-blueprints", json=inactive_bp)

        # Default: active_only=True
        response = client.get("/api/v1/blueprints/agent-blueprints")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Include inactive
        response = client.get("/api/v1/blueprints/agent-blueprints?active_only=false")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_create_conflict(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        client.post("/api/v1/blueprints/agent-blueprints", json=_sample_blueprint())
        response = client.post("/api/v1/blueprints/agent-blueprints", json=_sample_blueprint())
        assert response.status_code == 409

    def test_get_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/agent-blueprints/nonexistent")
        assert response.status_code == 404

    def test_pagination(self, client: TestClient) -> None:
        _seed_prerequisites(client)
        for i in range(5):
            client.post(
                "/api/v1/blueprints/agent-blueprints",
                json=_sample_blueprint(f"bp{i}"),
            )
        response = client.get("/api/v1/blueprints/agent-blueprints?limit=3&offset=0")
        assert response.status_code == 200
        assert len(response.json()) == 3


# ===================================================================
# Canvas Layout CRUD
# ===================================================================


class TestCanvasLayoutAPI:
    """Tests for /api/v1/canvas/layouts endpoints."""

    def test_list_empty(self, client: TestClient) -> None:
        response = client.get("/api/v1/canvas/layouts")
        assert response.status_code == 200
        assert response.json() == []

    def test_create(self, client: TestClient) -> None:
        payload = _sample_layout()
        response = client.post("/api/v1/canvas/layouts", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "test-layout"
        assert data["name"] == "Test Layout"
        assert len(data["layout_data"]["nodes"]) == 1

    def test_get_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/canvas/layouts", json=_sample_layout())
        response = client.get("/api/v1/canvas/layouts/test-layout")
        assert response.status_code == 200
        assert response.json()["id"] == "test-layout"

    def test_update(self, client: TestClient) -> None:
        client.post("/api/v1/canvas/layouts", json=_sample_layout())
        updated = _sample_layout()
        updated["name"] = "Updated Layout"
        updated["layout_data"]["nodes"].append({"id": "n2", "type": "llm-profile", "x": 300, "y": 400})
        response = client.put("/api/v1/canvas/layouts/test-layout", json=updated)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Layout"
        assert len(response.json()["layout_data"]["nodes"]) == 2

    def test_delete(self, client: TestClient) -> None:
        client.post("/api/v1/canvas/layouts", json=_sample_layout())
        response = client.delete("/api/v1/canvas/layouts/test-layout")
        assert response.status_code == 200
        response = client.get("/api/v1/canvas/layouts/test-layout")
        assert response.status_code == 404

    def test_filter_by_project(self, client: TestClient) -> None:
        layout_p1 = _sample_layout("l1")
        layout_p1["project_id"] = "proj-1"
        client.post("/api/v1/canvas/layouts", json=layout_p1)
        layout_p2 = _sample_layout("l2")
        layout_p2["project_id"] = "proj-2"
        client.post("/api/v1/canvas/layouts", json=layout_p2)

        response = client.get("/api/v1/canvas/layouts?project_id=proj-1")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj-1"

    def test_roundtrip_with_blueprint_refs(self, client: TestClient) -> None:
        """Create a layout referencing blueprint IDs and verify roundtrip."""
        # Create prerequisite entities and a blueprint
        _seed_prerequisites(client)
        client.post("/api/v1/blueprints/agent-blueprints", json=_sample_blueprint())

        layout = _sample_layout("roundtrip-layout")
        layout["layout_data"]["nodes"] = [
            {
                "id": "bp-node",
                "type": "agent-blueprint",
                "x": 100,
                "y": 200,
                "blueprint_id": "test-bp",
            },
        ]
        layout["layout_data"]["edges"] = [
            {"id": "e1", "source": "bp-node", "target": "bp-node", "type": "uses_llm"},
        ]
        client.post("/api/v1/canvas/layouts", json=layout)

        response = client.get("/api/v1/canvas/layouts/roundtrip-layout")
        assert response.status_code == 200
        data = response.json()
        assert data["layout_data"]["nodes"][0]["blueprint_id"] == "test-bp"
        assert data["layout_data"]["edges"][0]["type"] == "uses_llm"

    def test_create_conflict(self, client: TestClient) -> None:
        client.post("/api/v1/canvas/layouts", json=_sample_layout())
        response = client.post("/api/v1/canvas/layouts", json=_sample_layout())
        assert response.status_code == 409

    def test_get_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/canvas/layouts/nonexistent")
        assert response.status_code == 404

    def test_pagination(self, client: TestClient) -> None:
        for i in range(5):
            client.post("/api/v1/canvas/layouts", json=_sample_layout(f"l{i}"))
        response = client.get("/api/v1/canvas/layouts?limit=2&offset=0")
        assert response.status_code == 200
        assert len(response.json()) == 2


# ===================================================================
# Error Handling
# ===================================================================


class TestErrorHandling:
    """Tests for centralized error handlers (404, 409, 422)."""

    def test_not_found_has_detail(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/llm-profiles/does-not-exist")
        assert response.status_code == 404
        body = response.json()
        assert "detail" in body
        assert "not found" in body["detail"].lower()

    def test_conflict_has_detail(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        response = client.post("/api/v1/blueprints/llm-profiles", json=_sample_llm_profile())
        assert response.status_code == 409
        body = response.json()
        assert "detail" in body
        assert "already exists" in body["detail"].lower()

    def test_validation_error_temperature(self, client: TestClient) -> None:
        """Invalid temperature should trigger 422 from Pydantic."""
        payload = _sample_llm_profile()
        payload["temperature"] = 5.0  # out of range [0, 2]
        response = client.post("/api/v1/blueprints/llm-profiles", json=payload)
        assert response.status_code == 422

    def test_validation_error_invalid_id_pattern(self, client: TestClient) -> None:
        """ID with uppercase should trigger 422."""
        payload = _sample_llm_profile()
        payload["id"] = "Invalid-ID!"
        response = client.post("/api/v1/blueprints/llm-profiles", json=payload)
        assert response.status_code == 422

    def test_canvas_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/canvas/layouts/does-not-exist")
        assert response.status_code == 404

    def test_canvas_conflict(self, client: TestClient) -> None:
        client.post("/api/v1/canvas/layouts", json=_sample_layout())
        response = client.post("/api/v1/canvas/layouts", json=_sample_layout())
        assert response.status_code == 409


# ===================================================================
# Workflow Definition CRUD
# ===================================================================


def _sample_workflow(wf_id: str = "test-wf") -> dict:
    return {
        "id": wf_id,
        "name": "Test Workflow",
        "description": "A test workflow definition",
        "execution_order": ["node-1", "node-2"],
        "conditional_edges": [
            {
                "source_node_id": "node-1",
                "target_node_id": "node-2",
                "condition": "consensus_reached",
                "description": "Branch if consensus",
            }
        ],
        "interjection_points": [
            {
                "node_id": "node-1",
                "input_type": "user_query",
                "blocking": True,
                "description": "Wait for user input",
            }
        ],
        "node_blueprint_map": {
            "node-1": "bp-strategist",
            "node-2": "bp-critic",
        },
        "tags": ["test", "phase4"],
        "is_active": True,
    }


class TestWorkflowDefinitionAPI:
    """Tests for /api/v1/blueprints/workflows endpoints."""

    def test_list_empty(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/workflows")
        assert response.status_code == 200
        assert response.json() == []

    def test_create(self, client: TestClient) -> None:
        payload = _sample_workflow()
        response = client.post("/api/v1/blueprints/workflows", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "test-wf"
        assert data["name"] == "Test Workflow"
        assert len(data["execution_order"]) == 2
        assert len(data["conditional_edges"]) == 1
        assert len(data["interjection_points"]) == 1
        assert data["node_blueprint_map"]["node-1"] == "bp-strategist"

    def test_get_by_id(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/workflows", json=_sample_workflow())
        response = client.get("/api/v1/blueprints/workflows/test-wf")
        assert response.status_code == 200
        assert response.json()["id"] == "test-wf"

    def test_list_after_create(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/workflows", json=_sample_workflow())
        response = client.get("/api/v1/blueprints/workflows")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_update(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/workflows", json=_sample_workflow())
        updated = _sample_workflow()
        updated["name"] = "Updated Workflow"
        updated["execution_order"] = ["node-2", "node-1"]
        response = client.put("/api/v1/blueprints/workflows/test-wf", json=updated)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Workflow"
        assert response.json()["execution_order"] == ["node-2", "node-1"]

    def test_delete(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/workflows", json=_sample_workflow())
        response = client.delete("/api/v1/blueprints/workflows/test-wf")
        assert response.status_code == 200
        assert response.json()["deleted"] == "test-wf"
        # Verify gone
        response = client.get("/api/v1/blueprints/workflows/test-wf")
        assert response.status_code == 404

    def test_get_not_found(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/workflows/nonexistent")
        assert response.status_code == 404

    def test_create_conflict(self, client: TestClient) -> None:
        client.post("/api/v1/blueprints/workflows", json=_sample_workflow())
        response = client.post("/api/v1/blueprints/workflows", json=_sample_workflow())
        assert response.status_code == 409

    def test_update_not_found(self, client: TestClient) -> None:
        response = client.put(
            "/api/v1/blueprints/workflows/nonexistent",
            json=_sample_workflow("nonexistent"),
        )
        assert response.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        response = client.delete("/api/v1/blueprints/workflows/nonexistent")
        assert response.status_code == 404

    def test_pagination(self, client: TestClient) -> None:
        for i in range(3):
            wf = _sample_workflow(f"wf-{i}")
            wf["name"] = f"Workflow {i}"
            client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.get("/api/v1/blueprints/workflows?limit=2&offset=0")
        assert response.status_code == 200
        assert len(response.json()) == 2
        response = client.get("/api/v1/blueprints/workflows?limit=2&offset=2")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_minimal_workflow(self, client: TestClient) -> None:
        """A workflow with only required fields should be valid."""
        payload = {"id": "minimal-wf", "name": "Minimal"}
        response = client.post("/api/v1/blueprints/workflows", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["execution_order"] == []
        assert data["conditional_edges"] == []
        assert data["interjection_points"] == []
        assert data["node_blueprint_map"] == {}

    def test_empty_name_rejected(self, client: TestClient) -> None:
        """Workflow name must be at least 1 character."""
        payload = {"id": "bad-wf", "name": ""}
        response = client.post("/api/v1/blueprints/workflows", json=payload)
        assert response.status_code == 422

    def test_duplicate_execution_order_rejected(self, client: TestClient) -> None:
        """execution_order must not contain duplicate node IDs."""
        payload = _sample_workflow()
        payload["execution_order"] = ["node-1", "node-1"]
        response = client.post("/api/v1/blueprints/workflows", json=payload)
        assert response.status_code == 422


# ===================================================================
# Compiler Service
# ===================================================================


# Mock module lookups for compiler tests (no DB-backed role_definitions table).
_ROLE_DEFINITIONS: dict[str, RoleDefinition] = {
    "bp-role": RoleDefinition(
        id="bp-role",
        name="Test Role",
        role_type_id="strategist",
    ),
}

_ROLE_TYPES: dict[str, RoleType] = {
    "strategist": RoleType(id="strategist", name="Strategist"),
}


def _mock_resolve_role_definition(role_def_id: str):
    return _ROLE_DEFINITIONS.get(role_def_id)


def _mock_resolve_role_type(role_type_id: str):
    return _ROLE_TYPES.get(role_type_id)


@pytest.fixture(autouse=True)
def _patch_compiler_module_lookups(request):
    """Auto-patch module lookups for compiler tests only."""
    if request.node.get_closest_marker("compiler") is not None or (hasattr(request, "cls") and request.cls is TestCompilerAPI):
        with (
            patch(
                "backend.workflow.workflow_compiler.resolve_role_definition",
                side_effect=_mock_resolve_role_definition,
            ),
            patch(
                "backend.workflow.workflow_compiler.resolve_role_type",
                side_effect=_mock_resolve_role_type,
            ),
            patch(
                "backend.blueprints.compiler.resolve_role_definition",
                side_effect=_mock_resolve_role_definition,
            ),
            patch(
                "backend.blueprints.compiler.resolve_role_type",
                side_effect=_mock_resolve_role_type,
            ),
            patch(
                "backend.blueprints.module_lookups.resolve_role_definition",
                side_effect=_mock_resolve_role_definition,
            ),
            patch(
                "backend.blueprints.module_lookups.resolve_role_type",
                side_effect=_mock_resolve_role_type,
            ),
        ):
            yield
    else:
        yield


class TestCompilerAPI:
    """Tests for POST /api/v1/blueprints/workflows/{id}/compile."""

    def _seed_full_catalog(self, client: TestClient) -> None:
        """Create LLM profile and blueprint for compiler tests."""
        client.post(
            "/api/v1/blueprints/llm-profiles",
            json=_sample_llm_profile("bp-llm"),
        )
        client.post(
            "/api/v1/blueprints/agent-blueprints",
            json=_sample_blueprint("bp-strategist", "bp-llm", "bp-role"),
        )

    def test_compile_not_found(self, client: TestClient) -> None:
        response = client.post("/api/v1/blueprints/workflows/nonexistent/compile")
        assert response.status_code == 404

    def test_compile_valid_workflow(self, client: TestClient) -> None:
        self._seed_full_catalog(client)
        wf = _sample_workflow()
        wf["node_blueprint_map"] = {"node-1": "bp-strategist"}
        wf["execution_order"] = ["node-1"]
        wf["conditional_edges"] = []
        wf["interjection_points"] = []
        client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.post("/api/v1/blueprints/workflows/test-wf/compile")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert len(data["resolved_agents"]) == 1
        assert data["resolved_agents"][0]["blueprint_id"] == "bp-strategist"
        assert data["resolved_agents"][0]["role"] == "strategist"
        assert data["errors"] == []

    def test_compile_missing_blueprint(self, client: TestClient) -> None:
        """Referencing a non-existent blueprint should produce an error."""
        wf = _sample_workflow()
        wf["node_blueprint_map"] = {"node-1": "nonexistent-bp"}
        wf["execution_order"] = ["node-1"]
        wf["conditional_edges"] = []
        wf["interjection_points"] = []
        client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.post("/api/v1/blueprints/workflows/test-wf/compile")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert any("not found in catalog" in e for e in data["errors"])

    def test_compile_invalid_execution_order_node(self, client: TestClient) -> None:
        """execution_order referencing unknown node should produce an error."""
        self._seed_full_catalog(client)
        wf = _sample_workflow()
        wf["node_blueprint_map"] = {"node-1": "bp-strategist"}
        wf["execution_order"] = ["node-1", "ghost-node"]
        wf["conditional_edges"] = []
        wf["interjection_points"] = []
        client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.post("/api/v1/blueprints/workflows/test-wf/compile")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert any("ghost-node" in e for e in data["errors"])

    def test_compile_invalid_conditional_edge_source(self, client: TestClient) -> None:
        """Conditional edge referencing unknown source should produce an error."""
        self._seed_full_catalog(client)
        wf = _sample_workflow()
        wf["node_blueprint_map"] = {"node-1": "bp-strategist"}
        wf["execution_order"] = ["node-1"]
        wf["conditional_edges"] = [
            {
                "source_node_id": "ghost",
                "target_node_id": "node-1",
                "condition": "always",
            }
        ]
        wf["interjection_points"] = []
        client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.post("/api/v1/blueprints/workflows/test-wf/compile")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert any("ghost" in e for e in data["errors"])

    def test_compile_invalid_interjection_point(self, client: TestClient) -> None:
        """Interjection point referencing unknown node should produce an error."""
        self._seed_full_catalog(client)
        wf = _sample_workflow()
        wf["node_blueprint_map"] = {"node-1": "bp-strategist"}
        wf["execution_order"] = ["node-1"]
        wf["conditional_edges"] = []
        wf["interjection_points"] = [{"node_id": "ghost", "input_type": "user_query", "blocking": True}]
        client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.post("/api/v1/blueprints/workflows/test-wf/compile")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is False
        assert any("ghost" in e for e in data["errors"])

    def test_compile_inactive_blueprint_warning(self, client: TestClient) -> None:
        """An inactive blueprint should produce a warning but not an error."""
        self._seed_full_catalog(client)
        # Deactivate the blueprint
        client.put(
            "/api/v1/blueprints/agent-blueprints/bp-strategist",
            json=_sample_blueprint("bp-strategist", "bp-llm", "bp-role") | {"is_active": False},
        )
        wf = _sample_workflow()
        wf["node_blueprint_map"] = {"node-1": "bp-strategist"}
        wf["execution_order"] = ["node-1"]
        wf["conditional_edges"] = []
        wf["interjection_points"] = []
        client.post("/api/v1/blueprints/workflows", json=wf)
        response = client.post("/api/v1/blueprints/workflows/test-wf/compile")
        assert response.status_code == 200
        data = response.json()
        assert data["is_valid"] is True
        assert any("inactive" in w for w in data["warnings"])


# ===================================================================
# Workflow Health
# ===================================================================


class TestWorkflowHealth:
    """Smoke tests to verify workflow routes are registered."""

    def test_workflows_prefix_accessible(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/workflows")
        assert response.status_code == 200


# ===================================================================
# Health (blueprint routes registered)
# ===================================================================


class TestBlueprintHealth:
    """Smoke tests to verify blueprint routes are registered."""

    def test_blueprints_prefix_accessible(self, client: TestClient) -> None:
        response = client.get("/api/v1/blueprints/llm-profiles")
        assert response.status_code == 200

    def test_canvas_prefix_accessible(self, client: TestClient) -> None:
        response = client.get("/api/v1/canvas/layouts")
        assert response.status_code == 200
