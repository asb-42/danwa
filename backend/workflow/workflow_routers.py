"""Router functions for conditional edges in workflow graphs.

Each router inspects the current ``WorkflowState`` and returns a string key
that LangGraph uses to select the next node from a mapping dict.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.workflow.safe_eval import SafeEvalError, evaluate_condition
from backend.workflow.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


def route_sequential(state: WorkflowState) -> str:
    """Always returns the single target for a sequential edge.

    Used when a node has exactly one outgoing non-feedback edge.
    """
    return "next"


def route_conditional(
    conditions: dict[str, str],
) -> Any:
    """Factory that returns a router for conditional (gate) edges.

    Args:
        conditions: Mapping of ``{target_node_id: condition_expression}``.
            Condition expressions are either:

            * a named condition (e.g. ``"consensus_reached"``,
              ``"max_rounds_reached"``, ``"extension_granted"``) — see
              :data:`backend.workflow.safe_eval.NAMED_CONDITIONS` for
              the full registry; or
            * a safe Python expression over the ``state`` mapping (e.g.
              ``"state['current_round'] >= 3"``).

            Expressions are evaluated with :func:`safe_eval.evaluate_condition`
            which uses an AST whitelist — there is no Python ``eval()``
            involved, so the sandbox cannot be escaped via dunder
            traversal or ``__import__``.

    Returns:
        A router function suitable for ``graph.add_conditional_edges()``.
    """

    def _router(state: WorkflowState) -> str:
        for target_node_id, expr in conditions.items():
            try:
                if evaluate_condition(expr, dict(state)):
                    return target_node_id
            except SafeEvalError as exc:
                logger.warning(
                    "Gate condition '%s' for target '%s' is not safe (%s), skipping",
                    expr,
                    target_node_id,
                    exc,
                )
            except Exception as exc:
                logger.warning(
                    "Gate condition '%s' for target '%s' raised %s, skipping",
                    expr,
                    target_node_id,
                    type(exc).__name__,
                )
        # Fallback: return last target if no condition matched
        fallback = list(conditions.keys())[-1] if conditions else "end"
        logger.info("No gate condition matched, falling back to '%s'", fallback)
        return fallback

    return _router


def route_feedback(
    max_rounds: int = 10,
) -> Any:
    """Factory that returns a router for feedback (back) edges.

    Returns ``"continue"`` if the current round is below ``max_rounds``,
    or in the extension zone (``max_rounds + 2``) when ``enable_extra_rounds``
    is True and ``extension_granted`` is also True.
    Otherwise returns ``"exit"`` to break the loop.

    Args:
        max_rounds: Maximum number of rounds before forcing exit.

    Returns:
        A router function suitable for ``graph.add_conditional_edges()``.
    """

    def _router(state: WorkflowState) -> str:
        current_round = state.get("current_round", 1)
        enable_extra = state.get("enable_extra_rounds", False)

        # Normal round budget
        if current_round <= max_rounds:
            logger.info("Feedback loop: round %d <= max %d, continuing", current_round, max_rounds)
            return "continue"

        # Extension zone — allow up to max_rounds + 2 if extension was granted
        if enable_extra and current_round <= max_rounds + 2:
            extension_granted = state.get("extension_granted")
            if extension_granted is True:
                logger.info(
                    "Feedback loop: extra round %d (of max %d+2) granted, continuing",
                    current_round,
                    max_rounds,
                )
                return "continue"
            logger.info(
                "Feedback loop: extra round %d (of max %d+2) not granted, exiting",
                current_round,
                max_rounds,
            )
            return "exit"

        logger.info("Feedback loop: round %d > max %d, exiting", current_round, max_rounds)
        return "exit"

    return _router


def route_after_interjection(state: WorkflowState) -> str:
    """Router used after an interjection node — always proceeds to the next node.

    The interjection node itself handles pausing/consuming, so this router
    simply returns ``"next"`` to continue the flow.
    """
    return "next"


def _resolve_max_draft_versions(state: WorkflowState) -> int:
    """Read ``max_draft_versions`` from ``termination_conditions``; fall back to 5.

    Workflow authors can override the historical default of 5 by adding an
    entry like ``{"type": "max_draft_versions", "value": 8}`` to
    ``WorkflowDefinition.termination_conditions``.  The default is kept
    at 5 to preserve existing behaviour for the seeded
    ``transactional_drafting`` template.
    """
    for tc in state.get("termination_conditions", []) or []:
        if isinstance(tc, dict) and tc.get("type") == "max_draft_versions":
            value = tc.get("value")
            if isinstance(value, int) and value > 0:
                return value
    return 5


def route_decision(max_rounds: int = 5) -> Any:
    """Factory that returns a router for the Moderator's decision in Transactional Drafting.

    If the current round exceeds ``max_rounds``, returns ``"construction_deadlock"``
    to terminate.  Otherwise inspects ``state["consensus_result"]["verdict"]``:

    - ``"approved"`` → ``"approved"`` (→ END)
    - ``"revision_required"`` → ``"return_to_builder"`` (→ BuilderNode)

    Deadlock fallback: if ``draft_version >= max_draft_versions`` (read from
    ``termination_conditions`` or 5 by default), returns
    ``"construction_deadlock"``.  Workflow authors can override the threshold
    per template — see :func:`_resolve_max_draft_versions`.

    Args:
        max_rounds: Maximum number of drafting rounds before forced termination.
    """

    def _router(state: WorkflowState) -> str:
        current_round = state.get("current_round", 1)
        draft_version = state.get("draft_version", 1)
        effective_max = max_rounds or state.get("max_rounds", 5)
        max_draft_versions = _resolve_max_draft_versions(state)

        if current_round > effective_max:
            logger.warning(
                "Decision router: round %d exceeds max %d, terminating",
                current_round,
                effective_max,
            )
            return "construction_deadlock"

        if draft_version >= max_draft_versions:
            logger.warning(
                "Decision router: construction deadlock at draft_version=%d (max=%d)",
                draft_version,
                max_draft_versions,
            )
            return "construction_deadlock"

        result = state.get("consensus_result", {})
        verdict = result.get("verdict", "revision_required")
        if verdict == "approved":
            logger.info("Decision router: approved (round=%d, draft_version=%d)", current_round, draft_version)
            return "approved"
        logger.info(
            "Decision router: return_to_builder (round=%d, draft_version=%d, concerns=%s)",
            current_round,
            draft_version,
            result.get("concerns", []),
        )
        return "return_to_builder"

    return _router
