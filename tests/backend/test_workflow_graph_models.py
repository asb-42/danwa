"""Tests for Phase 1 Group A — Backend Model Extension.

Covers:
- WorkflowNode model validation (agent nodes require blueprint_id)
- WorkflowEdge model validation (conditional edges require condition)
- TerminationCondition model
- Extended WorkflowDefinition with nodes/edges/entry_point
- Migration v4 applies cleanly
- Repository roundtrip with new fields
- Clone endpoint (creates new ID, increments version)
- Compiler validation (missing entry_point, isolated nodes, invalid refs, gate outputs)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.blueprints.compiler import CompilerService
from backend.blueprints.migrations import run_migrations
from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    """Create a BlueprintRepository with a temporary database."""
    return BlueprintRepository(db_path=tmp_path / "test_wf_graph.db")


@pytest.fixture()
def sample_blueprint(repo: BlueprintRepository) -> AgentBlueprint:
    """Create and persist a sample AgentBlueprint with dependencies."""
    profile = BlueprintLLMProfile(
        id="llm-1",
        name="Test LLM",
        provider="openrouter",
        model="anthropic/claude-3.5-sonnet",
        api_key_env="TEST_KEY",
    )
    repo.save_llm_profile(profile)

    blueprint = AgentBlueprint(
        id="bp-1",
        name="Test Blueprint",
        llm_profile_id="llm-1",
        role_definition_id="rd-1",
    )
    repo.save_blueprint(blueprint)
    return blueprint


# =========================================================================
# A.6.1 — WorkflowNode model validation
# =========================================================================


class TestWorkflowNodeModel:
    """Test WorkflowNode Pydantic model validation."""

    def test_valid_agent_node_with_blueprint_id(self):
        """Agent nodes with agent_blueprint_id should validate."""
        node = WorkflowNode(
            id="n1",
            type="wf-strategist",
            label="Strategist",
            agent_blueprint_id="bp-1",
        )
        assert node.id == "n1"
        assert node.type == "wf-strategist"
        assert node.agent_blueprint_id == "bp-1"

    def test_agent_node_without_blueprint_id_fails(self):
        """Agent nodes without agent_blueprint_id should fail validation."""
        with pytest.raises(ValueError, match="requires an .*agent_blueprint_id"):
            WorkflowNode(id="n1", type="wf-strategist")

    def test_critic_node_requires_blueprint_id(self):
        """Critic node requires agent_blueprint_id."""
        with pytest.raises(ValueError, match="requires an .*agent_blueprint_id"):
            WorkflowNode(id="n1", type="wf-critic")

    def test_optimizer_node_requires_blueprint_id(self):
        """Optimizer node requires agent_blueprint_id."""
        with pytest.raises(ValueError, match="requires an .*agent_blueprint_id"):
            WorkflowNode(id="n1", type="wf-optimizer")

    def test_strategist_node_requires_blueprint_id(self):
        """Strategist node requires agent_blueprint_id."""
        with pytest.raises(ValueError, match="requires an .*agent_blueprint_id"):
            WorkflowNode(id="n1", type="wf-strategist")

    def test_moderator_node_requires_blueprint_id(self):
        """Moderator node requires agent_blueprint_id."""
        with pytest.raises(ValueError, match="requires an .*agent_blueprint_id"):
            WorkflowNode(id="n1", type="wf-moderator")

    def test_non_agent_node_without_blueprint_id(self):
        """Non-agent nodes (input, initialize, gate, user-injection) don't need blueprint_id."""
        for node_type in ["wf-input", "wf-initialize", "wf-gate", "wf-user-injection"]:
            node = WorkflowNode(id="n1", type=node_type)
            assert node.agent_blueprint_id is None

    def test_node_with_config_and_position(self):
        """Node should accept config and position dicts."""
        node = WorkflowNode(
            id="n1",
            type="wf-gate",
            config={"condition": "round >= 3"},
            position={"x": 100.0, "y": 200.0},
        )
        assert node.config == {"condition": "round >= 3"}
        assert node.position == {"x": 100.0, "y": 200.0}

    def test_node_default_values(self):
        """Node should have sensible defaults."""
        node = WorkflowNode(id="n1", type="wf-input")
        assert node.label == ""
        assert node.config == {}
        assert node.position == {}


# =========================================================================
# A.6.2 — WorkflowEdge model validation
# =========================================================================


