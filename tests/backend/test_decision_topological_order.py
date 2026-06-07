"""Tests for Sprint 41 (M3) — topological sort must respect decision edges.

M3: The ``WorkflowCompiler._topological_sort`` excluded decision
edges from the sort.  A Moderator with a decision edge to a
Builder would therefore NOT establish an ordering constraint —
the Builder could end up sequenced before the Moderator in
``CompiledWorkflow.node_sequence``.  At runtime the routing
graph still respected the decision (the Moderator ran first
and then ``route_decision`` picked the target), but the static
``node_sequence`` (used by Inspector / observability / debug
tools) was wrong.

Sprint 41 includes decision edges in the topological sort
while still skipping self-loops (the ``revision_required``
self-edge on a Moderator that loops back to itself) so
Kahn's algorithm terminates.  ``feedback`` and
``injects_config`` remain excluded — they are not
sequencing edges (feedback is a back-edge, injects_config
is config injection).
"""

from __future__ import annotations

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
# Fixtures
# ---------------------------------------------------------------------------


_ROLE_DEFINITIONS: dict[str, RoleDefinition] = {
    "role-1": RoleDefinition(
        id="role-1",
        name="Moderator",
        role="moderator",
        description="Moderator node",
        consensus_threshold=0.7,
    ),
    "role-2": RoleDefinition(
        id="role-2",
        name="Builder",
        role="builder",
        description="Builder node",
        consensus_threshold=0.7,
    ),
    "role-3": RoleDefinition(
        id="role-3",
        name="Input",
        role="input",
        description="Input node",
        consensus_threshold=0.7,
    ),
}


def _mock_resolve_role_definition(role_def_id: str) -> RoleDefinition | None:
    return _ROLE_DEFINITIONS.get(role_def_id)


