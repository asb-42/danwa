"""Tests for multi-phase debate workflow support.

Covers:
- WorkflowNode.parent_id field
- PhaseConfig model
- WorkflowDefinition.phase_configs roundtrip
- 8 new agent node types (wf-socratic-questioner, wf-expert-reviewer, etc.)
- wf-phase node type
- Canvas-to-workflow conversion with parent_id propagation
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.blueprints.canvas_to_workflow import (
    CANVAS_TO_WF_NODE_TYPE,
    CanvasToWorkflowConverter,
)
from backend.blueprints.models import (
    CanvasLayout,
    CanvasLayoutData,
    CanvasLayoutEdge,
    CanvasLayoutNode,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    AGENT_NODE_TYPES,
    INJECTABLE_AGENT_NODE_TYPES,
    WORKFLOW_NODE_TYPES,
    PhaseConfig,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)

# =========================================================================
# Helper factories
# =========================================================================


def _phase_node(node_id: str = "phase-1", label: str = "Opening Phase") -> CanvasLayoutNode:
    return CanvasLayoutNode(
        id=node_id,
        type="wf-phase",
        x=0,
        y=0,
        label=label,
        data={"label": label},
    )


def _wf_agent_node(
    node_type: str = "wf-strategist",
    node_id: str | None = None,
    blueprint_id: str | None = None,
    parent_id: str | None = None,
    x: float = 200,
    y: float = 0,
) -> CanvasLayoutNode:
    nid = node_id or f"{node_type}-1"
    bp_id = blueprint_id or nid
    return CanvasLayoutNode(
        id=nid,
        type=node_type,
        x=x,
        y=y,
        blueprint_id=bp_id,
        agent_blueprint_id=bp_id,
        parent_id=parent_id,
        label=node_type.replace("wf-", "").replace("-", " ").title(),
        data={
            "label": node_type.replace("wf-", "").replace("-", " ").title(),
            "agent_blueprint_id": bp_id,
        },
    )


def _wf_input_node(node_id: str = "input-1", x: float = 0, y: float = 0) -> CanvasLayoutNode:
    return CanvasLayoutNode(id=node_id, type="wf-input", x=x, y=y, label="Input", data={"label": "Input"})


def _sequential_edge(source: str, target: str, edge_id: str | None = None) -> CanvasLayoutEdge:
    return CanvasLayoutEdge(id=edge_id or f"e-{source}-{target}", source=source, target=target, type="sequential")


def _make_layout(
    layout_id: str = "test-layout",
    name: str = "Test Layout",
    nodes: list[CanvasLayoutNode] | None = None,
    edges: list[CanvasLayoutEdge] | None = None,
) -> CanvasLayout:
    return CanvasLayout(
        id=layout_id,
        name=name,
        layout_data=CanvasLayoutData(nodes=nodes or [], edges=edges or []),
    )


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    return BlueprintRepository(db_path=tmp_path / "test.db")


# =========================================================================
# A — WorkflowNode.parent_id
# =========================================================================


class TestWorkflowNodeParentId:
    def test_parent_id_default_is_none(self):
        """parent_id should default to None."""
        node = WorkflowNode(id="n1", type="wf-strategist", agent_blueprint_id="bp-1")
        assert node.parent_id is None

    def test_parent_id_set(self):
        """parent_id should be settable."""
        node = WorkflowNode(
            id="n1",
            type="wf-strategist",
            agent_blueprint_id="bp-1",
            parent_id="phase-1",
        )
        assert node.parent_id == "phase-1"

    def test_parent_id_on_non_agent_node(self):
        """Non-agent nodes should also support parent_id."""
        node = WorkflowNode(id="n1", type="wf-input", parent_id="phase-1")
        assert node.parent_id == "phase-1"

    def test_wf_phase_node(self):
        """wf-phase node type should be valid."""
        node = WorkflowNode(id="phase-1", type="wf-phase")
        assert node.type == "wf-phase"
        assert node.agent_blueprint_id is None

    def test_parent_id_serialization_roundtrip(self, repo: BlueprintRepository):
        """parent_id should survive JSON serialization/deserialization."""
        wf = WorkflowDefinition(
            name="Phase Test",
            nodes=[
                WorkflowNode(id="phase-1", type="wf-phase"),
                WorkflowNode(
                    id="strat-1",
                    type="wf-strategist",
                    agent_blueprint_id="bp-1",
                    parent_id="phase-1",
                ),
            ],
        )
        repo.save_workflow_definition(wf)
        loaded = repo.get_workflow_definition(wf.id)
        assert loaded is not None
        strat = next(n for n in loaded.nodes if n.id == "strat-1")
        assert strat.parent_id == "phase-1"


# =========================================================================
# B — 8 new agent node types
# =========================================================================


class TestNewAgentNodeTypes:
    def test_all_new_types_in_workflow_node_types(self):
        """All 8 new agent types should be in WORKFLOW_NODE_TYPES."""
        new_types = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        for t in new_types:
            assert t in WORKFLOW_NODE_TYPES, f"{t} missing from WORKFLOW_NODE_TYPES"

    def test_all_new_types_in_agent_node_types(self):
        """All 8 new agent types should be in AGENT_NODE_TYPES."""
        new_types = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        for t in new_types:
            assert t in AGENT_NODE_TYPES, f"{t} missing from AGENT_NODE_TYPES"

    def test_all_new_types_in_injectable_types(self):
        """All 8 new agent types should be in INJECTABLE_AGENT_NODE_TYPES."""
        new_types = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        for t in new_types:
            assert t in INJECTABLE_AGENT_NODE_TYPES, f"{t} missing from INJECTABLE_AGENT_NODE_TYPES"

    def test_all_new_types_in_canvas_to_wf_map(self):
        """All 8 new agent types should be in CANVAS_TO_WF_NODE_TYPE."""
        new_types = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        for t in new_types:
            assert t in CANVAS_TO_WF_NODE_TYPE, f"{t} missing from CANVAS_TO_WF_NODE_TYPE"

    def test_each_new_type_requires_blueprint_id(self):
        """Each new agent type should require agent_blueprint_id."""
        types_without_bp = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        for t in types_without_bp:
            with pytest.raises(ValueError, match="requires an .*agent_blueprint_id"):
                WorkflowNode(id="n1", type=t)

    def test_each_new_type_accepts_blueprint_id(self):
        """Each new agent type should validate with a blueprint ID."""
        types = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        for t in types:
            node = WorkflowNode(id="n1", type=t, agent_blueprint_id="bp-1")
            assert node.agent_blueprint_id == "bp-1"
            assert node.type == t

    def test_wf_phase_not_in_agent_node_types(self):
        """wf-phase should NOT be in AGENT_NODE_TYPES (it is a container, not an agent)."""
        assert "wf-phase" not in AGENT_NODE_TYPES

    def test_wf_phase_in_workflow_node_types(self):
        """wf-phase should be in WORKFLOW_NODE_TYPES."""
        assert "wf-phase" in WORKFLOW_NODE_TYPES


# =========================================================================
# C — PhaseConfig model
# =========================================================================


class TestPhaseConfigModel:
    def test_phase_config_defaults(self):
        """PhaseConfig should have sensible defaults."""
        pc = PhaseConfig(phase_node_id="phase-1")
        assert pc.phase_node_id == "phase-1"
        assert pc.name == "Phase"
        assert pc.description == ""
        assert pc.roles == []
        assert pc.max_rounds == 3
        assert pc.color == "#6366f1"

    def test_phase_config_with_all_fields(self):
        """PhaseConfig should accept all fields."""
        pc = PhaseConfig(
            phase_node_id="phase-1",
            name="Opening Statements",
            description="First phase: opening positions",
            roles=["wf-strategist", "wf-critic"],
            max_rounds=5,
            color="#ef4444",
        )
        assert pc.name == "Opening Statements"
        assert pc.roles == ["wf-strategist", "wf-critic"]
        assert pc.max_rounds == 5
        assert pc.color == "#ef4444"

    def test_max_rounds_validation(self):
        """max_rounds should be between 1 and 50."""
        PhaseConfig(phase_node_id="p1", max_rounds=1)
        PhaseConfig(phase_node_id="p1", max_rounds=50)
        with pytest.raises(ValueError):
            PhaseConfig(phase_node_id="p1", max_rounds=0)
        with pytest.raises(ValueError):
            PhaseConfig(phase_node_id="p1", max_rounds=51)


# =========================================================================
# D — WorkflowDefinition.phase_configs
# =========================================================================


class TestWorkflowDefinitionPhaseConfigs:
    def test_phase_configs_default_to_empty(self):
        """phase_configs should default to empty dict."""
        wf = WorkflowDefinition(name="Phase Workflow")
        assert wf.phase_configs == {}

    def test_phase_configs_with_multiple_phases(self):
        """phase_configs should hold multiple PhaseConfig entries."""
        wf = WorkflowDefinition(
            name="Multi-Phase",
            phase_configs={
                "phase-1": PhaseConfig(
                    phase_node_id="phase-1",
                    name="Opening",
                    roles=["wf-strategist", "wf-critic"],
                ),
                "phase-2": PhaseConfig(
                    phase_node_id="phase-2",
                    name="Rebuttal",
                    roles=["wf-devils-advocate", "wf-mediator"],
                ),
            },
        )
        assert len(wf.phase_configs) == 2
        assert wf.phase_configs["phase-1"].name == "Opening"
        assert wf.phase_configs["phase-2"].name == "Rebuttal"

    def test_phase_configs_serialization_roundtrip(self, repo: BlueprintRepository):
        """phase_configs should survive JSON roundtrip through repository."""
        wf = WorkflowDefinition(
            name="Phase Roundtrip",
            nodes=[
                WorkflowNode(id="phase-1", type="wf-phase"),
                WorkflowNode(id="phase-2", type="wf-phase"),
            ],
            phase_configs={
                "phase-1": PhaseConfig(
                    phase_node_id="phase-1",
                    name="Opening",
                    roles=["wf-strategist"],
                    max_rounds=3,
                    color="#6366f1",
                ),
                "phase-2": PhaseConfig(
                    phase_node_id="phase-2",
                    name="Rebuttal",
                    roles=["wf-devils-advocate"],
                    max_rounds=5,
                    color="#ef4444",
                ),
            },
        )
        repo.save_workflow_definition(wf)
        loaded = repo.get_workflow_definition(wf.id)
        assert loaded is not None
        assert len(loaded.phase_configs) == 2
        assert loaded.phase_configs["phase-1"].name == "Opening"
        assert loaded.phase_configs["phase-1"].max_rounds == 3
        assert loaded.phase_configs["phase-2"].name == "Rebuttal"
        assert loaded.phase_configs["phase-2"].color == "#ef4444"

    def test_phase_configs_empty_roundtrip(self, repo: BlueprintRepository):
        """Empty phase_configs should roundtrip correctly."""
        wf = WorkflowDefinition(name="No Phases")
        repo.save_workflow_definition(wf)
        loaded = repo.get_workflow_definition(wf.id)
        assert loaded is not None
        assert loaded.phase_configs == {}

    def test_phase_configs_with_nodes_and_edges(self, repo: BlueprintRepository):
        """phase_configs should coexist with nodes, edges, entry_point."""
        wf = WorkflowDefinition(
            name="Full Phase Workflow",
            nodes=[
                WorkflowNode(id="input", type="wf-input"),
                WorkflowNode(id="phase-1", type="wf-phase"),
                WorkflowNode(
                    id="strat-1",
                    type="wf-strategist",
                    agent_blueprint_id="bp-1",
                    parent_id="phase-1",
                ),
            ],
            edges=[
                WorkflowEdge(source="input", target="phase-1", type="sequential"),
            ],
            entry_point="input",
            phase_configs={
                "phase-1": PhaseConfig(
                    phase_node_id="phase-1",
                    name="Opening",
                    roles=["wf-strategist"],
                ),
            },
        )
        repo.save_workflow_definition(wf)
        loaded = repo.get_workflow_definition(wf.id)
        assert loaded is not None
        assert loaded.entry_point == "input"
        assert len(loaded.nodes) == 3
        assert len(loaded.edges) == 1
        strat = next(n for n in loaded.nodes if n.id == "strat-1")
        assert strat.parent_id == "phase-1"
        assert loaded.phase_configs["phase-1"].roles == ["wf-strategist"]


# =========================================================================
# E — Canvas-to-workflow conversion with parent_id
# =========================================================================


class TestCanvasToWorkflowWithPhases:
    """Test that parent_id is propagated during canvas-to-workflow conversion."""

    def test_phase_node_included_in_conversion(self, repo: BlueprintRepository):
        """wf-phase canvas nodes should be included in the workflow."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[_phase_node("phase-1"), _wf_input_node("input-1")],
            edges=[_sequential_edge("input-1", "phase-1")],
        )
        wf = converter.convert(layout)
        phase_nodes = [n for n in wf.nodes if n.type == "wf-phase"]
        assert len(phase_nodes) == 1
        assert phase_nodes[0].id == "phase-1"

    def test_parent_id_propagated_to_child_nodes(self, repo: BlueprintRepository):
        """parent_id on canvas nodes should be propagated to WorkflowNode."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _phase_node("phase-1"),
                _wf_agent_node("wf-strategist", node_id="strat-1", parent_id="phase-1"),
                _wf_input_node("input-1"),
            ],
            edges=[
                _sequential_edge("input-1", "phase-1"),
                _sequential_edge("phase-1", "strat-1"),
            ],
        )
        wf = converter.convert(layout)
        strat = next(n for n in wf.nodes if n.id == "strat-1")
        assert strat.parent_id == "phase-1"

    def test_multiple_children_in_same_phase(self, repo: BlueprintRepository):
        """Multiple child nodes in the same phase should all have parent_id."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _phase_node("phase-1"),
                _wf_agent_node("wf-strategist", node_id="strat-1", parent_id="phase-1"),
                _wf_agent_node("wf-critic", node_id="critic-1", parent_id="phase-1"),
                _wf_input_node("input-1"),
            ],
            edges=[
                _sequential_edge("input-1", "phase-1"),
                _sequential_edge("phase-1", "strat-1"),
                _sequential_edge("strat-1", "critic-1"),
            ],
        )
        wf = converter.convert(layout)
        strat = next(n for n in wf.nodes if n.id == "strat-1")
        critic = next(n for n in wf.nodes if n.id == "critic-1")
        assert strat.parent_id == "phase-1"
        assert critic.parent_id == "phase-1"

    def test_multi_phase_conversion(self, repo: BlueprintRepository):
        """Multiple phases with their respective children should convert."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node("input-1"),
                _phase_node("phase-opening", label="Opening"),
                _phase_node("phase-rebuttal", label="Rebuttal"),
                _wf_agent_node("wf-strategist", node_id="strat-1", parent_id="phase-opening"),
                _wf_agent_node("wf-critic", node_id="critic-1", parent_id="phase-opening"),
                _wf_agent_node("wf-devils-advocate", node_id="da-1", parent_id="phase-rebuttal"),
                _wf_agent_node("wf-mediator", node_id="med-1", parent_id="phase-rebuttal"),
            ],
            edges=[
                _sequential_edge("input-1", "phase-opening"),
                _sequential_edge("phase-opening", "phase-rebuttal"),
                _sequential_edge("phase-opening", "strat-1"),
                _sequential_edge("strat-1", "critic-1"),
                _sequential_edge("phase-rebuttal", "da-1"),
                _sequential_edge("da-1", "med-1"),
            ],
        )
        wf = converter.convert(layout, name="Multi-Phase Debate")
        assert wf.name == "Multi-Phase Debate"
        assert len(wf.nodes) == 7

        phases = [n for n in wf.nodes if n.type == "wf-phase"]
        assert len(phases) == 2

        opening_children = [n for n in wf.nodes if n.parent_id == "phase-opening"]
        rebuttal_children = [n for n in wf.nodes if n.parent_id == "phase-rebuttal"]
        assert len(opening_children) == 2
        assert len(rebuttal_children) == 2

        strat = next(n for n in wf.nodes if n.id == "strat-1")
        assert strat.parent_id == "phase-opening"
        da = next(n for n in wf.nodes if n.id == "da-1")
        assert da.parent_id == "phase-rebuttal"

    def test_node_without_parent_id_stays_none(self, repo: BlueprintRepository):
        """Nodes without parent_id in canvas should have None in workflow."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_agent_node("wf-strategist", node_id="strat-1"),
            ],
            edges=[_sequential_edge("input-1", "strat-1")],
        )
        wf = converter.convert(layout)
        strat = next(n for n in wf.nodes if n.id == "strat-1")
        assert strat.parent_id is None

    def test_new_agent_types_converted(self, repo: BlueprintRepository):
        """All new agent types should convert from canvas to workflow nodes."""
        converter = CanvasToWorkflowConverter(repo)
        new_types = [
            "wf-socratic-questioner",
            "wf-expert-reviewer",
            "wf-steel-manner",
            "wf-devils-advocate",
            "wf-troll",
            "wf-mediator",
            "wf-ethicist",
            "wf-synthesizer",
        ]
        nodes = [_wf_input_node("input-1")]
        edges = []
        for i, t in enumerate(new_types):
            nid = f"node-{i}"
            nodes.append(_wf_agent_node(t, node_id=nid))
            edges.append(_sequential_edge("input-1" if i == 0 else f"node-{i - 1}", nid))

        layout = _make_layout(nodes=nodes, edges=edges)
        wf = converter.convert(layout, name="All New Types")
        assert len(wf.nodes) == len(new_types) + 1  # +1 for input

        converted_types = {n.type for n in wf.nodes}
        for t in new_types:
            assert t in converted_types, f"{t} not converted"

    def test_all_new_types_resolve_blueprint_id(self, repo: BlueprintRepository):
        """Each new agent type should resolve its agent_blueprint_id from canvas data."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_agent_node("wf-socratic-questioner", node_id="sq-1", blueprint_id="bp-sq"),
                _wf_agent_node("wf-synthesizer", node_id="syn-1", blueprint_id="bp-syn"),
            ],
            edges=[
                _sequential_edge("input-1", "sq-1"),
                _sequential_edge("sq-1", "syn-1"),
            ],
        )
        wf = converter.convert(layout)
        sq = next(n for n in wf.nodes if n.type == "wf-socratic-questioner")
        syn = next(n for n in wf.nodes if n.type == "wf-synthesizer")
        assert sq.agent_blueprint_id == "bp-sq"
        assert syn.agent_blueprint_id == "bp-syn"

    def test_phase_children_with_all_new_types(self, repo: BlueprintRepository):
        """Phase with all new agent types as children should convert correctly."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node("input-1"),
                _phase_node("phase-1"),
                _wf_agent_node("wf-socratic-questioner", node_id="sq-1", parent_id="phase-1"),
                _wf_agent_node("wf-ethicist", node_id="eth-1", parent_id="phase-1"),
                _wf_agent_node("wf-synthesizer", node_id="syn-1", parent_id="phase-1"),
            ],
            edges=[
                _sequential_edge("input-1", "phase-1"),
                _sequential_edge("phase-1", "sq-1"),
                _sequential_edge("sq-1", "eth-1"),
                _sequential_edge("eth-1", "syn-1"),
            ],
        )
        wf = converter.convert(layout, name="Phase with New Types")
        phase_children = [n for n in wf.nodes if n.parent_id == "phase-1"]
        assert len(phase_children) == 3
        child_types = {n.type for n in phase_children}
        assert "wf-socratic-questioner" in child_types
        assert "wf-ethicist" in child_types
        assert "wf-synthesizer" in child_types

    def test_fact_checker_analyst_creative_conversion(self, repo: BlueprintRepository):
        """wf-fact-checker, wf-analyst, wf-creative should also convert."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_agent_node("wf-fact-checker", node_id="fc-1"),
                _wf_agent_node("wf-analyst", node_id="an-1"),
                _wf_agent_node("wf-creative", node_id="cr-1"),
            ],
            edges=[
                _sequential_edge("input-1", "fc-1"),
                _sequential_edge("fc-1", "an-1"),
                _sequential_edge("an-1", "cr-1"),
            ],
        )
        wf = converter.convert(layout)
        types = {n.type for n in wf.nodes}
        assert "wf-fact-checker" in types
        assert "wf-analyst" in types
        assert "wf-creative" in types

    def test_parent_id_from_data_fallback(self, repo: BlueprintRepository):
        """parent_id should fall back to data.parentId when not on the canvas node."""
        converter = CanvasToWorkflowConverter(repo)
        strat = CanvasLayoutNode(
            id="strat-1",
            type="wf-strategist",
            x=200,
            y=0,
            blueprint_id="bp-1",
            agent_blueprint_id="bp-1",
            label="Strategist",
            parent_id=None,
            data={"parentId": "phase-1", "agent_blueprint_id": "bp-1"},
        )
        layout = _make_layout(
            nodes=[_phase_node("phase-1"), _wf_input_node(), strat],
            edges=[
                _sequential_edge("input-1", "phase-1"),
                _sequential_edge("phase-1", "strat-1"),
            ],
        )
        wf = converter.convert(layout)
        strat_node = next(n for n in wf.nodes if n.id == "strat-1")
        assert strat_node.parent_id == "phase-1"