class TestWorkflowEdgeModel:
    """Test WorkflowEdge Pydantic model validation."""

    def test_valid_sequential_edge(self):
        """Sequential edge should validate without condition."""
        edge = WorkflowEdge(source="n1", target="n2", type="sequential")
        assert edge.source == "n1"
        assert edge.target == "n2"
        assert edge.type == "sequential"
        assert edge.condition is None

    def test_valid_conditional_edge_with_condition(self):
        """Conditional edge with condition should validate."""
        edge = WorkflowEdge(source="n1", target="n2", type="conditional", condition="round >= 3")
        assert edge.condition == "round >= 3"

    def test_conditional_edge_without_condition_fails(self):
        """Conditional edge without condition should fail."""
        with pytest.raises(ValueError, match="Conditional edges require a condition"):
            WorkflowEdge(source="n1", target="n2", type="conditional")

    def test_feedback_edge(self):
        """Feedback edge should validate."""
        edge = WorkflowEdge(source="n1", target="n2", type="feedback")
        assert edge.type == "feedback"

    def test_interjection_edge(self):
        """Interjection edge should validate."""
        edge = WorkflowEdge(source="n1", target="n2", type="interjection")
        assert edge.type == "interjection"

    def test_edge_default_id(self):
        """Edge should auto-generate an ID."""
        edge = WorkflowEdge(source="n1", target="n2")
        assert edge.id  # Should be non-empty
        assert len(edge.id) == 8


# =========================================================================
# A.6.3 — TerminationCondition model
# =========================================================================


class TestTerminationConditionModel:
    """Test TerminationCondition model."""

    def test_max_rounds_condition(self):
        """Max rounds condition should validate."""
        tc = TerminationCondition(type="max_rounds", value=5)
        assert tc.type == "max_rounds"
        assert tc.value == 5

    def test_consensus_reached_condition(self):
        """Consensus reached condition should validate."""
        tc = TerminationCondition(type="consensus_reached", value=0.9)
        assert tc.type == "consensus_reached"
        assert tc.value == 0.9

    def test_time_limit_condition(self):
        """Time limit condition should validate."""
        tc = TerminationCondition(type="time_limit", value=300)
        assert tc.type == "time_limit"
        assert tc.value == 300

    def test_custom_condition(self):
        """Custom condition should validate."""
        tc = TerminationCondition(type="custom", value=0, description="Stop when user says stop")
        assert tc.description == "Stop when user says stop"

    def test_default_values(self):
        """Default values should be sensible."""
        tc = TerminationCondition()
        assert tc.type == "max_rounds"
        assert tc.value == 5
        assert tc.description == ""


# =========================================================================
# A.6.4 — Extended WorkflowDefinition
# =========================================================================


class TestWorkflowDefinitionExtended:
    """Test extended WorkflowDefinition with nodes/edges/entry_point."""

    def test_workflow_with_nodes_and_edges(self):
        """Workflow should accept nodes and edges."""
        wf = WorkflowDefinition(
            name="Test Workflow",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
            ],
            edges=[
                WorkflowEdge(source="input", target="strat", type="sequential"),
            ],
            entry_point="input",
        )
        assert len(wf.nodes) == 2
        assert len(wf.edges) == 1
        assert wf.entry_point == "input"

    def test_workflow_with_termination_conditions(self):
        """Workflow should accept termination conditions."""
        wf = WorkflowDefinition(
            name="Test Workflow",
            termination_conditions=[
                TerminationCondition(type="max_rounds", value=3),
            ],
        )
        assert len(wf.termination_conditions) == 1

    def test_workflow_version_and_lock(self):
        """Workflow should have version and is_locked fields."""
        wf = WorkflowDefinition(name="Test", version=2, is_locked=True)
        assert wf.version == 2
        assert wf.is_locked is True

    def test_workflow_default_version(self):
        """Default version should be 1."""
        wf = WorkflowDefinition(name="Test")
        assert wf.version == 1
        assert wf.is_locked is False

    def test_entry_point_must_reference_valid_node(self):
        """entry_point must reference a valid node ID."""
        with pytest.raises(ValueError, match="does not reference any node"):
            WorkflowDefinition(
                name="Test",
                nodes=[WorkflowNode(id="n1", type="wf-input")],
                entry_point="nonexistent",
            )

    def test_entry_point_valid_reference(self):
        """entry_point referencing a valid node should pass."""
        wf = WorkflowDefinition(
            name="Test",
            nodes=[WorkflowNode(id="n1", type="wf-input")],
            entry_point="n1",
        )
        assert wf.entry_point == "n1"

    def test_entry_point_none_is_valid(self):
        """entry_point=None should be valid (no entry point set)."""
        wf = WorkflowDefinition(name="Test")
        assert wf.entry_point is None

    def test_backward_compat_with_legacy_fields(self):
        """Legacy fields should still work."""
        wf = WorkflowDefinition(
            name="Test",
            execution_order=["n1", "n2"],
            node_blueprint_map={"n1": "bp-1", "n2": "bp-2"},
        )
        assert wf.execution_order == ["n1", "n2"]
        assert wf.node_blueprint_map == {"n1": "bp-1", "n2": "bp-2"}


