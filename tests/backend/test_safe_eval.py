"""Tests for backend/workflow/safe_eval.py.

Covers the AST-walking safe expression evaluator and the named-condition
registry used by workflow gates.

- NAMED_CONDITIONS registry content + behaviour
- is_named_condition helper
- _max_draft_versions helper (with/without termination_conditions)
- safe_eval: input validation, simple constants, comparisons, boolean ops,
  unary ops, binary ops, all operator kinds, tuples, lists, subscripts,
  state lookup, unknown name, disallowed AST nodes, state["key"] access,
  subscript on non-mapping, unsupported subscript key
- evaluate_condition: empty string, named condition, arbitrary expression
  with truthy/falsy result
"""

from __future__ import annotations

import pytest

from backend.workflow.safe_eval import (
    NAMED_CONDITIONS,
    SafeEvalError,
    _max_draft_versions,
    evaluate_condition,
    is_named_condition,
    safe_eval,
)

# ---------------------------------------------------------------------------
# NAMED_CONDITIONS registry
# ---------------------------------------------------------------------------


class TestNamedConditions:
    """The registry should contain the documented names and behave correctly."""

    def test_consensus_reached_approved(self) -> None:
        state = {"consensus_result": {"verdict": "approved"}}
        assert NAMED_CONDITIONS["consensus_reached"](state) is True

    def test_consensus_reached_other(self) -> None:
        state = {"consensus_result": {"verdict": "revision_required"}}
        assert NAMED_CONDITIONS["consensus_reached"](state) is False

    def test_consensus_reached_missing(self) -> None:
        assert NAMED_CONDITIONS["consensus_reached"]({}) is False

    def test_max_rounds_reached_true(self) -> None:
        state = {"current_round": 6, "max_rounds": 5}
        assert NAMED_CONDITIONS["max_rounds_reached"](state) is True

    def test_max_rounds_reached_false(self) -> None:
        state = {"current_round": 3, "max_rounds": 5}
        assert NAMED_CONDITIONS["max_rounds_reached"](state) is False

    def test_max_rounds_reached_defaults(self) -> None:
        # current_round defaults to 0, max_rounds defaults to 5
        assert NAMED_CONDITIONS["max_rounds_reached"]({}) is False

    def test_rounds_exhausted_alias(self) -> None:
        state = {"current_round": 10, "max_rounds": 5}
        assert NAMED_CONDITIONS["rounds_exhausted"](state) is True

    def test_extension_granted_true(self) -> None:
        assert NAMED_CONDITIONS["extension_granted"]({"extension_granted": True}) is True

    def test_extension_granted_false(self) -> None:
        assert NAMED_CONDITIONS["extension_granted"]({"extension_granted": False}) is False

    def test_extension_granted_missing(self) -> None:
        assert NAMED_CONDITIONS["extension_granted"]({}) is False

    def test_draft_deadlock_with_termination_conditions(self) -> None:
        state = {
            "draft_version": 3,
            "termination_conditions": [{"type": "max_draft_versions", "value": 3}],
        }
        assert NAMED_CONDITIONS["draft_deadlock"](state) is True

    def test_draft_deadlock_default_threshold(self) -> None:
        state = {"draft_version": 5}
        assert NAMED_CONDITIONS["draft_deadlock"](state) is True

    def test_draft_deadlock_below_threshold(self) -> None:
        state = {"draft_version": 1}
        assert NAMED_CONDITIONS["draft_deadlock"](state) is False

    def test_is_paused_true(self) -> None:
        assert NAMED_CONDITIONS["is_paused"]({"is_paused": True}) is True

    def test_is_paused_default_false(self) -> None:
        assert NAMED_CONDITIONS["is_paused"]({}) is False

    def test_approved_alias(self) -> None:
        state = {"consensus_result": {"verdict": "approved"}}
        assert NAMED_CONDITIONS["approved"](state) is True

    def test_revision_required(self) -> None:
        state = {"consensus_result": {"verdict": "revision_required"}}
        assert NAMED_CONDITIONS["revision_required"](state) is True

    def test_construction_deadlock(self) -> None:
        state = {"consensus_result": {"verdict": "construction_deadlock"}}
        assert NAMED_CONDITIONS["construction_deadlock"](state) is True

    def test_construction_deadlock_other_verdict(self) -> None:
        state = {"consensus_result": {"verdict": "approved"}}
        assert NAMED_CONDITIONS["construction_deadlock"](state) is False

    def test_phase_transition_gates_always_pass(self) -> None:
        for name in (
            "framing_complete",
            "positions_ready",
            "stress_test_complete",
            "integration_complete",
        ):
            assert NAMED_CONDITIONS[name]({}) is True, name

    def test_true_constant_named_condition(self) -> None:
        assert NAMED_CONDITIONS["True"]({}) is True

    def test_false_constant_named_condition(self) -> None:
        assert NAMED_CONDITIONS["False"]({}) is False


