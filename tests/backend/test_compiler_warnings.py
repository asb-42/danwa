"""Tests for Sprint 33 (M1 + M2) — compiler warnings and topo-sort perf.

M1: The WorkflowCompiler used to silently take the first of multiple
non-feedback outgoing edges for a non-gate node, logging only via
``logger.warning``.  Sprint 33 surfaces this to ``CompiledWorkflow.warnings``
so callers can see it programmatically.

M2: The topological sort used ``list.pop(0)`` which is O(n) per
call.  Sprint 33 swaps it for ``collections.deque.popleft()`` (O(1)).
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
    RoleDefinition,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from backend.workflow.workflow_compiler import WorkflowCompiler

# ---------------------------------------------------------------------------
# Module-lookup mocks — see tests/backend/test_decision_mapping.py for
# the rationale.  The P3 refactor moved RoleDefinition / RoleType
# resolution from BlueprintRepository to module_lookups.resolve_*().
# ---------------------------------------------------------------------------


_ROLE_DEFINITIONS: dict[str, RoleDefinition] = {
    "role-1": RoleDefinition(
        id="role-1",
        name="Strategist",
        role="strategist",
        description="Strategic analyst",
        consensus_threshold=0.7,
    ),
}


def _mock_resolve_role_definition(role_def_id: str) -> RoleDefinition | None:
    return _ROLE_DEFINITIONS.get(role_def_id)


@pytest.fixture(autouse=True)
def _patch_module_lookups():
    """Auto-patch module_lookups / compiler / workflow_compiler
    resolve_*  functions with the in-memory test stubs.
    """
    with (
        patch(
            "backend.blueprints.module_lookups.resolve_role_definition",
            side_effect=_mock_resolve_role_definition,
        ),
        patch(
            "backend.workflow.workflow_compiler.resolve_role_definition",
            side_effect=_mock_resolve_role_definition,
        ),
    ):
        yield


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def sample_blueprint_id(repo: BlueprintRepository) -> str:
    """Save LLM profile + blueprint; RoleDefinition is resolved via the
    autouse ``_patch_module_lookups`` fixture's stub.
    """
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
    return blueprint.id


# ---------------------------------------------------------------------------
# M1 — multi-target warning is surfaced
# ---------------------------------------------------------------------------


class TestM1MultiTargetWarning:
    """Verify that a non-gate node with multiple outgoing non-feedback
    edges gets a warning on ``CompiledWorkflow.warnings`` — not just
    a ``logger.warning`` call that callers can easily miss.
    """

    def test_multi_target_emits_warning(self, repo: BlueprintRepository, sample_blueprint_id: str) -> None:
        """Two sequential edges from a non-gate node must produce a warning."""
        workflow = WorkflowDefinition(
            id="wf-multi",
            name="Multi-Target",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
                WorkflowNode(id="wf-sink-a", type="wf-input"),
                WorkflowNode(id="wf-sink-b", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
                # Two outgoing edges from node-s1 — not a gate!
                WorkflowEdge(source="node-s1", target="wf-sink-a", type="sequential"),
                WorkflowEdge(source="node-s1", target="wf-sink-b", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid  # warning, not error
        assert len(result.warnings) == 1
        assert "node-s1" in result.warnings[0]
        # 3.3: The convergence warning replaces the old "non-feedback" message
        # when fan-out targets don't share a common downstream node.
        assert "do NOT converge" in result.warnings[0]
        assert "wf-sink-a" in result.warnings[0]

    def test_single_target_emits_no_warning(self, repo: BlueprintRepository, sample_blueprint_id: str) -> None:
        """A well-formed workflow (single target per node) must NOT
        emit a multi-target warning.
        """
        workflow = WorkflowDefinition(
            id="wf-single",
            name="Single-Target",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        assert result.warnings == []

    def test_warning_includes_node_id_and_target(self, repo: BlueprintRepository, sample_blueprint_id: str) -> None:
        """The warning text must mention both the offending node and
        the target that was actually used (the first one) so the
        workflow author can find the source of the issue.
        """
        workflow = WorkflowDefinition(
            id="wf-multi",
            name="Multi-Target",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="my-strategist",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
                WorkflowNode(id="first-actual-target", type="wf-input"),
                WorkflowNode(id="second-ignored-target", type="wf-input"),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="my-strategist", type="sequential"),
                WorkflowEdge(source="my-strategist", target="first-actual-target", type="sequential"),
                WorkflowEdge(source="my-strategist", target="second-ignored-target", type="sequential"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert any("my-strategist" in w for w in result.warnings)
        assert any("first-actual-target" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# M2 — topological sort uses deque for O(1) popleft
# ---------------------------------------------------------------------------


class TestM2TopologicalSortPerformance:
    """Verify the topological sort is O(V+E), not O(V²) like
    ``list.pop(0)``.
    """

    def test_topo_sort_uses_deque(self) -> None:
        """Static check: the compiler's topological sort must use
        ``collections.deque`` for its working queue.  This is a
        regression guard against someone swapping back to a list.
        """
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "workflow_compiler.py").read_text(encoding="utf-8")
        assert "from collections import defaultdict, deque" in src
        # No more raw list.pop(0) for the topological sort
        assert "queue.pop(0)" not in src

    def test_topo_sort_completes_in_linear_time(self, repo: BlueprintRepository) -> None:
        """A 200-node linear workflow should compile in well under 1s.
        With list.pop(0) the O(n²) sort would still finish in <100ms
        at n=200, but the test serves as a regression guard.
        """
        # 200-node linear chain
        nodes = [WorkflowNode(id=f"n{i}", type="wf-input") for i in range(200)]
        nodes.insert(0, WorkflowNode(id="wf-input", type="wf-input"))
        edges = [
            WorkflowEdge(
                source=f"n{i}",
                target=f"n{i + 1}",
                type="sequential",
            )
            for i in range(199)
        ]
        edges.insert(0, WorkflowEdge(source="wf-input", target="n0", type="sequential"))

        workflow = WorkflowDefinition(
            id="wf-linear",
            name="Linear",
            nodes=nodes,
            edges=edges,
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        start = time.monotonic()
        result = compiler.compile(workflow)
        duration = time.monotonic() - start

        assert result.is_valid
        assert len(result.node_sequence) == 201
        # Linear-time O(V+E) is ~1ms; O(V²) is ~40ms.  Allow generous
        # headroom for slow CI machines.
        assert duration < 1.0, f"Topo sort took {duration:.3f}s for n=200"


# ---------------------------------------------------------------------------
# F-08 — topo-sort warns on decision-edge cycles
# ---------------------------------------------------------------------------


class TestF08TopoSortCycleWarning:
    """Verify that the compiler emits a ``CompiledWorkflow.warnings`` entry
    when Kahn's algorithm cannot reach all nodes due to decision-edge
    cycles (F-08 from the code-review report).
    """

    def test_decision_edge_cycle_emits_warning(
        self,
        repo: BlueprintRepository,
        sample_blueprint_id: str,
    ) -> None:
        """Two nodes with mutual decision edges form a cycle.
        Kahn's algorithm cannot place them; the fallback appends
        them, but a warning must be emitted.
        """
        workflow = WorkflowDefinition(
            id="wf-cycle",
            name="Decision-Cycle",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-moderator",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
                WorkflowNode(
                    id="node-builder",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-moderator", type="sequential"),
                # Mutual decision edges — creates a cycle
                WorkflowEdge(source="node-moderator", target="node-builder", type="decision"),
                WorkflowEdge(source="node-builder", target="node-moderator", type="decision"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid  # warning, not error
        cycle_warnings = [w for w in result.warnings if "decision-edge cycles" in w]
        assert len(cycle_warnings) == 1
        # Both cycle nodes must appear in the warning
        assert "node-moderator" in cycle_warnings[0]
        assert "node-builder" in cycle_warnings[0]

    def test_no_cycle_no_warning(
        self,
        repo: BlueprintRepository,
        sample_blueprint_id: str,
    ) -> None:
        """A workflow with only sequential and feedback edges must NOT
        trigger the decision-edge cycle warning.
        """
        workflow = WorkflowDefinition(
            id="wf-no-cycle",
            name="No-Cycle",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-s1",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
                WorkflowNode(
                    id="node-s2",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-s1", type="sequential"),
                WorkflowEdge(source="node-s1", target="node-s2", type="sequential"),
                # Feedback edge (back-edge) — excluded from topo sort
                WorkflowEdge(source="node-s2", target="node-s1", type="feedback"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        cycle_warnings = [w for w in result.warnings if "decision-edge cycles" in w]
        assert cycle_warnings == []

    def test_self_loop_decision_edge_no_warning(
        self,
        repo: BlueprintRepository,
        sample_blueprint_id: str,
    ) -> None:
        """Self-loop decision edges (Moderator → Moderator on
        ``revision_required``) are skipped in the topo sort, so they
        must NOT cause a cycle warning.
        """
        workflow = WorkflowDefinition(
            id="wf-self-loop",
            name="Self-Loop",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-mod",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
                WorkflowNode(
                    id="node-build",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-mod", type="sequential"),
                WorkflowEdge(source="node-mod", target="node-build", type="decision"),
                # Self-loop on decision edge — must be skipped
                WorkflowEdge(source="node-mod", target="node-mod", type="decision"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        cycle_warnings = [w for w in result.warnings if "decision-edge cycles" in w]
        assert cycle_warnings == []

    def test_all_nodes_present_in_sequence_despite_cycle(
        self,
        repo: BlueprintRepository,
        sample_blueprint_id: str,
    ) -> None:
        """Even when a cycle is detected, all nodes must still appear
        in ``node_sequence`` (via the fallback append).
        """
        workflow = WorkflowDefinition(
            id="wf-cycle-2",
            name="Decision-Cycle-2",
            nodes=[
                WorkflowNode(id="wf-input", type="wf-input"),
                WorkflowNode(
                    id="node-a",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
                WorkflowNode(
                    id="node-b",
                    type="wf-strategist",
                    agent_blueprint_id=sample_blueprint_id,
                ),
            ],
            edges=[
                WorkflowEdge(source="wf-input", target="node-a", type="sequential"),
                WorkflowEdge(source="node-a", target="node-b", type="decision"),
                WorkflowEdge(source="node-b", target="node-a", type="decision"),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        assert len(result.node_sequence) == 3
        assert set(result.node_sequence) == {"wf-input", "node-a", "node-b"}
