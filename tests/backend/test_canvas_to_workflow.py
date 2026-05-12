"""Tests for canvas-to-workflow conversion."""

from __future__ import annotations

import pytest

from backend.blueprints.canvas_to_workflow import (
    CanvasToWorkflowConverter,
    ConversionError,
)
from backend.blueprints.models import (
    CanvasLayout,
    CanvasLayoutData,
    CanvasLayoutEdge,
    CanvasLayoutNode,
)
from backend.blueprints.repository import BlueprintRepository


@pytest.fixture()
def repo(tmp_path) -> BlueprintRepository:
    return BlueprintRepository(db_path=tmp_path / "test.db")


def _make_layout(
    layout_id: str = "test-layout",
    name: str = "Test Layout",
    nodes: list[CanvasLayoutNode] | None = None,
    edges: list[CanvasLayoutEdge] | None = None,
) -> CanvasLayout:
    """Create a CanvasLayout with the given nodes and edges."""
    return CanvasLayout(
        id=layout_id,
        name=name,
        layout_data=CanvasLayoutData(
            nodes=nodes or [],
            edges=edges or [],
        ),
    )


def _wf_input_node(node_id: str = "input-1") -> CanvasLayoutNode:
    return CanvasLayoutNode(
        id=node_id,
        type="wf-input",
        x=0,
        y=0,
        label="Input",
        data={"label": "Input"},
    )


def _wf_strategist_node(
    node_id: str = "strat-1",
    blueprint_id: str | None = None,
) -> CanvasLayoutNode:
    # Use node_id as default blueprint_id so WorkflowNode validation passes
    bp_id = blueprint_id if blueprint_id is not None else node_id
    return CanvasLayoutNode(
        id=node_id,
        type="wf-strategist",
        x=200,
        y=0,
        blueprint_id=bp_id,
        agent_blueprint_id=bp_id,
        label="Strategist",
        data={"label": "Strategist", "agent_blueprint_id": bp_id},
    )


def _wf_critic_node(
    node_id: str = "critic-1",
    blueprint_id: str | None = None,
) -> CanvasLayoutNode:
    bp_id = blueprint_id if blueprint_id is not None else node_id
    return CanvasLayoutNode(
        id=node_id,
        type="wf-critic",
        x=400,
        y=0,
        blueprint_id=bp_id,
        agent_blueprint_id=bp_id,
        label="Critic",
        data={"label": "Critic", "agent_blueprint_id": bp_id},
    )


def _wf_moderator_node(
    node_id: str = "mod-1",
    blueprint_id: str | None = None,
) -> CanvasLayoutNode:
    bp_id = blueprint_id if blueprint_id is not None else node_id
    return CanvasLayoutNode(
        id=node_id,
        type="wf-moderator",
        x=600,
        y=0,
        blueprint_id=bp_id,
        agent_blueprint_id=bp_id,
        label="Moderator",
        config={"max_rounds": 7, "consensus_threshold": 0.85},
        data={
            "label": "Moderator",
            "agent_blueprint_id": bp_id,
            "config": {"max_rounds": 7, "consensus_threshold": 0.85},
        },
    )


def _wf_gate_node(node_id: str = "gate-1") -> CanvasLayoutNode:
    return CanvasLayoutNode(
        id=node_id,
        type="wf-gate",
        x=300,
        y=100,
        label="Gate",
        config={"condition": "round >= 3"},
        data={"label": "Gate", "config": {"condition": "round >= 3"}},
    )


def _sequential_edge(source: str, target: str, edge_id: str | None = None) -> CanvasLayoutEdge:
    return CanvasLayoutEdge(
        id=edge_id or f"e-{source}-{target}",
        source=source,
        target=target,
        type="sequential",
    )


def _feedback_edge(source: str, target: str, edge_id: str | None = None) -> CanvasLayoutEdge:
    return CanvasLayoutEdge(
        id=edge_id or f"e-{source}-{target}",
        source=source,
        target=target,
        type="feedback",
    )


