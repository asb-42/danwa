"""Tests for Workflow Templates — models, repository, API, and seed.

Covers:
- WorkflowTemplate Pydantic model validation
- TemplatePlaceholder model
- Repository CRUD for workflow templates
- Seed templates idempotency
- API CRUD endpoints
- Instantiation endpoint (happy path + validation errors)
- Save-as-template endpoint
- System template protection (403 on edit/delete)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_blueprint_repository
from backend.blueprints.models import AgentBlueprint, BlueprintLLMProfile
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    TemplatePlaceholder,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowTemplate,
)
from backend.main import create_app
from scripts.seed_templates import seed_system_templates

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo(tmp_path) -> BlueprintRepository:
    """Isolated BlueprintRepository with temp database."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def sample_template() -> WorkflowTemplate:
    """A minimal custom workflow template."""
    return WorkflowTemplate(
        id="tpl-test",
        name="Test Template",
        description="A test template",
        category="custom",
        tags=["test"],
        template_data={
            "nodes": [
                {"id": "input-1", "type": "wf-input", "label": "Input"},
                {
                    "id": "strategist-1",
                    "type": "wf-strategist",
                    "label": "Strategist",
                    "agent_blueprint_id": "{{strategist_id}}",
                },
            ],
            "edges": [
                {"id": "e1", "source": "input-1", "target": "strategist-1", "type": "sequential"},
            ],
            "entry_point": "input-1",
            "termination_conditions": [
                {"type": "max_rounds", "value": "{{max_rounds}}"},
            ],
        },
        placeholders=[
            TemplatePlaceholder(key="strategist_id", type="blueprint_ref", description="Strategist blueprint"),
            TemplatePlaceholder(key="max_rounds", type="integer", default=5, description="Max rounds"),
        ],
        is_system=False,
    )


@pytest.fixture()
def sample_blueprint(repo) -> AgentBlueprint:
    """Create and persist a sample AgentBlueprint for reference tests."""
    llm = BlueprintLLMProfile(
        id="llm-test",
        name="Test LLM",
        provider="openai",
        model="gpt-4",
    )
    repo.save_llm_profile(llm)

    bp = AgentBlueprint(
        id="bp-strategist",
        name="Strategist Blueprint",
        llm_profile_id="llm-test",
        role_definition_id="role-strategist",
    )
    repo.save_blueprint(bp)
    return bp


@pytest.fixture()
def app(repo):
    """FastAPI app with overridden repository."""
    application = create_app()
    application.dependency_overrides[get_blueprint_repository] = lambda: repo
    return application


