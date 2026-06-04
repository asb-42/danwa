"""Tests for safe_eval and named conditions (sprint 28)."""

from __future__ import annotations

import pytest

from backend.workflow.safe_eval import (
    SafeEvalError,
    evaluate_condition,
    is_named_condition,
    safe_eval,
)

# ---------------------------------------------------------------------------
# safe_eval — allows typical expression patterns
# ---------------------------------------------------------------------------


class TestSafeEvalAllows:
    """safe_eval should evaluate the expressions used by real gate conditions."""

    def test_state_subscript(self):
        assert safe_eval("state['x']", {"x": 42}) == 42

    def test_state_get_via_subscript_then_compare(self):
        result = safe_eval("state['x'] >= 3", {"x": 5})
        assert result is True

    def test_bare_name_lookup_against_state(self):
        """``current_round`` resolves to state['current_round'] without
        requiring the explicit subscript syntax.  This is the more
        common authoring pattern and matches the comment in
        ``backend/blueprints/workflow_models.py:246``."""
        result = safe_eval("current_round >= 1", {"current_round": 3})
        assert result is True

    def test_bare_name_lookup_compares_correctly(self):
        assert safe_eval("current_round >= 10", {"current_round": 3}) is False
        assert safe_eval("current_round == 3", {"current_round": 3}) is True

    def test_state_get_via_subscript_then_compare_false(self):
        result = safe_eval("state['x'] >= 10", {"x": 5})
        assert result is False

    def test_nested_subscript(self):
        state = {"a": {"b": {"c": "found"}}}
        assert safe_eval("state['a']['b']['c']", state) == "found"

    def test_arithmetic(self):
        assert safe_eval("1 + 2 * 3", {}) == 7
        assert safe_eval("10 - 4", {}) == 6
        assert safe_eval("7 // 2", {}) == 3
        assert safe_eval("7 % 2", {}) == 1
        assert safe_eval("2 ** 8", {}) == 256

    def test_boolean(self):
        assert safe_eval("True and False", {}) is False
        assert safe_eval("True or False", {}) is True
        assert safe_eval("not True", {}) is False
        assert safe_eval("True and (False or True)", {}) is True

    def test_comparisons(self):
        assert safe_eval("1 < 2", {}) is True
        assert safe_eval("1 == 1", {}) is True
        assert safe_eval("1 != 2", {}) is True
        assert safe_eval("'a' in ['a', 'b']", {}) is True
        assert safe_eval("'a' not in ['a', 'b']", {}) is False
        assert safe_eval("None is None", {}) is True
        assert safe_eval("True is not False", {}) is True

    def test_missing_state_key_returns_keyerror(self):
        """``state['missing']`` propagates the underlying KeyError. Callers should
        use ``state.get('x')`` — but wait, that requires ``.get`` which is
        not in the safe dialect.  Instead, we surface the KeyError so the
        caller can log it and skip the condition."""
        with pytest.raises(KeyError):
            safe_eval("state['missing']", {})

    def test_empty_state_subscript_zero(self):
        assert safe_eval("state['count']", {"count": 0}) == 0

    def test_tuple_and_list_literals(self):
        assert safe_eval("(1, 2, 3)", {}) == (1, 2, 3)
        assert safe_eval("[1, 2, 3]", {}) == [1, 2, 3]


# ---------------------------------------------------------------------------
# safe_eval — rejects dangerous constructs
# ---------------------------------------------------------------------------


class TestSafeEvalRejects:
    """safe_eval must reject every construct that can lead to code execution."""

    @pytest.mark.parametrize(
        "expression",
        [
            "__import__('os').system('echo pwned')",
            "open('/etc/passwd')",
            "eval('1+1')",
            "exec('print(1)')",
            "lambda: 1",
            "[x for x in range(10)]",
            "{x: x for x in range(10)}",
            "f'x'",
            "{1, 2, 3}",  # Set literal — not in whitelist
            "del state",
            "state['x'] = 1",
            "assert True",
            "(1).__class__.__base__.__subclasses__()",
            "[].__class__",
            "type(state)",
        ],
    )
    def test_dangerous_expression_rejected(self, expression: str):
        with pytest.raises(SafeEvalError):
            safe_eval(expression, {"x": 1})

    def test_function_call_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("len(state)", {"x": 1})

    def test_method_call_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("state.get('x')", {"x": 1})

    def test_attribute_access_rejected(self):
        """Attribute access on state is not allowed — use ``state['key']`` instead."""
        with pytest.raises(SafeEvalError):
            safe_eval("state.attr", {"attr": 1})

    def test_unknown_name_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("os", {"x": 1})

    def test_bare_name_not_in_state_rejected(self):
        """Names that are neither reserved (state/True/False/None) nor a
        state key must be rejected — otherwise a typo silently resolves
        to ``None`` and the condition always evaluates falsy."""
        with pytest.raises(SafeEvalError):
            safe_eval("not_a_state_key >= 1", {"x": 1})

    def test_empty_expression_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("", {})

    def test_whitespace_only_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("   \n\t  ", {})

    def test_non_string_input_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval(123, {})  # type: ignore[arg-type]

    def test_syntax_error_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("1 +", {})

    def test_nested_dangerous_call_rejected(self):
        with pytest.raises(SafeEvalError):
            safe_eval("state if open('/tmp/x') else state", {})