class TestIsNamedCondition:
    def test_known(self) -> None:
        assert is_named_condition("consensus_reached") is True

    def test_unknown(self) -> None:
        assert is_named_condition("nope") is False

    def test_empty(self) -> None:
        assert is_named_condition("") is False


# ---------------------------------------------------------------------------
# _max_draft_versions
# ---------------------------------------------------------------------------


class TestMaxDraftVersions:
    def test_default_when_no_termination_conditions(self) -> None:
        assert _max_draft_versions({}) == 5

    def test_default_when_empty_list(self) -> None:
        assert _max_draft_versions({"termination_conditions": []}) == 5

    def test_default_when_none(self) -> None:
        assert _max_draft_versions({"termination_conditions": None}) == 5

    def test_reads_from_termination_conditions(self) -> None:
        state = {"termination_conditions": [{"type": "max_draft_versions", "value": 7}]}
        assert _max_draft_versions(state) == 7

    def test_ignores_non_matching_types(self) -> None:
        state = {"termination_conditions": [{"type": "max_rounds", "value": 9}]}
        assert _max_draft_versions(state) == 5

    def test_ignores_non_int_value(self) -> None:
        state = {"termination_conditions": [{"type": "max_draft_versions", "value": "7"}]}
        assert _max_draft_versions(state) == 5

    def test_picks_first_match(self) -> None:
        state = {
            "termination_conditions": [
                {"type": "max_draft_versions", "value": 2},
                {"type": "max_draft_versions", "value": 99},
            ]
        }
        assert _max_draft_versions(state) == 2

    def test_skips_non_mapping_entries(self) -> None:
        state = {"termination_conditions": ["oops", {"type": "max_draft_versions", "value": 4}]}
        assert _max_draft_versions(state) == 4


# ---------------------------------------------------------------------------
# safe_eval
# ---------------------------------------------------------------------------


class TestSafeEvalInputValidation:
    def test_non_string_raises(self) -> None:
        with pytest.raises(SafeEvalError, match="expression must be str"):
            safe_eval(123, {})  # type: ignore[arg-type]

    def test_empty_raises(self) -> None:
        with pytest.raises(SafeEvalError, match="empty expression"):
            safe_eval("", {})

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(SafeEvalError, match="empty expression"):
            safe_eval("   \n\t  ", {})

    def test_syntax_error_raises(self) -> None:
        with pytest.raises(SafeEvalError, match="invalid syntax"):
            safe_eval("1 +", {})


class TestSafeEvalDisallowedNodes:
    def test_function_call_rejected(self) -> None:
        with pytest.raises(SafeEvalError, match="disallowed construct: Call"):
            safe_eval("len(state)", {"x": [1, 2]})

    def test_attribute_access_rejected(self) -> None:
        with pytest.raises(SafeEvalError, match="disallowed construct: Attribute"):
            safe_eval("state.get", {"x": 1})

    def test_lambda_rejected(self) -> None:
        # The Call node is rejected before Lambda is even inspected
        with pytest.raises(SafeEvalError, match="disallowed construct"):
            safe_eval("(lambda: 1)()", {})

    def test_if_expression_rejected(self) -> None:
        # IfExp is not in the whitelist
        with pytest.raises(SafeEvalError):
            safe_eval("1 if True else 2", {})

    def test_dict_literal_rejected(self) -> None:
        with pytest.raises(SafeEvalError):
            safe_eval("{'a': 1}", {})

    def test_comprehension_rejected(self) -> None:
        with pytest.raises(SafeEvalError):
            safe_eval("[x for x in state]", {"x": 1})

    def test_fstring_rejected(self) -> None:
        with pytest.raises(SafeEvalError, match="JoinedStr"):
            safe_eval("f'hello {1}'", {})

    def test_starred_rejected(self) -> None:
        with pytest.raises(SafeEvalError):
            safe_eval("[*state]", {"a": 1, "b": 2})