@pytest.fixture()
def client(app) -> TestClient:
    """Test client for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


class TestWorkflowTemplateModel:
    """Tests for the WorkflowTemplate Pydantic model."""

    def test_valid_creation(self, sample_template):
        assert sample_template.id == "tpl-test"
        assert sample_template.name == "Test Template"
        assert sample_template.is_system is False
        assert len(sample_template.placeholders) == 2

    def test_system_template(self):
        tmpl = WorkflowTemplate(
            id="tpl-system",
            name="System Template",
            is_system=True,
            category="system",
            template_data={"nodes": [], "edges": []},
        )
        assert tmpl.is_system is True
        assert tmpl.category == "system"

    def test_extract_placeholder_keys(self, sample_template):
        keys = sample_template.extract_placeholder_keys()
        assert "strategist_id" in keys
        assert "max_rounds" in keys

    def test_instantiate_with_values(self, sample_template):
        result = sample_template.instantiate({"strategist_id": "bp-123", "max_rounds": 3})
        assert result["nodes"][1]["agent_blueprint_id"] == "bp-123"
        # Note: JSON string replacement produces string values for integers
        assert str(result["termination_conditions"][0]["value"]) == "3"

    def test_instantiate_uses_defaults(self, sample_template):
        # max_rounds has default=5, only strategist_id is required
        result = sample_template.instantiate({"strategist_id": "bp-456"})
        assert str(result["termination_conditions"][0]["value"]) == "5"

    def test_instantiate_missing_required_raises(self, sample_template):
        with pytest.raises(ValueError, match="Missing placeholder values"):
            sample_template.instantiate({})

    def test_template_data_must_have_nodes(self):
        with pytest.raises(Exception, match="nodes"):
            WorkflowTemplate(
                id="bad",
                name="Bad",
                template_data={"edges": []},
            )


class TestTemplatePlaceholder:
    """Tests for the TemplatePlaceholder model."""

    def test_valid_creation(self):
        ph = TemplatePlaceholder(key="my_key", type="string", default="hello")
        assert ph.key == "my_key"
        assert ph.default == "hello"

    def test_invalid_key_pattern(self):
        with pytest.raises(Exception):
            TemplatePlaceholder(key="Invalid-Key!", type="string")

    def test_valid_types(self):
        for t in ("string", "blueprint_ref", "integer", "float"):
            ph = TemplatePlaceholder(key=f"k_{t}", type=t)
            assert ph.type == t


# ---------------------------------------------------------------------------
# Repository Tests
# ---------------------------------------------------------------------------


class TestWorkflowTemplateRepository:
    """Repository CRUD for workflow templates."""

    def test_save_and_get(self, repo, sample_template):
        repo.save_workflow_template(sample_template)
        retrieved = repo.get_workflow_template("tpl-test")
        assert retrieved is not None
        assert retrieved.name == "Test Template"
        assert len(retrieved.placeholders) == 2

    def test_list_all(self, repo, sample_template):
        repo.save_workflow_template(sample_template)
        system = WorkflowTemplate(
            id="tpl-sys",
            name="System",
            is_system=True,
            category="system",
            template_data={"nodes": [], "edges": []},
        )
        repo.save_workflow_template(system)
        all_templates = repo.list_workflow_templates()
        assert len(all_templates) == 2

    def test_list_filtered_by_category(self, repo, sample_template):
        repo.save_workflow_template(sample_template)
        system = WorkflowTemplate(
            id="tpl-sys",
            name="System",
            is_system=True,
            category="system",
            template_data={"nodes": [], "edges": []},
        )
        repo.save_workflow_template(system)
        custom = repo.list_workflow_templates(category="custom")
        assert len(custom) == 1
        assert custom[0].id == "tpl-test"

    def test_delete(self, repo, sample_template):
        repo.save_workflow_template(sample_template)
        assert repo.delete_workflow_template("tpl-test") is True
        assert repo.get_workflow_template("tpl-test") is None

    def test_delete_nonexistent(self, repo):
        assert repo.delete_workflow_template("nonexistent") is False

    def test_get_nonexistent(self, repo):
        assert repo.get_workflow_template("nonexistent") is None


# ---------------------------------------------------------------------------
# Seed Tests
# ---------------------------------------------------------------------------


class TestSeedTemplates:
    """Tests for the seed_templates module."""

    def test_seed_creates_templates(self, repo):
        templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        result = seed_system_templates(repo=repo, templates_dir=templates_dir)
        assert result["created"] == 9
        assert result["updated"] == 0
        assert result["skipped"] == 0

        # Verify all nine exist
        for tid in (
            "tpl-standard-debate",
            "tpl-kantian-analysis",
            "tpl-quick-review",
            "tpl-dialectic-debate",
            "tpl-interview",
            "tpl-mediation",
            "tpl-streitgespraech",
            "tpl-transactional-drafting",
            "tpl-five-phase-debate",
        ):
            tmpl = repo.get_workflow_template(tid)
            assert tmpl is not None
            assert tmpl.is_system is True
            assert tmpl.category == "system"

    def test_seed_is_idempotent(self, repo):
        templates_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        seed_system_templates(repo=repo, templates_dir=templates_dir)
        result = seed_system_templates(repo=repo, templates_dir=templates_dir)
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result["skipped"] == 9

    def test_seed_updates_on_change(self, repo, tmp_path):
        """Modify a template file and verify seed detects the change."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        tmpl = {
            "id": "tpl-test-seed",
            "name": "Test Seed",
            "template_data": {"nodes": [{"id": "n1", "type": "wf-input"}], "edges": []},
            "placeholders": [],
            "is_system": True,
        }
        (templates_dir / "test.json").write_text(json.dumps(tmpl))

        seed_system_templates(repo=repo, templates_dir=templates_dir)
        assert repo.get_workflow_template("tpl-test-seed") is not None

        # Modify
        tmpl["name"] = "Updated Seed"
        (templates_dir / "test.json").write_text(json.dumps(tmpl))
        result = seed_system_templates(repo=repo, templates_dir=templates_dir)
        assert result["updated"] == 1
        assert repo.get_workflow_template("tpl-test-seed").name == "Updated Seed"


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestWorkflowTemplateAPI:
    """Tests for /api/v1/workflow-templates endpoints."""

    def test_list_returns_list(self, client):
        response = client.get("/api/v1/workflow-templates")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_create(self, client, sample_template):
        payload = sample_template.model_dump(mode="json")
        response = client.post("/api/v1/workflow-templates", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "tpl-test"
        assert data["is_system"] is False

    def test_get_by_id(self, client, sample_template):
        client.post("/api/v1/workflow-templates", json=sample_template.model_dump(mode="json"))
        response = client.get("/api/v1/workflow-templates/tpl-test")
        assert response.status_code == 200
        assert response.json()["name"] == "Test Template"

    def test_get_not_found(self, client):
        response = client.get("/api/v1/workflow-templates/nonexistent")
        assert response.status_code == 404

    def test_update_custom(self, client, sample_template):
        client.post("/api/v1/workflow-templates", json=sample_template.model_dump(mode="json"))
        updated = sample_template.model_dump(mode="json")
        updated["name"] = "Updated Template"
        response = client.put("/api/v1/workflow-templates/tpl-test", json=updated)
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Template"

    def test_update_system_forbidden(self, client, repo):
        system = WorkflowTemplate(
            id="tpl-sys",
            name="System",
            is_system=True,
            category="system",
            template_data={"nodes": [], "edges": []},
        )
        repo.save_workflow_template(system)
        response = client.put(
            "/api/v1/workflow-templates/tpl-sys",
            json=system.model_dump(mode="json"),
        )
        assert response.status_code == 403

    def test_delete_custom(self, client, sample_template):
        client.post("/api/v1/workflow-templates", json=sample_template.model_dump(mode="json"))
        response = client.delete("/api/v1/workflow-templates/tpl-test")
        assert response.status_code == 200
        # Verify deleted
        response = client.get("/api/v1/workflow-templates/tpl-test")
        assert response.status_code == 404

    def test_delete_system_forbidden(self, client, repo):
        system = WorkflowTemplate(
            id="tpl-sys",
            name="System",
            is_system=True,
            category="system",
            template_data={"nodes": [], "edges": []},
        )
        repo.save_workflow_template(system)
        response = client.delete("/api/v1/workflow-templates/tpl-sys")
        assert response.status_code == 403

    def test_create_conflict(self, client, sample_template):
        payload = sample_template.model_dump(mode="json")
        client.post("/api/v1/workflow-templates", json=payload)
        response = client.post("/api/v1/workflow-templates", json=payload)
        assert response.status_code == 409

    def test_filter_by_category(self, client, repo, sample_template):
        repo.save_workflow_template(sample_template)
        system = WorkflowTemplate(
            id="tpl-sys",
            name="System",
            is_system=True,
            category="system",
            template_data={"nodes": [], "edges": []},
        )
        repo.save_workflow_template(system)
        response = client.get("/api/v1/workflow-templates?category=system")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(t["category"] == "system" for t in data)


class TestInstantiateAPI:
    """Tests for POST /api/v1/workflow-templates/{id}/instantiate."""

    def test_instantiate_success(self, client, repo, sample_template, sample_blueprint):
        repo.save_workflow_template(sample_template)
        response = client.post(
            "/api/v1/workflow-templates/tpl-test/instantiate",
            json={
                "name": "My Workflow",
                "placeholder_values": {
                    "strategist_id": "bp-strategist",
                    "max_rounds": 3,
                },
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Workflow"
        assert data["template_id"] == "tpl-test"
        assert len(data["nodes"]) == 2
        # Verify placeholder was replaced
        assert data["nodes"][1]["agent_blueprint_id"] == "bp-strategist"

    def test_instantiate_uses_default(self, client, repo, sample_template, sample_blueprint):
        """max_rounds has default=5, so it's not required."""
        repo.save_workflow_template(sample_template)
        response = client.post(
            "/api/v1/workflow-templates/tpl-test/instantiate",
            json={
                "placeholder_values": {"strategist_id": "bp-strategist"},
            },
        )
        assert response.status_code == 201

    def test_instantiate_missing_placeholder(self, client, repo, sample_template):
        repo.save_workflow_template(sample_template)
        response = client.post(
            "/api/v1/workflow-templates/tpl-test/instantiate",
            json={"placeholder_values": {}},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "missing_placeholders"
        assert "strategist_id" in detail["missing"]

    def test_instantiate_invalid_blueprint_ref(self, client, repo, sample_template):
        repo.save_workflow_template(sample_template)
        response = client.post(
            "/api/v1/workflow-templates/tpl-test/instantiate",
            json={
                "placeholder_values": {"strategist_id": "nonexistent-bp"},
            },
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "invalid_blueprint_ref"

    def test_instantiate_not_found(self, client):
        response = client.post(
            "/api/v1/workflow-templates/nonexistent/instantiate",
            json={"placeholder_values": {}},
        )
        assert response.status_code == 404

    def test_instantiate_generates_default_name(self, client, repo, sample_template, sample_blueprint):
        repo.save_workflow_template(sample_template)
        response = client.post(
            "/api/v1/workflow-templates/tpl-test/instantiate",
            json={
                "placeholder_values": {"strategist_id": "bp-strategist"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert "Test Template" in data["name"]


class TestSaveAsTemplateAPI:
    """Tests for POST /api/v1/blueprints/workflows/{id}/save-as-template."""

    def test_save_as_template(self, client, repo):
        # Create a workflow first
        wf = WorkflowDefinition(
            id="wf-test",
            name="Test Workflow",
            nodes=[
                WorkflowNode(id="input-1", type="wf-input", label="Input"),
                WorkflowNode(
                    id="strat-1",
                    type="wf-strategist",
                    label="Strategist",
                    agent_blueprint_id="bp-123",
                ),
            ],
            edges=[
                WorkflowEdge(source="input-1", target="strat-1", type="sequential"),
            ],
            entry_point="input-1",
        )
        repo.save_workflow_definition(wf)

        response = client.post(
            "/api/v1/blueprints/workflows/wf-test/save-as-template",
            json={
                "name": "My Template",
                "description": "From workflow",
                "extracted_placeholders": ["agent_blueprint_id"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My Template"
        assert data["is_system"] is False
        assert data["source_workflow_id"] == "wf-test"

    def test_save_as_template_workflow_not_found(self, client):
        response = client.post(
            "/api/v1/blueprints/workflows/nonexistent/save-as-template",
            json={"name": "Test"},
        )
        assert response.status_code == 404


class TestWorkflowDefinitionTemplateId:
    """Tests for template_id field on WorkflowDefinition."""

    def test_template_id_persisted(self, repo):
        wf = WorkflowDefinition(
            id="wf-from-tpl",
            name="From Template",
            template_id="tpl-test",
        )
        repo.save_workflow_definition(wf)
        retrieved = repo.get_workflow_definition("wf-from-tpl")
        assert retrieved is not None
        assert retrieved.template_id == "tpl-test"

    def test_template_id_none_by_default(self, repo):
        wf = WorkflowDefinition(id="wf-no-tpl", name="No Template")
        repo.save_workflow_definition(wf)
        retrieved = repo.get_workflow_definition("wf-no-tpl")
        assert retrieved is not None
        assert retrieved.template_id is None