# ---------------------------------------------------------------------------
# Named conditions
# ---------------------------------------------------------------------------


class TestNamedConditions:
    """The NAMED_CONDITIONS registry should match the strings used in templates."""

    def test_consensus_reached_true(self):
        state = {"consensus_result": {"verdict": "approved"}}
        assert evaluate_condition("consensus_reached", state) is True

    def test_consensus_reached_false(self):
        state = {"consensus_result": {"verdict": "revision_required"}}
        assert evaluate_condition("consensus_reached", state) is False

    def test_consensus_reached_missing_state(self):
        """Missing consensus_result → not reached."""
        assert evaluate_condition("consensus_reached", {}) is False

    def test_max_rounds_reached_true(self):
        state = {"current_round": 6, "max_rounds": 5}
        assert evaluate_condition("max_rounds_reached", state) is True

    def test_max_rounds_reached_false(self):
        state = {"current_round": 3, "max_rounds": 5}
        assert evaluate_condition("max_rounds_reached", state) is False

    def test_max_rounds_reached_no_max_default(self):
        """If max_rounds missing, fall back to default 5."""
        state = {"current_round": 6}
        assert evaluate_condition("max_rounds_reached", state) is True

    def test_extension_granted_true(self):
        state = {"extension_granted": True}
        assert evaluate_condition("extension_granted", state) is True

    def test_extension_granted_false(self):
        state = {"extension_granted": False}
        assert evaluate_condition("extension_granted", state) is False

    def test_draft_deadlock_default_threshold(self):
        """draft_deadlock at draft_version >= 5 (default) is True."""
        assert evaluate_condition("draft_deadlock", {"draft_version": 5}) is True
        assert evaluate_condition("draft_deadlock", {"draft_version": 4}) is False

    def test_draft_deadlock_with_termination_condition(self):
        """draft_deadlock reads max_draft_versions from termination_conditions."""
        state = {
            "draft_version": 7,
            "termination_conditions": [{"type": "max_draft_versions", "value": 8}],
        }
        assert evaluate_condition("draft_deadlock", state) is False
        state["draft_version"] = 8
        assert evaluate_condition("draft_deadlock", state) is True

    def test_is_paused_true(self):
        assert evaluate_condition("is_paused", {"is_paused": True}) is True

    def test_is_paused_default_false(self):
        assert evaluate_condition("is_paused", {}) is False

    def test_approved_named(self):
        state = {"consensus_result": {"verdict": "approved"}}
        assert evaluate_condition("approved", state) is True

    def test_revision_required_named(self):
        state = {"consensus_result": {"verdict": "revision_required"}}
        assert evaluate_condition("revision_required", state) is True

    def test_construction_deadlock_named(self):
        state = {"consensus_result": {"verdict": "construction_deadlock"}}
        assert evaluate_condition("construction_deadlock", state) is True

    def test_true_named(self):
        assert evaluate_condition("True", {}) is True

    def test_false_named(self):
        assert evaluate_condition("False", {}) is False

    def test_named_takes_precedence_over_safe_eval(self):
        """If a name happens to also be a valid Python expression, the
        named registry wins — that way ``True`` is a name, not the
        Python constant ``True`` (which would happen to evaluate the
        same way, but other names may differ from Python)."""
        # 'consensus_reached' is NOT valid Python — only safe_eval would
        # raise SafeEvalError.  Named lookup should succeed.
        assert evaluate_condition("consensus_reached", {"consensus_result": {"verdict": "approved"}}) is True

    def test_named_condition_registry_is_complete(self):
        """Every name used in the bundled workflow templates must be in the registry."""
        for name in [
            "consensus_reached",
            "max_rounds_reached",
            "extension_granted",
            "draft_deadlock",
            "is_paused",
            "approved",
            "revision_required",
            "construction_deadlock",
            "True",
            "False",
        ]:
            assert is_named_condition(name), f"missing named condition: {name!r}"

    def test_named_condition_works_with_extra_whitespace(self):
        assert evaluate_condition("  consensus_reached  ", {"consensus_result": {"verdict": "approved"}}) is True

    def test_empty_string_returns_false(self):
        """Empty / whitespace conditions are not errors — they are simply false."""
        assert evaluate_condition("", {}) is False
        assert evaluate_condition("   ", {}) is False

    def test_unknown_name_falls_through_to_safe_eval(self):
        """An unknown name is not a SafeEvalError — safe_eval will reject it
        if it's not a valid safe expression.  The point is that 'unknown'
        does not silently mean 'true'."""
        with pytest.raises(SafeEvalError):
            evaluate_condition("not_a_real_name", {})