class TestSafeEvalConstants:
    def test_int(self) -> None:
        assert safe_eval("42", {}) == 42

    def test_float(self) -> None:
        assert safe_eval("3.14", {}) == 3.14

    def test_string(self) -> None:
        assert safe_eval("'hello'", {}) == "hello"

    def test_string_double_quotes(self) -> None:
        assert safe_eval('"hello"', {}) == "hello"

    def test_true(self) -> None:
        assert safe_eval("True", {}) is True

    def test_false(self) -> None:
        assert safe_eval("False", {}) is False

    def test_none(self) -> None:
        assert safe_eval("None", {}) is None

    def test_tuple(self) -> None:
        assert safe_eval("(1, 2, 3)", {}) == (1, 2, 3)

    def test_list(self) -> None:
        assert safe_eval("[1, 2, 3]", {}) == [1, 2, 3]


class TestSafeEvalStateLookup:
    def test_state_returns_mapping(self) -> None:
        s = {"a": 1}
        assert safe_eval("state", s) is s

    def test_bare_name_looks_up_state(self) -> None:
        assert safe_eval("current_round", {"current_round": 3}) == 3

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(SafeEvalError, match="unknown name"):
            safe_eval("missing", {})

    def test_state_subscript_string(self) -> None:
        assert safe_eval("state['x']", {"x": 7}) == 7

    def test_state_subscript_int(self) -> None:
        assert safe_eval("state[1]", {1: "one"}) == "one"

    def test_subscript_on_non_mapping_raises(self) -> None:
        # state['x'] is a list, then [0] is a list subscript on a non-Mapping
        with pytest.raises(SafeEvalError, match="subscript on non-mapping"):
            safe_eval("state['x'][0]", {"x": [1, 2]})

    def test_subscript_with_bool_key(self) -> None:
        # state[True] is parsed as Subscript(Name('True')) over a mapping
        assert safe_eval("state[True]", {True: "yes"}) == "yes"

    def test_subscript_with_complex_key_rejected(self) -> None:
        with pytest.raises(SafeEvalError, match="unsupported subscript key"):
            safe_eval("state[1 + 2]", {"state": {3: "ok"}})

    def test_nested_subscript(self) -> None:
        state = {"outer": {"inner": 42}}
        assert safe_eval("state['outer']['inner']", state) == 42


class TestSafeEvalUnaryOps:
    def test_neg(self) -> None:
        assert safe_eval("-5", {}) == -5

    def test_pos(self) -> None:
        assert safe_eval("+5", {}) == 5

    def test_not_true(self) -> None:
        assert safe_eval("not True", {}) is False

    def test_not_false(self) -> None:
        assert safe_eval("not False", {}) is True

    def test_invert(self) -> None:
        assert safe_eval("~0", {}) == -1


class TestSafeEvalBinaryOps:
    def test_add(self) -> None:
        assert safe_eval("2 + 3", {}) == 5

    def test_sub(self) -> None:
        assert safe_eval("5 - 2", {}) == 3

    def test_mul(self) -> None:
        assert safe_eval("3 * 4", {}) == 12

    def test_div(self) -> None:
        assert safe_eval("10 / 4", {}) == 2.5

    def test_floor_div(self) -> None:
        assert safe_eval("10 // 4", {}) == 2

    def test_mod(self) -> None:
        assert safe_eval("10 % 3", {}) == 1

    def test_pow(self) -> None:
        assert safe_eval("2 ** 8", {}) == 256

    def test_string_concat(self) -> None:
        assert safe_eval("'a' + 'b'", {}) == "ab"

    def test_list_concat(self) -> None:
        assert safe_eval("[1] + [2]", {}) == [1, 2]


class TestSafeEvalBoolOps:
    def test_and_short_circuit(self) -> None:
        assert safe_eval("False and 1", {}) is False

    def test_and_true(self) -> None:
        assert safe_eval("True and 5", {}) == 5

    def test_or_short_circuit(self) -> None:
        assert safe_eval("True or 1", {}) is True

    def test_or_false(self) -> None:
        assert safe_eval("False or 7", {}) == 7

    def test_chained_and_or(self) -> None:
        assert safe_eval("True and False or 1", {}) == 1

    def test_state_lookup_in_boolop(self) -> None:
        assert safe_eval("x and y", {"x": True, "y": 42}) == 42


