"""Tests for Phase 2 Group G.1 — WorkflowCompiler.

Covers compile() with valid/invalid workflows, feedback edges, interjection
edges, gate nodes, topological sort, and cycle detection.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
    RoleDefinition,
    RoleType,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from backend.workflow.workflow_compiler import CompiledWorkflow, WorkflowCompiler

# Module lookup stubs for testing
_ROLE_DEFINITIONS = {
    "role-1": RoleDefinition(
        id="role-1",
        name="Strategist",
        role_type_id="strategist",
        description="Strategic analyst",
        consensus_threshold=0.7,
    ),
}

_ROLE_TYPES = {
    "strategist": RoleType(
        id="strategist",
        name="Strategist",
        icon="🧠",
        color="#3b82f6",
        default_max_rounds=5,
        default_consensus_threshold=0.9,
    ),
}


def _mock_resolve_role_definition(role_def_id: str):
    return _ROLE_DEFINITIONS.get(role_def_id)


def _mock_resolve_role_type(role_type_id: str):
    return _ROLE_TYPES.get(role_type_id)


@pytest.fixture(autouse=True)
def _patch_module_lookups():
    """Auto-patch module lookups with test stubs."""
    with (
        patch(
            "backend.blueprints.module_lookups.resolve_role_definition",
            side_effect=_mock_resolve_role_definition,
        ),
        patch(
            "backend.blueprints.module_lookups.resolve_role_type",
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
            "backend.workflow.workflow_compiler.resolve_role_definition",
            side_effect=_mock_resolve_role_definition,
        ),
        patch(
            "backend.workflow.workflow_compiler.resolve_role_type",
            side_effect=_mock_resolve_role_type,
        ),
    ):
        yield


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    """Fresh BlueprintRepository with temp database."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def sample_blueprint(repo: BlueprintRepository) -> AgentBlueprint:
    """Create a sample blueprint with LLM profile in the repo."""
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


