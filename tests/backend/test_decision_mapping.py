"""Tests for Sprint 32 (C3) — robust decision-edge mapping.

Verifies that:
* ``route_decision`` returns the right mapping key for known and
  custom verdict values via its ``verdict_map`` parameter.
* ``WorkflowCompiler`` builds the ``verdict_map`` from the actual
  decision edges, so a template designer renaming a condition (e.g.
  ``"approved"`` → ``"accept"``) routes correctly instead of falling
  back to the silent ``__complete__`` placeholder.
* The deadlock / max_rounds exits are preserved.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from backend.blueprints.models import AgentBlueprint, BlueprintLLMProfile, RoleDefinition
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from backend.workflow.workflow_compiler import WorkflowCompiler
from backend.workflow.workflow_routers import route_decision, route_feedback

# ---------------------------------------------------------------------------
# Module-lookup mocks — main's P3 refactor moved RoleDefinition / RoleType
# resolution from BlueprintRepository to module_lookups.resolve_*().  These
# test stubs replace the real module lookups with in-memory dicts.
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

    The P3 refactor removed ``BlueprintRepository.save_role_definition``
    and friends, so the compiler now reads role definitions via
    ``backend.blueprints.module_lookups.resolve_role_definition``.
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


# ---------------------------------------------------------------------------
# route_decision — verdict_map parameter
# ---------------------------------------------------------------------------


class TestRouteDecisionVerdictMap:
    """Test the route_decision factory with explicit verdict_map."""

    def test_default_verdict_map_preserves_legacy_keys(self) -> None:
        """Without verdict_map, the router returns the historical
        ``"approved"`` / ``"return_to_builder"`` keys for backward
        compatibility with pre-Sprint-32 templates.
        """
        router = route_decision(max_rounds=5)

        # Verdict "approved" → key "approved"
        state = {"consensus_result": {"verdict": "approved"}, "current_round": 1, "draft_version": 1}
        assert router(state) == "approved"

        # Verdict "revision_required" → key "return_to_builder"
        state = {"consensus_result": {"verdict": "revision_required"}, "current_round": 1, "draft_version": 1}
        assert router(state) == "return_to_builder"

    def test_custom_verdict_map_uses_custom_keys(self) -> None:
        """A custom verdict_map lets the template designer choose
        their own condition names.  The router returns the mapped
        key, not a hardcoded literal.
        """
        router = route_decision(
            max_rounds=5,
            verdict_map={"accept": "accept", "revise": "revise"},
        )

        state = {"consensus_result": {"verdict": "accept"}, "current_round": 1, "draft_version": 1}
        assert router(state) == "accept"

        state = {"consensus_result": {"verdict": "revise"}, "current_round": 1, "draft_version": 1}
        assert router(state) == "revise"

    def test_unmapped_verdict_falls_back_to_first_non_approved(self) -> None:
        """If the verdict is not in verdict_map, the router returns
        the fallback key (first non-"approved" entry, or
        ``"return_to_builder"`` if only "approved" is mapped).
        """
        router = route_decision(
            max_rounds=5,
            verdict_map={"accept": "accept", "revise": "revise"},
        )

        # Verdict "foo" not in map → fallback to first non-approved
        # entry in iteration order — for this map that's "accept".
        state = {"consensus_result": {"verdict": "foo"}, "current_round": 1, "draft_version": 1}
        assert router(state) == "accept"


class TestRouteDecisionExtension:
    """Test the route_decision factory's respect for ``extension_granted``.

    The ``Moderator`` node sets ``state["extension_granted"] = True`` when the
    user grants an extension during the wait loop in
    ``backend/workflow/nodes/moderator_nodes.py``.  The ``route_feedback``
    router (used for the feedback-loop edge) already honours this flag and
    allows up to ``max_rounds + 2`` rounds.  ``route_decision`` (used for the
    decision edge in Transactional Drafting) must do the same, otherwise the
    extension grant is silently discarded and the workflow terminates with
    ``"construction_deadlock"`` even though the user explicitly asked for more
    rounds.

    See audit M11 in ``docs/blueprint_workflow_audit.md``.
    """

    def test_extension_granted_allows_extra_rounds(self) -> None:
        """``extension_granted=True`` in the extension zone (max_rounds+1)
        routes to the verdict-driven target, NOT construction_deadlock.
        """
        router = route_decision(max_rounds=5)

        state = {
            "consensus_result": {"verdict": "revision_required"},
            "current_round": 6,  # max_rounds + 1
            "draft_version": 1,
            "enable_extra_rounds": True,
            "extension_granted": True,
        }
        assert router(state) == "return_to_builder"

    def test_extension_granted_allows_second_extra_round(self) -> None:
        """``extension_granted=True`` in the extension zone (max_rounds+2)
        also routes to the verdict-driven target.
        """
        router = route_decision(max_rounds=5)

        state = {
            "consensus_result": {"verdict": "revision_required"},
            "current_round": 7,  # max_rounds + 2
            "draft_version": 1,
            "enable_extra_rounds": True,
            "extension_granted": True,
        }
        assert router(state) == "return_to_builder"

    def test_extension_granted_approved_verdict(self) -> None:
        """When extension is granted AND consensus reaches threshold
        (verdict="approved"), the router returns "approved" — the
        extension does not override a legitimate consensus.
        """
        router = route_decision(max_rounds=5)

        state = {
            "consensus_result": {"verdict": "approved"},
            "current_round": 6,
            "draft_version": 1,
            "enable_extra_rounds": True,
            "extension_granted": True,
        }
        assert router(state) == "approved"

    def test_no_extension_granted_still_deadlocks(self) -> None:
        """Without ``extension_granted=True`` (or with it set to False),
        the router still returns construction_deadlock past max_rounds.
        """
        router = route_decision(max_rounds=5)

        # extension_granted not set
        state = {
            "consensus_result": {"verdict": "revision_required"},
            "current_round": 6,
            "draft_version": 1,
            "enable_extra_rounds": True,
        }
        assert router(state) == "construction_deadlock"

        # extension_granted explicitly False
        state["extension_granted"] = False
        assert router(state) == "construction_deadlock"

    def test_extension_granted_beyond_zone_still_deadlocks(self) -> None:
        """Even with ``extension_granted=True``, rounds beyond max_rounds+2
        deadlock — the user only allowed 2 extra rounds.
        """
        router = route_decision(max_rounds=5)

        state = {
            "consensus_result": {"verdict": "revision_required"},
            "current_round": 8,  # max_rounds + 3 — beyond extension zone
            "draft_version": 1,
            "enable_extra_rounds": True,
            "extension_granted": True,
        }
        assert router(state) == "construction_deadlock"

    def test_enable_extra_rounds_false_ignores_extension(self) -> None:
        """If ``enable_extra_rounds`` is False, the extension_granted flag
        is irrelevant — the workflow terminates at max_rounds.
        """
        router = route_decision(max_rounds=5)

        state = {
            "consensus_result": {"verdict": "revision_required"},
            "current_round": 6,
            "draft_version": 1,
            "enable_extra_rounds": False,
            "extension_granted": True,
        }
        assert router(state) == "construction_deadlock"

    def test_construction_deadlock_takes_precedence(self) -> None:
        """Max-rounds / max-draft-versions check returns
        ``"construction_deadlock"`` regardless of verdict_map — the
        deadlock exit is always available.
        """
        router = route_decision(
            max_rounds=5,
            verdict_map={"accept": "accept", "revise": "revise"},
        )

        # Round exceeds max → deadlock
        state = {
            "consensus_result": {"verdict": "accept"},
            "current_round": 100,
            "draft_version": 1,
        }
        assert router(state) == "construction_deadlock"

    def test_draft_version_deadlock_takes_precedence(self) -> None:
        """Draft-version deadlock also returns ``"construction_deadlock"``."""
        router = route_decision(max_rounds=10, verdict_map={"accept": "accept"})

        state = {
            "consensus_result": {"verdict": "accept"},
            "current_round": 1,
            "draft_version": 10,  # max_draft_versions defaults to 5
        }
        assert router(state) == "construction_deadlock"

    def test_missing_verdict_defaults_to_revision(self) -> None:
        """If ``consensus_result`` is missing, the router treats the
        verdict as ``"revision_required"`` (backward-compat).
        """
        router = route_decision(max_rounds=5)

        # Empty consensus_result → revision_required → return_to_builder
        state = {"consensus_result": {}, "current_round": 1, "draft_version": 1}
        assert router(state) == "return_to_builder"

        # Missing consensus_result entirely → also revision_required
        state = {"current_round": 1, "draft_version": 1}
        assert router(state) == "return_to_builder"


# ---------------------------------------------------------------------------
# WorkflowCompiler — verdict_map from decision edges
# ---------------------------------------------------------------------------


def _make_decision_workflow(
    sample_blueprint_id: str,
    decision_edges: list[WorkflowEdge],
) -> WorkflowDefinition:
    """Build a minimal workflow with a Moderator node and the given
    decision edges.
    """
    return WorkflowDefinition(
        id="wf-decision",
        name="Decision Test",
        nodes=[
            WorkflowNode(id="wf-input", type="wf-input"),
            WorkflowNode(
                id="node-moderator",
                type="wf-moderator",
                agent_blueprint_id=sample_blueprint_id,
            ),
        ],
        edges=[
            WorkflowEdge(source="wf-input", target="node-moderator", type="sequential"),
            *decision_edges,
        ],
        entry_point="wf-input",
        termination_conditions=[TerminationCondition(type="max_rounds", value=5)],
    )


class TestCompilerDecisionMapping:
    """Test the C3 fix at the compiler level."""

    @pytest.fixture()
    def repo(self, tmp_path: Path) -> BlueprintRepository:
        """Fresh BlueprintRepository with temp database."""
        return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")

    @pytest.fixture()
    def sample_blueprint_id(self, repo: BlueprintRepository) -> str:
        """Create a sample blueprint and return its id.

        The RoleDefinition itself is no longer saved to the
        BlueprintRepository (P3 refactor) — the compiler resolves it
        via ``module_lookups.resolve_role_definition`` which is
        patched by the autouse ``_patch_module_lookups`` fixture to
        return from the ``_ROLE_DEFINITIONS`` dict.
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

    def test_standard_conditions_compile(self, repo: BlueprintRepository, sample_blueprint_id: str) -> None:
        """Templates with the standard ``"approved"`` /
        ``"revision_required"`` conditions compile to a graph with
        the legacy mapping (``"approved"``, ``"return_to_builder"``,
        ``"construction_deadlock"`` keys).
        """
        workflow = _make_decision_workflow(
            sample_blueprint_id,
            decision_edges=[
                WorkflowEdge(
                    source="node-moderator",
                    target="__end__",
                    type="decision",
                    condition="approved",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="node-moderator",
                    type="decision",
                    condition="revision_required",
                ),
            ],
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid, f"compile failed: {result.errors}"

    def test_custom_condition_compiles(self, repo: BlueprintRepository, sample_blueprint_id: str) -> None:
        """Templates with custom condition names (``"accept"``,
        ``"revise"``) compile successfully — no silent fallback to
        ``__complete__``.
        """
        workflow = _make_decision_workflow(
            sample_blueprint_id,
            decision_edges=[
                WorkflowEdge(
                    source="node-moderator",
                    target="__end__",
                    type="decision",
                    condition="accept",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="node-moderator",
                    type="decision",
                    condition="revise",
                ),
            ],
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid, f"compile failed: {result.errors}"

    def test_mixed_standard_and_custom_conditions(self, repo: BlueprintRepository, sample_blueprint_id: str) -> None:
        """A template can mix standard and custom conditions — e.g.
        ``"approved"`` for the happy path and a custom ``"abort"``
        for a domain-specific exit.
        """
        workflow = _make_decision_workflow(
            sample_blueprint_id,
            decision_edges=[
                WorkflowEdge(
                    source="node-moderator",
                    target="__end__",
                    type="decision",
                    condition="approved",
                ),
                WorkflowEdge(
                    source="node-moderator",
                    target="__end__",
                    type="decision",
                    condition="abort",
                ),
            ],
        )
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(workflow)

        assert result.is_valid, f"compile failed: {result.errors}"


# ---------------------------------------------------------------------------
# Static guard — compiler must not reference removed legacy keys
# ---------------------------------------------------------------------------


class TestCompilerSourceGuards:
    """Static checks that the refactored compiler no longer relies on
    the silent-fallback ``__complete__`` placeholder.
    """

    def test_compiler_uses_verdict_map_parameter(self) -> None:
        """The compiler must call ``route_decision(... verdict_map=...)`` —
        the C3 fix — not the old positional call.
        """
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "workflow_compiler.py").read_text(encoding="utf-8")
        assert "verdict_map=" in src
        assert "route_decision(decision_max_rounds, verdict_map=verdict_map)" in src

    def test_compiler_no_longer_uses_complete_fallback(self) -> None:
        """The compiler must not have any
        ``targets.get("approved", "__complete__")`` style fallback —
        the silent-failure that was the C3 bug.
        """
        from pathlib import Path

        src = (Path(__file__).resolve().parents[2] / "backend" / "workflow" / "workflow_compiler.py").read_text(encoding="utf-8")
        # The bug was an inline fallback literal — the new code uses
        # END as the explicit fallback and warns loudly when no
        # matching edge is found.  Search for the exact pattern
        # (not the string "__complete__" in isolation, which appears
        # in unrelated docstrings).
        assert 'targets.get("approved", "__complete__")' not in src
        assert 'targets.get("revision_required", END)' not in src


# ---------------------------------------------------------------------------
# F-10 — route_feedback max_rounds=0 edge case
# ---------------------------------------------------------------------------


class TestRouteFeedbackMaxRoundsZero:
    """Verify that ``route_feedback`` clamps ``max_rounds`` to at least 1
    so that the extension zone (max_rounds + 2) doesn't allow regular
    rounds through when ``max_rounds=0`` (F-10 from the code-review report).
    """

    def test_max_rounds_zero_treats_as_one(self) -> None:
        """With ``max_rounds=0`` and ``current_round=1``, the router
        should return ``"exit"`` (round 1 > clamped max of 1 is False,
        but the clamp makes effective=1 so round 1 is normal → continue).
        Actually: round 1 <= 1 → continue.  Round 2 > 1, and extension
        zone covers 2-3.  Without extension_granted → exit.
        """
        router = route_feedback(max_rounds=0)

        # Round 1: clamped to effective=1, so 1 <= 1 → continue
        state = {"current_round": 1, "enable_extra_rounds": True, "extension_granted": True}
        assert router(state) == "continue"

        # Round 2: 2 > 1, extension zone 2 <= 1+2=3, extension_granted → continue
        state["current_round"] = 2
        assert router(state) == "continue"

        # Round 3: still in extension zone 3 <= 3, granted → continue
        state["current_round"] = 3
        assert router(state) == "continue"

        # Round 4: beyond extension zone 4 > 3 → exit
        state["current_round"] = 4
        assert router(state) == "exit"

    def test_max_rounds_zero_without_extension(self) -> None:
        """With ``max_rounds=0`` (clamped to 1) and no extension grant,
        round 1 is normal (continue), round 2+ exits.
        """
        router = route_feedback(max_rounds=0)

        state = {"current_round": 1, "enable_extra_rounds": False}
        assert router(state) == "continue"

        state["current_round"] = 2
        assert router(state) == "exit"

    def test_normal_max_rounds_still_works(self) -> None:
        """Ensure the clamp doesn't break normal ``max_rounds=5``."""
        router = route_feedback(max_rounds=5)

        state = {"current_round": 1}
        assert router(state) == "continue"

        state["current_round"] = 5
        assert router(state) == "continue"

        # Round 6: past max, no extension → exit
        state["current_round"] = 6
        assert router(state) == "exit"

        # Round 6 with extension granted → continue
        state["enable_extra_rounds"] = True
        state["extension_granted"] = True
        assert router(state) == "continue"

        # Round 8: beyond max+2=7 → exit
        state["current_round"] = 8
        assert router(state) == "exit"
