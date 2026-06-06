"""Safe expression evaluator and named-condition registry for workflow gates.

The original code used ``eval(expr, {"__builtins__": {}}, dict(state))`` to
evaluate gate conditions like ``"consensus_reached"`` or
``"current_round >= 3"``.  The ``__builtins__: {}`` sandbox is not actually
safe — Python introspection can be used to escape it, e.g.
``(1).__class__.__base__.__subclasses__()`` chains into ``os.system``.

This module provides:

* :func:`safe_eval` — an AST-walking evaluator that only accepts pure
  Python expressions over a single ``state`` mapping and a closed set of
  operators.  Anything else raises :class:`SafeEvalError`.
* :func:`evaluate_condition` — resolves a condition string.  It first
  checks the :data:`NAMED_CONDITIONS` registry for symbolic names like
  ``"consensus_reached"`` and only falls back to :func:`safe_eval` for
  arbitrary expressions.  This lets workflow templates use readable
  identifiers without paying the cost (or risk) of arbitrary Python.
* :data:`NAMED_CONDITIONS` — the public registry.  Tests and product
  code can introspect / extend it.

AST-walker design
-----------------
The walker descends the parsed ``ast.Expression`` and emits a small
``stack machine`` over Python primitives.  Allowed node types are
explicitly enumerated (see ``_ALLOWED_NODES``); anything not on the list
— function calls, comprehensions, lambdas, attribute access on objects
other than ``state``, ``del``, ``assert``, f-strings, starred
expressions, … — is rejected with :class:`SafeEvalError`.
"""

from __future__ import annotations

import ast
import logging
from collections.abc import Callable, Mapping
from typing import Any

logger = logging.getLogger(__name__)


class SafeEvalError(Exception):
    """Raised when an expression cannot be safely evaluated."""


# ---------------------------------------------------------------------------
# Named conditions — the preferred way to author gate conditions.
# ---------------------------------------------------------------------------
#
# A named condition is a stable, human-readable identifier that maps to a
# pure Python callable over ``WorkflowState``.  Workflow templates should
# use these names instead of writing arbitrary Python expressions.
#
# The names mirror the values used in the bundled workflow templates
# (``modules/workflows/workflow-tpl-*/profile.json``) so existing
# template JSON keeps working unchanged.
# ---------------------------------------------------------------------------

NAMED_CONDITIONS: dict[str, Callable[[Mapping[str, Any]], bool]] = {
    "consensus_reached": lambda s: s.get("consensus_result", {}).get("verdict") == "approved",
    "max_rounds_reached": lambda s: s.get("current_round", 0) > s.get("max_rounds", 5),
    "rounds_exhausted": lambda s: s.get("current_round", 0) > s.get("max_rounds", 5),
    "extension_granted": lambda s: s.get("extension_granted") is True,
    "draft_deadlock": lambda s: s.get("draft_version", 0) >= _max_draft_versions(s),
    "is_paused": lambda s: bool(s.get("is_paused", False)),
    "approved": lambda s: s.get("consensus_result", {}).get("verdict") == "approved",
    "revision_required": lambda s: s.get("consensus_result", {}).get("verdict") == "revision_required",
    "construction_deadlock": lambda s: s.get("consensus_result", {}).get("verdict") == "construction_deadlock",
    # Phase-transition gates: always pass — the gate is only reached after
    # agents in the current phase have completed their work.
    "framing_complete": lambda s: True,
    "positions_ready": lambda s: True,
    "stress_test_complete": lambda s: True,
    "integration_complete": lambda s: True,
    "True": lambda s: True,
    "False": lambda s: False,
}


def _max_draft_versions(state: Mapping[str, Any]) -> int:
    """Read ``max_draft_versions`` from ``termination_conditions`` or fall back to 5."""
    for tc in state.get("termination_conditions", []) or []:
        if isinstance(tc, Mapping) and tc.get("type") == "max_draft_versions":
            value = tc.get("value")
            if isinstance(value, int):
                return value
    return 5


def is_named_condition(name: str) -> bool:
    """Return True iff ``name`` is a registered named condition."""
    return name in NAMED_CONDITIONS


# ---------------------------------------------------------------------------
# AST-walking safe evaluator
# ---------------------------------------------------------------------------

_ALLOWED_NODES: frozenset[type[ast.AST]] = frozenset(
    {
        ast.Expression,
        ast.Compare,
        ast.BoolOp,
        ast.BinOp,
        ast.UnaryOp,
        ast.Name,
        ast.Load,
        ast.Constant,
        ast.Tuple,
        ast.List,
        ast.Subscript,
        # Operators (instances of these are allowed; the operator kinds
        # are individually whitelisted in _eval_node).
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Mod,
        ast.FloorDiv,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Not,
        ast.Invert,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.In,
        ast.NotIn,
        ast.Is,
        ast.IsNot,
        ast.And,
        ast.Or,
    }
)

# Names that may appear in expressions. ``state`` is the *only* binding
# the walker ever resolves; the truthy / falsy constants are useful for
# fallback conditions like ``"True"`` used by the compiler at line 408.
_ALLOWED_NAMES: frozenset[str] = frozenset({"state", "True", "False", "None"})