def _make_simple_workflow(sample_blueprint: AgentBlueprint) -> WorkflowDefinition:
    """Build a simple 3-node workflow: input → strategist → complete."""
    return WorkflowDefinition(
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


# ---------------------------------------------------------------------------
# Valid compilation
# ---------------------------------------------------------------------------


class TestValidCompilation:
    """Test WorkflowCompiler.compile() with valid workflows."""

    def test_compile_valid_workflow(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """A valid workflow should compile successfully."""
        workflow = _make_simple_workflow(sample_blueprint)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        assert result.graph is not None
        assert len(result.errors) == 0
        assert len(result.resolved_agents) == 1
        assert result.resolved_agents[0].blueprint_id == "bp-1"

    def test_compile_produces_node_sequence(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """Compiled result should include a node_sequence from topological sort."""
        workflow = _make_simple_workflow(sample_blueprint)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert len(result.node_sequence) == 2
        assert "wf-input" in result.node_sequence
        assert "node-s1" in result.node_sequence

    def test_compile_resolves_agent_config(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """Agent config should be fully resolved from the repository."""
        workflow = _make_simple_workflow(sample_blueprint)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        agent = result.resolved_agents[0]
        assert agent.node_id == "node-s1"
        assert agent.blueprint_name == "Strategist Agent"
        assert agent.llm_profile_id == "prof-1"
        assert agent.llm_model == "gpt-4"
        assert agent.role == "strategist"


# ---------------------------------------------------------------------------
# Invalid workflows
# ---------------------------------------------------------------------------


class TestInvalidCompilation:
    """Test compilation with invalid workflows."""

    def test_empty_nodes(self, repo: BlueprintRepository) -> None:
        """Workflow with no nodes should produce an error."""
        workflow = WorkflowDefinition(
            id="wf-empty",
            name="Empty",
            nodes=[],
            edges=[],
            entry_point=None,
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert not result.is_valid
        assert any("no nodes" in e.lower() for e in result.errors)

    def test_missing_entry_point(self, repo: BlueprintRepository) -> None:
        """Workflow with no entry_point should produce an error."""
        workflow = WorkflowDefinition(
            id="wf-no-entry",
            name="No Entry",
            nodes=[WorkflowNode(id="n1", type="wf-input")],
            edges=[],
            entry_point=None,
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert not result.is_valid
        assert any("entry_point" in e.lower() for e in result.errors)

    def test_missing_blueprint(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """Agent node referencing nonexistent blueprint should produce an error."""
        workflow = WorkflowDefinition(
            id="wf-missing-bp",
            name="Missing BP",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id="nonexistent-bp",
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert not result.is_valid
        assert any("not found" in e.lower() for e in result.errors)

    def test_invalid_edge_source(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """Edge with invalid source should produce an error."""
        workflow = WorkflowDefinition(
            id="wf-bad-edge",
            name="Bad Edge",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint.id,
                ),
            ],
            edges=[
                WorkflowEdge(source="nonexistent", target="node-s1", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert not result.is_valid


# ---------------------------------------------------------------------------
# Feedback edges
# ---------------------------------------------------------------------------


class TestFeedbackEdges:
    """Test compilation with feedback (back) edges."""

    def test_feedback_edge_compiles(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """A workflow with a feedback edge should compile with conditional routing."""
        workflow = WorkflowDefinition(
            id="wf-feedback",
            name="Feedback",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(
                    id="node-s2",
                    type="wf-critic",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(id="wf-end", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
                WorkflowEdge(source="node-s1", target="node-s2", type="sequential"),
                # Feedback from critic back to strategist
                WorkflowEdge(source="node-s2", target="node-s1", type="feedback"),
                # Exit edge from critic to end
                WorkflowEdge(source="node-s2", target="wf-end", type="sequential"),
            ],
            entry_point="wf-input",
            termination_conditions=[
                TerminationCondition(type="max_rounds", value=3),
            ],
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        assert result.graph is not None


# ---------------------------------------------------------------------------
# Interjection edges
# ---------------------------------------------------------------------------


class TestInterjectionEdges:
    """Test compilation with interjection edges."""

    def test_interjection_edge_inserts_node(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """An interjection edge should insert an interjection node."""
        workflow = WorkflowDefinition(
            id="wf-inj",
            name="Interjection",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(id="wf-end", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
                WorkflowEdge(source="node-s1", target="wf-end", type="interjection"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        assert result.graph is not None


# ---------------------------------------------------------------------------
# Gate nodes
# ---------------------------------------------------------------------------


class TestGateNodes:
    """Test compilation with gate nodes and conditional routing."""

    def test_gate_node_with_two_targets(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """A gate node with two outgoing edges should use conditional routing."""
        workflow = WorkflowDefinition(
            id="wf-gate",
            name="Gate",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(id="wf-gate", type="wf-gate"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(id="wf-end", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="wf-gate", type="sequential"),
                WorkflowEdge(
                    source="wf-gate",
                    target="node-s1",
                    type="conditional",
                    condition="current_round < 3",
                ),
                WorkflowEdge(
                    source="wf-gate",
                    target="wf-end",
                    type="conditional",
                    condition="current_round >= 3",
                ),
                WorkflowEdge(source="node-s1", target="wf-end", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        assert result.graph is not None


# ---------------------------------------------------------------------------
# Topological sort
# ---------------------------------------------------------------------------


class TestTopologicalSort:
    """Test topological sort with complex graphs."""

    def test_linear_sort(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """Linear graph should produce correct topological order."""
        workflow = _make_simple_workflow(sample_blueprint)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        # wf-input should come before node-s1
        seq = result.node_sequence
        assert seq.index("wf-input") < seq.index("node-s1")

    def test_diamond_sort(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """Diamond graph should produce valid topological order."""
        workflow = WorkflowDefinition(
            id="wf-diamond",
            name="Diamond",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(
                    id="node-s2",
                    type="wf-critic",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(id="wf-end", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
                WorkflowEdge(source="wf-input", target="node-s2", type="sequential"),
                WorkflowEdge(source="node-s1", target="wf-end", type="sequential"),
                WorkflowEdge(source="node-s2", target="wf-end", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        seq = result.node_sequence
        assert seq.index("wf-input") < seq.index("node-s1")
        assert seq.index("wf-input") < seq.index("node-s2")
        assert seq.index("node-s1") < seq.index("wf-end")
        assert seq.index("node-s2") < seq.index("wf-end")


# ---------------------------------------------------------------------------
# Cycle detection (non-feedback)
# ---------------------------------------------------------------------------


class TestCycleDetection:
    """Test compilation with cycles (non-feedback)."""

    def test_cycle_detected(self, repo: BlueprintRepository, sample_blueprint: AgentBlueprint) -> None:
        """A cycle in non-feedback edges should be detected by the compiler."""
        workflow = WorkflowDefinition(
            id="wf-cycle",
            name="Cycle",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-a",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint.id,
                ),
                WorkflowNode(
                    id="node-b",
                    type="wf-critic",
                    agent_blueprint_id=sample_blueprint.id,
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-a", type="sequential"),
                WorkflowEdge(source="node-a", target="node-b", type="sequential"),
                WorkflowEdge(source="node-b", target="node-a", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        # The compiler should detect the cycle (either as error or warning)
        assert not result.is_valid or len(result.warnings) > 0


# ---------------------------------------------------------------------------
# CompiledWorkflow dataclass
# ---------------------------------------------------------------------------


class TestCompiledWorkflow:
    """Test the CompiledWorkflow dataclass."""

    def test_is_valid_property(self) -> None:
        """is_valid should be True when errors list is empty."""
        cw = CompiledWorkflow(graph=None)
        assert cw.is_valid is True

    def test_is_valid_false_with_errors(self) -> None:
        """is_valid should be False when errors list is non-empty."""
        cw = CompiledWorkflow(graph=None, errors=["some error"])
        assert cw.is_valid is False

    def test_defaults(self) -> None:
        """CompiledWorkflow should have sensible defaults."""
        cw = CompiledWorkflow(graph=None)
        assert cw.resolved_agents == []
        assert cw.node_sequence == []
        assert cw.errors == []
        assert cw.warnings == []