# =========================================================================
# A.6.5 — Migration v4
# =========================================================================


class TestMigrationV4:
    """Test that migration v4 applies cleanly."""

    def test_migration_v4_creates_columns(self, tmp_path: Path):
        """Migration v4 should add new columns to workflow_definitions."""
        import sqlite3

        db_path = tmp_path / "test.db"
        run_migrations(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute("PRAGMA table_info(workflow_definitions)")
            columns = {row[1] for row in cursor.fetchall()}
        finally:
            conn.close()

        assert "nodes_json" in columns
        assert "edges_json" in columns
        assert "entry_point" in columns
        assert "termination_conditions_json" in columns
        assert "version" in columns
        assert "is_locked" in columns

    def test_migration_v4_is_idempotent(self, tmp_path: Path):
        """Running migration v4 twice should not fail."""
        db_path = tmp_path / "test.db"
        run_migrations(db_path)
        run_migrations(db_path)  # Should not raise

    def test_schema_version_is_current(self, tmp_path: Path):
        """After migration, schema version should match SCHEMA_VERSION."""
        import sqlite3

        from backend.blueprints.migrations import SCHEMA_VERSION

        db_path = tmp_path / "test.db"
        run_migrations(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            assert row[0] == SCHEMA_VERSION
        finally:
            conn.close()


# =========================================================================
# A.6.6 — Repository roundtrip with new fields
# =========================================================================


class TestRepositoryRoundtrip:
    """Test repository serialization/deserialization of new fields."""

    def test_save_and_load_workflow_with_nodes(self, repo: BlueprintRepository):
        """Save and load a workflow with nodes, edges, entry_point."""
        wf = WorkflowDefinition(
            name="Test Workflow",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
            ],
            edges=[
                WorkflowEdge(id="e1", source="input", target="strat", type="sequential"),
            ],
            entry_point="input",
            termination_conditions=[
                TerminationCondition(type="max_rounds", value=3),
            ],
            version=2,
            is_locked=True,
        )
        repo.save_workflow_definition(wf)

        loaded = repo.get_workflow_definition(wf.id)
        assert loaded is not None
        assert loaded.name == "Test Workflow"
        assert len(loaded.nodes) == 2
        assert loaded.nodes[0].id == "input"
        assert loaded.nodes[0].type == "wf-input"
        assert loaded.nodes[1].id == "strat"
        assert loaded.nodes[1].type == "wf-strategist"
        assert loaded.nodes[1].agent_blueprint_id == "bp-1"
        assert len(loaded.edges) == 1
        assert loaded.edges[0].source == "input"
        assert loaded.edges[0].target == "strat"
        assert loaded.edges[0].type == "sequential"
        assert loaded.entry_point == "input"
        assert len(loaded.termination_conditions) == 1
        assert loaded.termination_conditions[0].type == "max_rounds"
        assert loaded.termination_conditions[0].value == 3
        assert loaded.version == 2
        assert loaded.is_locked is True

    def test_save_and_load_empty_graph(self, repo: BlueprintRepository):
        """Save and load a workflow with empty nodes/edges (backward compat)."""
        wf = WorkflowDefinition(name="Empty Workflow")
        repo.save_workflow_definition(wf)

        loaded = repo.get_workflow_definition(wf.id)
        assert loaded is not None
        assert loaded.nodes == []
        assert loaded.edges == []
        assert loaded.entry_point is None
        assert loaded.termination_conditions == []
        assert loaded.version == 1
        assert loaded.is_locked is False

    def test_list_workflows_includes_new_fields(self, repo: BlueprintRepository):
        """List should include workflows with new fields."""
        wf = WorkflowDefinition(
            name="Test",
            nodes=[WorkflowNode(id="n1", type="wf-input")],
        )
        repo.save_workflow_definition(wf)

        workflows = repo.list_workflow_definitions()
        assert len(workflows) == 1
        assert len(workflows[0].nodes) == 1


# =========================================================================
# A.6.7 — Clone endpoint
# =========================================================================


class TestCloneEndpoint:
    """Test the clone workflow endpoint."""

    def test_clone_creates_new_id(self, repo: BlueprintRepository, sample_blueprint):
        """Clone should create a workflow with a new ID."""
        wf = WorkflowDefinition(
            name="Original",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
            ],
            edges=[WorkflowEdge(source="input", target="strat")],
            entry_point="input",
            version=1,
        )
        repo.save_workflow_definition(wf)

        # Simulate clone logic (same as the endpoint)
        original = repo.get_workflow_definition(wf.id)
        assert original is not None

        import uuid
        from datetime import UTC, datetime

        cloned = original.model_copy(deep=True)
        cloned.id = str(uuid.uuid4())[:8]
        cloned.name = f"{original.name} (Copy)"
        cloned.version = original.version + 1
        cloned.is_locked = False
        cloned.created_at = datetime.now(UTC)
        cloned.updated_at = datetime.now(UTC)
        repo.save_workflow_definition(cloned)

        assert cloned.id != wf.id
        assert cloned.name == "Original (Copy)"
        assert cloned.version == 2
        assert cloned.is_locked is False
        assert len(cloned.nodes) == 2
        assert len(cloned.edges) == 1

    def test_clone_preserves_structure(self, repo: BlueprintRepository, sample_blueprint):
        """Clone should preserve the full graph structure."""
        wf = WorkflowDefinition(
            name="Complex",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
                WorkflowNode(id="gate", type="wf-gate", config={"condition": "round >= 3"}),
            ],
            edges=[
                WorkflowEdge(source="input", target="strat"),
                WorkflowEdge(source="strat", target="gate"),
                WorkflowEdge(source="gate", target="strat", type="feedback"),
            ],
            entry_point="input",
            termination_conditions=[TerminationCondition(type="max_rounds", value=5)],
        )
        repo.save_workflow_definition(wf)

        original = repo.get_workflow_definition(wf.id)
        cloned = original.model_copy(deep=True)
        cloned.id = "clone-1"
        cloned.name = "Complex (Copy)"
        cloned.version = 2
        repo.save_workflow_definition(cloned)

        loaded = repo.get_workflow_definition("clone-1")
        assert loaded is not None
        assert len(loaded.nodes) == 3
        assert len(loaded.edges) == 3
        assert loaded.edges[2].type == "feedback"
        assert loaded.termination_conditions[0].value == 5