def _blueprint_node(
    node_id: str,
    blueprint_id: str | None = None,
) -> CanvasLayoutNode:
    return CanvasLayoutNode(
        id=node_id,
        type="agent-blueprint",
        x=100,
        y=200,
        blueprint_id=blueprint_id or node_id,
        data={"blueprint_id": blueprint_id or node_id},
    )


# ──────────────────────────────────────────────────────────────────────


class TestCanvasToWorkflowConverter:
    """Tests for CanvasToWorkflowConverter.convert()."""

    def test_empty_canvas_raises_error(self, repo: BlueprintRepository) -> None:
        """Canvas with no workflow nodes should raise ConversionError."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(nodes=[], edges=[])

        with pytest.raises(ConversionError, match="no workflow nodes"):
            converter.convert(layout)

    def test_asset_only_canvas_raises_error(self, repo: BlueprintRepository) -> None:
        """Canvas with only asset nodes should raise ConversionError."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[_blueprint_node("bp-1"), _blueprint_node("bp-2")],
            edges=[],
        )

        with pytest.raises(ConversionError, match="no workflow nodes"):
            converter.convert(layout)

    def test_single_input_node(self, repo: BlueprintRepository) -> None:
        """Canvas with a single wf-input node should convert successfully."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(nodes=[_wf_input_node()])

        wf = converter.convert(layout)

        assert len(wf.nodes) == 1
        assert wf.nodes[0].type == "wf-input"
        assert wf.entry_point == "input-1"
        assert wf.canvas_layout_id == "test-layout"
        assert len(wf.termination_conditions) == 2

    def test_basic_workflow_with_edges(self, repo: BlueprintRepository) -> None:
        """Canvas with input → strategist → critic → moderator should convert."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_strategist_node(),
                _wf_critic_node(),
                _wf_moderator_node(),
            ],
            edges=[
                _sequential_edge("input-1", "strat-1"),
                _sequential_edge("strat-1", "critic-1"),
                _sequential_edge("critic-1", "mod-1"),
            ],
        )

        wf = converter.convert(layout, name="My Workflow")

        assert len(wf.nodes) == 4
        assert len(wf.edges) == 3
        assert wf.entry_point == "input-1"
        assert wf.name == "My Workflow"

    def test_agent_blueprint_id_from_data(self, repo: BlueprintRepository) -> None:
        """agent_blueprint_id should be resolved from node data."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_strategist_node(blueprint_id="bp-strat"),
            ],
            edges=[_sequential_edge("input-1", "strat-1")],
        )

        wf = converter.convert(layout)

        strat_node = next(n for n in wf.nodes if n.type == "wf-strategist")
        assert strat_node.agent_blueprint_id == "bp-strat"

    def test_agent_blueprint_id_from_asset_edge(self, repo: BlueprintRepository) -> None:
        """agent_blueprint_id should be resolved from connected asset node."""
        converter = CanvasToWorkflowConverter(repo)
        # Node with NO blueprint_id — must resolve from connected asset edge
        strat_no_bp = CanvasLayoutNode(
            id="strat-1",
            type="wf-strategist",
            x=200,
            y=0,
            label="Strategist",
        )
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                strat_no_bp,
                _blueprint_node("bp-asset", blueprint_id="bp-strat"),
            ],
            edges=[
                _sequential_edge("input-1", "strat-1"),
                CanvasLayoutEdge(
                    id="e-bp",
                    source="bp-asset",
                    target="strat-1",
                    type="implements_role",
                ),
            ],
        )

        wf = converter.convert(layout)

        strat_node = next(n for n in wf.nodes if n.type == "wf-strategist")
        assert strat_node.agent_blueprint_id == "bp-strat"

    def test_feedback_edges_preserved(self, repo: BlueprintRepository) -> None:
        """Feedback edges should be preserved in the workflow."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_strategist_node(),
                _wf_moderator_node(),
            ],
            edges=[
                _sequential_edge("input-1", "strat-1"),
                _sequential_edge("strat-1", "mod-1"),
                _feedback_edge("mod-1", "strat-1"),
            ],
        )

        wf = converter.convert(layout)

        feedback_edges = [e for e in wf.edges if e.type == "feedback"]
        assert len(feedback_edges) == 1
        assert feedback_edges[0].source == "mod-1"
        assert feedback_edges[0].target == "strat-1"

    def test_termination_from_moderator_config(self, repo: BlueprintRepository) -> None:
        """Termination conditions should be extracted from moderator node config."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_moderator_node(),
            ],
            edges=[_sequential_edge("input-1", "mod-1")],
        )

        wf = converter.convert(layout)

        max_rounds_tc = next(tc for tc in wf.termination_conditions if tc.type == "max_rounds")
        consensus_tc = next(tc for tc in wf.termination_conditions if tc.type == "consensus_reached")
        assert max_rounds_tc.value == 7
        assert consensus_tc.value == 0.85

    def test_custom_name_and_description(self, repo: BlueprintRepository) -> None:
        """Custom name and description should be set on the workflow."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(nodes=[_wf_input_node()])

        wf = converter.convert(
            layout,
            name="Custom Name",
            description="Custom description",
        )

        assert wf.name == "Custom Name"
        assert wf.description == "Custom description"

    def test_defaults_to_layout_name(self, repo: BlueprintRepository) -> None:
        """Workflow name should default to layout name."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(name="My Layout", nodes=[_wf_input_node()])

        wf = converter.convert(layout)

        assert wf.name == "My Layout"

    def test_asset_edges_excluded(self, repo: BlueprintRepository) -> None:
        """Edges to/from asset nodes should be excluded from the workflow."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_strategist_node(),
                _blueprint_node("bp-1"),
            ],
            edges=[
                _sequential_edge("input-1", "strat-1"),
                CanvasLayoutEdge(
                    id="e-bp",
                    source="bp-1",
                    target="strat-1",
                    type="implements_role",
                ),
            ],
        )

        wf = converter.convert(layout)

        # Only the sequential edge between workflow nodes should be included
        assert len(wf.edges) == 1
        assert wf.edges[0].type == "sequential"

    def test_gate_node_with_condition(self, repo: BlueprintRepository) -> None:
        """Gate node should preserve its condition config."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_gate_node(),
            ],
            edges=[_sequential_edge("input-1", "gate-1")],
        )

        wf = converter.convert(layout)

        gate_node = next(n for n in wf.nodes if n.type == "wf-gate")
        assert gate_node.config.get("condition") == "round >= 3"

    def test_entry_point_prefers_input_node(self, repo: BlueprintRepository) -> None:
        """Entry point should be the wf-input node when present."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_strategist_node(),
                _wf_input_node(),
            ],
            edges=[_sequential_edge("input-1", "strat-1")],
        )

        wf = converter.convert(layout)

        assert wf.entry_point == "input-1"

    def test_entry_point_falls_back_to_no_incoming(self, repo: BlueprintRepository) -> None:
        """Entry point should be the node with no incoming edges if no wf-input."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_strategist_node(node_id="first"),
                _wf_critic_node(node_id="second"),
            ],
            edges=[_sequential_edge("first", "second")],
        )

        wf = converter.convert(layout)

        assert wf.entry_point == "first"

    def test_node_blueprint_map_populated(self, repo: BlueprintRepository) -> None:
        """node_blueprint_map should be populated for backward compatibility."""
        converter = CanvasToWorkflowConverter(repo)
        layout = _make_layout(
            nodes=[
                _wf_input_node(),
                _wf_strategist_node(blueprint_id="bp-strat"),
                _wf_critic_node(blueprint_id="bp-critic"),
            ],
            edges=[
                _sequential_edge("input-1", "strat-1"),
                _sequential_edge("strat-1", "critic-1"),
            ],
        )

        wf = converter.convert(layout)

        assert wf.node_blueprint_map["strat-1"] == "bp-strat"
        assert wf.node_blueprint_map["critic-1"] == "bp-critic"
        assert "input-1" not in wf.node_blueprint_map