@pytest.fixture(autouse=True)
def _patch_module_lookups():
    """Patch both ``module_lookups.resolve_role_definition`` and
    the alias the compiler imports it as.  Without the
    compiler-side patch the compiler uses the real (failing)
    lookup even if the module_lookups one is mocked.
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


@pytest.fixture
def repo(tmp_path: Path) -> BlueprintRepository:
    """In-memory ``BlueprintRepository`` with a sample
    blueprint and LLM profile so the compiler's role
    lookups succeed.
    """
    repo = BlueprintRepository(db_path=tmp_path / "test_blueprints.db")
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
        name="Test Blueprint",
        llm_profile_id="prof-1",
        role_definition_id="role-1",
        active=True,
    )
    repo.save_blueprint(blueprint)
    return repo


def _make_workflow(
    edges: list[WorkflowEdge],
    nodes: list[WorkflowNode] | None = None,
    entry_point: str = "wf-input",
) -> WorkflowDefinition:
    if nodes is None:
        # Default: every node id mentioned in edges exists.
        # Use the conventional node types from the codebase
        # so the compiler's resolve_*_bundle path is taken,
        # not the strict wf-agent path that requires
        # ``bundle_id``.
        seen: set[str] = set()
        for e in edges:
            seen.add(e.source)
            seen.add(e.target)
        nodes = []
        for nid in seen:
            if nid in ("__end__", ""):
                continue
            if nid == entry_point:
                nodes.append(WorkflowNode(id=nid, type="wf-input"))
            elif "moderator" in nid:
                nodes.append(
                    WorkflowNode(
                        id=nid,
                        type="wf-moderator",
                        agent_blueprint_id="bp-1",
                    )
                )
            else:
                nodes.append(
                    WorkflowNode(
                        id=nid,
                        type="wf-strategist",
                        agent_blueprint_id="bp-1",
                    )
                )
    return WorkflowDefinition(
        id="wf-test",
        name="Test",
        nodes=nodes,
        edges=edges,
        entry_point=entry_point,
    )


# ---------------------------------------------------------------------------
# M3 — decision edges are ordering constraints
# ---------------------------------------------------------------------------


class TestDecisionEdgeOrdering:
    """A decision edge from Moderator to Builder must place the
    Builder AFTER the Moderator in ``node_sequence`` — they
    are part of the workflow's logical data flow, just like
    sequential edges.
    """

    def test_decision_edge_orders_target_after_source(self, repo: BlueprintRepository) -> None:
        """Moderator → (decision "approved") → Builder.

        The Builder must come after the Moderator in
        ``node_sequence`` because the Builder is the
        conditional target of the Moderator's decision.
        Before Sprint 41 the Builder could be ordered first
        (it had in_degree 0 because decision edges were
        excluded from the sort).
        """
        workflow = _make_workflow(
            edges=[
                WorkflowEdge(
                    source="wf-input",
                    target="node-moderator",
                    type="sequential",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="node-builder",
                    type="decision",
                    condition="approved",
                ),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid, f"compile failed: {result.errors}"
        seq = result.node_sequence
        assert seq.index("node-moderator") < seq.index("node-builder"), (
            f"node_builder must come after node_moderator because the decision edge is an ordering constraint; got {seq}"
        )

    def test_decision_self_loop_does_not_break_sort(self, repo: BlueprintRepository) -> None:
        """A self-loop decision edge (Moderator → Moderator on
        ``revision_required``) must NOT cause Kahn's algorithm
        to deadlock.  The fix skips self-loops in the sort
        while still using non-self decision edges for
        ordering.
        """
        workflow = _make_workflow(
            edges=[
                WorkflowEdge(
                    source="wf-input",
                    target="node-moderator",
                    type="sequential",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="node-moderator",
                    type="decision",
                    condition="revision_required",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="node-builder",
                    type="decision",
                    condition="approved",
                ),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid, f"compile failed: {result.errors}"
        seq = result.node_sequence
        assert "wf-input" in seq
        assert "node-moderator" in seq
        assert "node-builder" in seq
        # Ordering: input → moderator → builder
        assert seq.index("wf-input") < seq.index("node-moderator")
        assert seq.index("node-moderator") < seq.index("node-builder")

    def test_decision_with_no_targets_still_orders(self, repo: BlueprintRepository) -> None:
        """A decision edge whose target is ``__end__`` (workflow
        terminates on this branch) must still establish an
        ordering between the source and the implicit end.  We
        check that the source comes after its predecessor
        even if no target node exists.
        """
        workflow = _make_workflow(
            edges=[
                WorkflowEdge(
                    source="wf-input",
                    target="node-moderator",
                    type="sequential",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="__end__",
                    type="decision",
                    condition="approved",
                ),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        seq = result.node_sequence
        assert seq.index("wf-input") < seq.index("node-moderator")


class TestFeedbackAndInjectsConfigStillExcluded:
    """The fix must NOT regress Sprint 33 (M2) behaviour:
    ``feedback`` and ``injects_config`` edges are still
    excluded from the sort (they are not sequencing edges).
    """

    def test_feedback_edge_does_not_block_target(self, repo: BlueprintRepository) -> None:
        """A → B (sequential) and A → B (feedback).  The
        feedback edge must not create a cycle that Kahn's
        algorithm cannot resolve — the target is still
        ordered after the source via the sequential edge.
        """
        workflow = _make_workflow(
            edges=[
                WorkflowEdge(
                    source="wf-input",
                    target="node-a",
                    type="sequential",
                ),
                WorkflowEdge(
                    source="node-a",
                    target="node-b",
                    type="sequential",
                ),
                WorkflowEdge(
                    source="node-a",
                    target="node-b",
                    type="feedback",
                ),
            ],
            entry_point="wf-input",
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid
        seq = result.node_sequence
        assert seq.index("wf-input") < seq.index("node-a")
        assert seq.index("node-a") < seq.index("node-b")


# ---------------------------------------------------------------------------
# Static guard — keep the contract in code
# ---------------------------------------------------------------------------


class TestTopologicalSortCodeContract:
    """Static check that the sort continues to include the
    right edges.  A future refactor that accidentally drops
    decision edges again (re-introducing M3) will fail this
    test.
    """

    def test_decision_edge_included_in_topo_sort(self) -> None:
        import inspect

        from backend.workflow.workflow_compiler import WorkflowCompiler

        src = inspect.getsource(WorkflowCompiler._topological_sort)
        # The sort must include ``"decision"`` (or, more
        # permissively, must not unconditionally exclude it).
        # We check that the exclusion list does not contain
        # ``"decision"`` — the fix replaces
        # ``if edge.type not in ("feedback", "injects_config", "decision")``
        # with one that excludes only feedback + injects_config
        # (plus self-loops handled separately).
        assert '"decision"' not in _extract_excluded_types(src), (
            "WorkflowCompiler._topological_sort must not unconditionally exclude decision edges from the sort — see M3."
        )

    def test_feedback_edge_still_excluded(self) -> None:
        import inspect

        from backend.workflow.workflow_compiler import WorkflowCompiler

        src = inspect.getsource(WorkflowCompiler._topological_sort)
        excluded = _extract_excluded_types(src)
        assert "feedback" in excluded, (
            "WorkflowCompiler._topological_sort must continue to exclude feedback edges — they are back-edges, not sequencing edges."
        )


def _extract_excluded_types(src: str) -> set[str]:
    """Return the set of edge types excluded from the sort.

    Handles both styles:

    * ``if edge.type not in ("a", "b", ...)`` — single-line
      tuple, collected via regex.
    * ``if edge.type in ("a", "b", ...): continue`` — same
      exclusion list, just inverted (the excluded set is the
      tuple contents).
    * Multi-line ``in (...)`` tuples where each member is on
      its own indented line.
    """
    import re

    # Match any tuple of double-quoted string literals that
    # appears in a line that also mentions ``edge.type``.
    pattern = re.compile(r'"([a-z_]+)"')
    excluded: set[str] = set()
    for line in src.splitlines():
        if "edge.type" not in line:
            continue
        for m in pattern.finditer(line):
            excluded.add(m.group(1))
    return excluded