# ---------------------------------------------------------------------------
# route_decision respects max_draft_versions termination condition
# ---------------------------------------------------------------------------


class TestRouteDecisionMaxDraftVersions:
    """The magic number 5 in route_decision must be overridable via
    termination_conditions."""

    def test_default_threshold_is_5(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        # No termination_conditions → default 5
        assert router({"current_round": 1, "draft_version": 5, "consensus_result": {"verdict": "approved"}}) == "construction_deadlock"

    def test_default_threshold_allows_4(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        # draft_version=4 with default 5 → return_to_builder if not approved
        assert router({"current_round": 1, "draft_version": 4, "consensus_result": {"verdict": "revision_required"}}) == "return_to_builder"

    def test_custom_max_draft_versions(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = {
            "current_round": 1,
            "draft_version": 3,
            "consensus_result": {"verdict": "revision_required"},
            "termination_conditions": [{"type": "max_draft_versions", "value": 3}],
        }
        assert router(state) == "construction_deadlock"

    def test_custom_max_draft_versions_lets_lower_pass(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = {
            "current_round": 1,
            "draft_version": 2,
            "consensus_result": {"verdict": "revision_required"},
            "termination_conditions": [{"type": "max_draft_versions", "value": 3}],
        }
        assert router(state) == "return_to_builder"

    def test_termination_condition_value_zero_uses_default(self):
        """A non-positive value is ignored so the default kicks in."""
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = {
            "current_round": 1,
            "draft_version": 4,
            "consensus_result": {"verdict": "revision_required"},
            "termination_conditions": [{"type": "max_draft_versions", "value": 0}],
        }
        # Default is 5, so draft_version=4 is allowed
        assert router(state) == "return_to_builder"

    def test_max_rounds_still_takes_precedence(self):
        """The max_rounds check is independent of max_draft_versions."""
        from backend.workflow.workflow_routers import route_decision

        router = route_decision(max_rounds=3)
        state = {
            "current_round": 5,
            "draft_version": 1,
            "consensus_result": {"verdict": "revision_required"},
            "max_rounds": 3,
        }
        assert router(state) == "construction_deadlock"

    def test_approved_verdict_breaks_out(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = {
            "current_round": 1,
            "draft_version": 1,
            "consensus_result": {"verdict": "approved", "reality_score": 0.8},
        }
        assert router(state) == "approved"


# ---------------------------------------------------------------------------
# Moderator structural reject — prevent LLM from gaming reality_score
# ---------------------------------------------------------------------------


class TestModeratorStructuralReject:
    """Verify the Moderator's structural check on pragmatist_output.evaluations."""

    def test_rejected_evaluation_overrides_high_reality_score(self):
        """Even if reality_score=0.9, a single verdict=reject vetoes approval."""
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        ev = {"verdict": "reject", "feasibility": 0.9, "process_risk": "low"}
        assert _is_evaluation_acceptable(ev) is False

    def test_accepted_evaluation_with_low_feasibility_rejected(self):
        """feasibility below the hard floor → rejected even if verdict=accept."""
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        ev = {"verdict": "accept", "feasibility": 0.1, "process_risk": "low"}
        assert _is_evaluation_acceptable(ev) is False

    def test_accepted_evaluation_above_floor_ok(self):
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        ev = {"verdict": "accept", "feasibility": 0.7, "process_risk": "low"}
        assert _is_evaluation_acceptable(ev) is True

    def test_revise_evaluation_above_floor_ok(self):
        """revise is allowed — only reject is a hard veto at this level."""
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        ev = {"verdict": "revise", "feasibility": 0.5, "process_risk": "medium"}
        assert _is_evaluation_acceptable(ev) is True

    def test_missing_evaluation_rejected(self):
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable(None) is False
        assert _is_evaluation_acceptable({}) is False

    def test_non_numeric_feasibility_rejected(self):
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({"verdict": "accept", "feasibility": "high"}) is False

    def test_mixed_evaluations_hard_reject_overrides_score(self):
        """Integration: moderator decision logic when 1 reject and 2 accepts."""
        # We'll inspect the consensus_result that moderator logic would produce.
        # Since the full moderator_node uses async LLM calls, we exercise the
        # structural-reject path by reading the helper directly.
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        evaluations = [
            {"verdict": "accept", "feasibility": 0.8},
            {"verdict": "reject", "feasibility": 0.95},
            {"verdict": "accept", "feasibility": 0.7},
        ]
        hard_rejects = [e for e in evaluations if not _is_evaluation_acceptable(e)]
        assert len(hard_rejects) == 1
        assert hard_rejects[0]["verdict"] == "reject"