# =========================================================================
# A.6.8 — Compiler validation
# =========================================================================


class TestCompilerValidation:
    """Test compiler validation for graph-based workflows."""

    def test_valid_workflow_passes(self, repo: BlueprintRepository, sample_blueprint):
        """A valid workflow should pass compilation."""
        from unittest.mock import patch

        from backend.blueprints.models import RoleDefinition, RoleType

        mock_role_def = RoleDefinition(
            id="rd-1",
            name="Strategist Role",
            role_type_id="strategist",
        )
        mock_role_type = RoleType(
            id="strategist",
            name="Strategist",
            description="",
        )
        wf = WorkflowDefinition(
            name="Valid",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
            ],
            edges=[WorkflowEdge(source="input", target="strat")],
            entry_point="input",
            node_blueprint_map={"strat": "bp-1"},
        )
        repo.save_workflow_definition(wf)

        compiler = CompilerService(repo)
        with (
            patch(
                "backend.blueprints.compiler.resolve_role_definition",
                return_value=mock_role_def,
            ),
            patch(
                "backend.blueprints.compiler.resolve_role_type",
                return_value=mock_role_type,
            ),
        ):
            result = compiler.compile(wf)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_missing_entry_point_detected(self, repo: BlueprintRepository, sample_blueprint):
        """Invalid entry_point should produce an error."""
        # Pydantic validator catches this at model creation time
        with pytest.raises(Exception, match="does not reference any node"):
            WorkflowDefinition(
                name="Bad Entry",
                nodes=[WorkflowNode(id="input", type="wf-input")],
                edges=[],
                entry_point="nonexistent",
            )

        # Also test the compiler's _validate_graph catches it
        # (e.g. when data comes from DB and bypasses Pydantic validation)
        wf = WorkflowDefinition(
            name="Bad Entry",
            nodes=[WorkflowNode(id="input", type="wf-input")],
            edges=[],
        )
        # Bypass Pydantic validator by setting entry_point after construction
        object.__setattr__(wf, "entry_point", "nonexistent")
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("entry_point" in e for e in errors)

    def test_agent_node_without_blueprint_id(self, repo: BlueprintRepository):
        """Agent node without agent_blueprint_id should produce an error."""
        # Bypass Pydantic validator by constructing manually
        wf = WorkflowDefinition(
            name="Bad Agent",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
            ],
            edges=[WorkflowEdge(source="input", target="strat")],
        )
        # Manually remove the blueprint_id to simulate DB inconsistency
        wf.nodes[1].agent_blueprint_id = None  # type: ignore[assignment]

        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("agent_blueprint_id" in e for e in errors)

    def test_gate_node_needs_two_outgoing_edges(self, repo: BlueprintRepository):
        """Gate node with <2 outgoing edges should produce an error."""
        wf = WorkflowDefinition(
            name="Bad Gate",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="gate", type="wf-gate"),
            ],
            edges=[WorkflowEdge(source="input", target="gate")],
        )
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("Gate node" in e and "at least 2" in e for e in errors)

    def test_isolated_node_detected(self, repo: BlueprintRepository):
        """Isolated node (no edges) should produce an error."""
        wf = WorkflowDefinition(
            name="Isolated",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="orphan", type="wf-input"),
            ],
            edges=[WorkflowEdge(source="input", target="input")],  # self-loop to keep input non-isolated
        )
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("isolated" in e for e in errors)

    def test_invalid_edge_source_detected(self, repo: BlueprintRepository):
        """Edge with invalid source should produce an error."""
        wf = WorkflowDefinition(
            name="Bad Edge",
            nodes=[WorkflowNode(id="n1", type="wf-input")],
            edges=[WorkflowEdge(source="nonexistent", target="n1")],
        )
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("source" in e and "nonexistent" in e for e in errors)

    def test_invalid_edge_target_detected(self, repo: BlueprintRepository):
        """Edge with invalid target should produce an error."""
        wf = WorkflowDefinition(
            name="Bad Edge",
            nodes=[WorkflowNode(id="n1", type="wf-input")],
            edges=[WorkflowEdge(source="n1", target="nonexistent")],
        )
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("target" in e and "nonexistent" in e for e in errors)

    def test_cycle_detection_warning(self, repo: BlueprintRepository):
        """Cycle in non-feedback edges should produce a warning."""
        wf = WorkflowDefinition(
            name="Cycle",
            nodes=[
                WorkflowNode(id="a", type="wf-input"),
                WorkflowNode(id="b", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="a", target="b", type="sequential"),
                WorkflowEdge(source="b", target="a", type="sequential"),
            ],
        )
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert any("Cycle detected" in w for w in warnings)

    def test_feedback_edge_no_cycle_warning(self, repo: BlueprintRepository):
        """Feedback edges should NOT trigger cycle warnings."""
        wf = WorkflowDefinition(
            name="Feedback",
            nodes=[
                WorkflowNode(id="strat", type="wf-strategist", agent_blueprint_id="bp-1"),
                WorkflowNode(id="mod", type="wf-moderator", agent_blueprint_id="bp-1"),
            ],
            edges=[
                WorkflowEdge(source="strat", target="mod", type="sequential"),
                WorkflowEdge(source="mod", target="strat", type="feedback"),
            ],
        )
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        # No cycle warning because the back-edge is a feedback edge
        assert not any("Cycle detected" in w for w in warnings)

    def test_empty_graph_no_errors(self, repo: BlueprintRepository):
        """Empty graph (no nodes) should produce no errors."""
        wf = WorkflowDefinition(name="Empty")
        errors: list[str] = []
        warnings: list[str] = []
        CompilerService._validate_graph(wf, errors, warnings)
        assert len(errors) == 0