def safe_eval(expression: str, state: Mapping[str, Any]) -> Any:
    """Evaluate ``expression`` over ``state`` without invoking Python's ``eval``.

    Raises :class:`SafeEvalError` if the expression uses any construct
    outside the whitelist (function calls, comprehensions, attribute
    access on anything other than ``state``, etc.).

    Returns the raw expression result.  Callers that need a boolean
    should wrap the call with :func:`bool`.
    """
    if not isinstance(expression, str):
        raise SafeEvalError(f"expression must be str, got {type(expression).__name__}")
    if not expression.strip():
        raise SafeEvalError("empty expression")

    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise SafeEvalError(f"invalid syntax: {exc.msg}") from exc

    # Whitelist pass: every AST node must be one we know how to handle.
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODES:
            raise SafeEvalError(f"disallowed construct: {type(node).__name__}")

    return _eval_node(tree.body, state)


def _eval_node(node: ast.AST, state: Mapping[str, Any]) -> Any:
    """Dispatch on AST node type and return the corresponding Python value."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "state":
            return state
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
        # Bare-name lookup against state keys.  This lets authors write
        # ``current_round >= 3`` instead of the more verbose
        # ``state['current_round'] >= 3``.  Reading state values is
        # safe — values are never written through this path, and the
        # state mapping can be substituted with a read-only proxy by
        # the caller if necessary.
        if isinstance(state, Mapping) and node.id in state:
            return state[node.id]
        raise SafeEvalError(f"unknown name: {node.id!r}")
    if isinstance(node, ast.UnaryOp):
        operand = _eval_node(node.operand, state)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.Not):
            return not operand
        if isinstance(node.op, ast.Invert):
            return ~operand
        raise SafeEvalError(f"disallowed unary op: {type(node.op).__name__}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, state)
        right = _eval_node(node.right, state)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left**right
        raise SafeEvalError(f"disallowed binary op: {type(node.op).__name__}")
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            value: Any = True
            for v in node.values:
                value = _eval_node(v, state)
                if not value:
                    return value
            return value
        if isinstance(node.op, ast.Or):
            value = False
            for v in node.values:
                value = _eval_node(v, state)
                if value:
                    return value
            return value
        raise SafeEvalError(f"disallowed bool op: {type(node.op).__name__}")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, state)
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            right = _eval_node(comparator, state)
            if isinstance(op, ast.Eq) and not (left == right):
                return False
            if isinstance(op, ast.NotEq) and not (left != right):
                return False
            if isinstance(op, ast.Lt) and not (left < right):
                return False
            if isinstance(op, ast.LtE) and not (left <= right):
                return False
            if isinstance(op, ast.Gt) and not (left > right):
                return False
            if isinstance(op, ast.GtE) and not (left >= right):
                return False
            if isinstance(op, ast.In) and left not in right:
                return False
            if isinstance(op, ast.NotIn) and not (left not in right):
                return False
            if isinstance(op, ast.Is) and left is not right:
                return False
            if isinstance(op, ast.IsNot) and not (left is not right):
                return False
            left = right
        return True
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(elt, state) for elt in node.elts)
    if isinstance(node, ast.List):
        return [_eval_node(elt, state) for elt in node.elts]
    if isinstance(node, ast.Subscript):
        value = _eval_node(node.value, state)
        if not isinstance(value, Mapping):
            raise SafeEvalError("subscript on non-mapping value")
        key = _eval_key(node.slice, state)
        return value[key]
    raise SafeEvalError(f"unhandled node: {type(node).__name__}")


def _eval_key(node: ast.AST, state: Mapping[str, Any]) -> Any:
    """Resolve the key of a subscript — supports ``state["x"]`` and ``state.get("x")``."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id == "True":
            return True
        if node.id == "False":
            return False
        if node.id == "None":
            return None
    if isinstance(node, ast.UnaryOp):
        return _eval_node(node, state)
    if isinstance(node, ast.Tuple):
        return tuple(_eval_node(elt, state) for elt in node.elts)
    raise SafeEvalError(f"unsupported subscript key: {type(node).__name__}")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def evaluate_condition(expression: str, state: Mapping[str, Any]) -> bool:
    """Resolve a condition string to a boolean.

    Resolution order:

    1.  **Empty / whitespace-only string** — returns ``False`` (a
        missing condition is treated as "no condition triggered", which
        matches the original ``if eval(...)`` semantics where ``""``
        raised and was caught).
    2.  **Named condition** — looked up in :data:`NAMED_CONDITIONS`.
        Unknown names raise :class:`SafeEvalError` so authors notice
        typos immediately.
    3.  **Arbitrary expression** — passed through :func:`safe_eval` and
        the result is coerced to ``bool``.

    Args:
        expression: The condition string from a workflow definition or
            a gate node.
        state: The current :class:`WorkflowState` mapping.

    Returns:
        The truthiness of the resolved condition.

    Raises:
        SafeEvalError: if the expression is neither a known name nor a
            safe expression.
    """
    if not expression or not expression.strip():
        return False
    stripped = expression.strip()
    if stripped in NAMED_CONDITIONS:
        return bool(NAMED_CONDITIONS[stripped](state))
    return bool(safe_eval(stripped, state))