class TestSafeEvalComparisons:
    def test_eq_true(self) -> None:
        assert safe_eval("1 == 1", {}) is True

    def test_eq_false(self) -> None:
        assert safe_eval("1 == 2", {}) is False

    def test_neq(self) -> None:
        assert safe_eval("1 != 2", {}) is True

    def test_lt(self) -> None:
        assert safe_eval("1 < 2", {}) is True

    def test_lte(self) -> None:
        assert safe_eval("2 <= 2", {}) is True

    def test_gt(self) -> None:
        assert safe_eval("3 > 2", {}) is True

    def test_gte(self) -> None:
        assert safe_eval("2 >= 2", {}) is True

    def test_in_true(self) -> None:
        assert safe_eval("1 in [1, 2, 3]", {}) is True

    def test_in_false(self) -> None:
        assert safe_eval("4 in [1, 2, 3]", {}) is False

    def test_not_in(self) -> None:
        assert safe_eval("4 not in [1, 2, 3]", {}) is True

    def test_is(self) -> None:
        assert safe_eval("None is None", {}) is True

    def test_is_not(self) -> None:
        assert safe_eval("None is not 1", {}) is True

    def test_chained_compare(self) -> None:
        assert safe_eval("1 < 2 < 3", {}) is True

    def test_chained_compare_fail(self) -> None:
        assert safe_eval("1 < 3 < 2", {}) is False

    def test_state_lookup_in_compare(self) -> None:
        assert safe_eval("current_round >= 3", {"current_round": 3}) is True

    def test_state_subscript_in_compare(self) -> None:
        state = {"verdict": "approved"}
        assert safe_eval("state['verdict'] == 'approved'", state) is True


class TestSafeEvalMixedExpressions:
    def test_combined_expression(self) -> None:
        state = {"current_round": 3, "max_rounds": 5, "consensus": {"verdict": "approved"}}
        # (current_round < max_rounds) and (consensus['verdict'] == 'approved')
        expr = "current_round < max_rounds and state['consensus']['verdict'] == 'approved'"
        assert safe_eval(expr, state) is True

    def test_complex_arithmetic(self) -> None:
        assert safe_eval("2 + 3 * 4 - 1", {}) == 13

    def test_list_contains(self) -> None:
        assert safe_eval("'a' in ['a', 'b']", {}) is True

    def test_truthy_state_dict(self) -> None:
        # A non-empty state should be truthy
        assert bool(safe_eval("state", {"a": 1})) is True


# ---------------------------------------------------------------------------
# evaluate_condition
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    def test_empty_string_returns_false(self) -> None:
        assert evaluate_condition("", {}) is False

    def test_whitespace_only_returns_false(self) -> None:
        assert evaluate_condition("   \n  ", {}) is False

    def test_named_condition_consensus_reached(self) -> None:
        state = {"consensus_result": {"verdict": "approved"}}
        assert evaluate_condition("consensus_reached", state) is True

    def test_named_condition_false(self) -> None:
        state = {"consensus_result": {"verdict": "revision_required"}}
        assert evaluate_condition("consensus_reached", state) is False

    def test_named_condition_true_constant(self) -> None:
        # The literal string "True" is a registered name that always returns True
        assert evaluate_condition("True", {}) is True

    def test_named_condition_false_constant(self) -> None:
        assert evaluate_condition("False", {}) is False

    def test_arbitrary_truthy_expression(self) -> None:
        assert evaluate_condition("1 + 1", {}) is True

    def test_arbitrary_falsy_expression(self) -> None:
        assert evaluate_condition("0", {}) is False

    def test_arbitrary_state_expression(self) -> None:
        assert evaluate_condition("current_round >= 3", {"current_round": 3}) is True
        assert evaluate_condition("current_round >= 3", {"current_round": 2}) is False

    def test_named_condition_with_surrounding_whitespace(self) -> None:
        state = {"consensus_result": {"verdict": "approved"}}
        assert evaluate_condition("  consensus_reached  ", state) is True

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(SafeEvalError):
            evaluate_condition("not_a_real_condition", {})

    def test_invalid_syntax_raises(self) -> None:
        with pytest.raises(SafeEvalError):
            evaluate_condition("1 +", {})
