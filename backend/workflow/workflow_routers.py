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

# Lazy import to avoid circular dependency at module level
_publish_async = None


def _get_publish():
    """Return (or lazily create) publish."""
    global _publish_async
    if _publish_async is None:
        from backend.api.events import publish_async

        _publish_async = publish_async
    return _publish_async


def route_sequential(state: WorkflowState) -> str:
    """Always returns the single target for a sequential edge.

    Used when a node has exactly one outgoing non-feedback edge.
    """
    return "next"


def route_conditional(
    conditions: dict[str, str],
    gate_node_id: str = "",
) -> Any:
    """Factory that returns a router for conditional (gate) edges.

    Publishes a ``gate.decision`` SSE event with the evaluation details
    so the frontend can show which path was taken and why.

    Args:
        conditions: Mapping of ``{target_node_id: condition_expression}``.
        gate_node_id: The ID of the gate node (for logging and SSE events).

    Returns:
        A router function suitable for ``graph.add_conditional_edges()``.
    """

    async def _router(state: WorkflowState) -> str:
        """Router the instance."""
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        state_dict = dict(state)
        evaluations: list[dict[str, Any]] = []

        for target_node_id, expr in conditions.items():
            try:
                result = evaluate_condition(expr, state_dict)
                evaluations.append({"condition": expr, "target": target_node_id, "result": result})
                if result:
                    # Publish gate.decision SSE event
                    await _publish_gate_decision(
                        session_id,
                        gate_node_id,
                        expr,
                        True,
                        target_node_id,
                        False,
                        evaluations,
                        current_round,
                    )
                    return target_node_id
            except SafeEvalError as exc:
                evaluations.append({"condition": expr, "target": target_node_id, "result": False, "error": str(exc)})
                logger.warning(
                    "Gate condition '%s' for target '%s' is not safe (%s), skipping",
                    expr,
                    target_node_id,
                    exc,
                )
            except Exception as exc:
                evaluations.append({"condition": expr, "target": target_node_id, "result": False, "error": str(exc)})
                logger.warning(
                    "Gate condition '%s' for target '%s' raised %s, skipping",
                    expr,
                    target_node_id,
                    type(exc).__name__,
                )

        # Fallback: return last target if no condition matched
        fallback = list(conditions.keys())[-1] if conditions else "end"
        logger.info("No gate condition matched, falling back to '%s'", fallback)
        await _publish_gate_decision(
            session_id,
            gate_node_id,
            "(none matched)",
            False,
            fallback,
            True,
            evaluations,
            current_round,
        )
        return fallback

    return _router


async def _publish_gate_decision(
    session_id: str,
    gate_node_id: str,
    condition: str,
    result: bool,
    chosen_target: str,
    fallback_used: bool,
    evaluations: list[dict[str, Any]],
    current_round: int,
) -> None:
    """Publish a gate.decision SSE event and write an audit log entry."""
    publish = _get_publish()
    try:
        await publish(
            session_id,
            "gate.decision",
            {
                "gate_node_id": gate_node_id,
                "condition": condition,
                "result": result,
                "chosen_target": chosen_target,
                "fallback_used": fallback_used,
                "all_evaluations": evaluations,
                "round": current_round,
            },
        )
    except Exception:
        logger.debug("Failed to publish gate.decision SSE event", exc_info=True)

    # Audit log
    try:
        from backend.workflow.audit_logger import get_audit_logger

        get_audit_logger().log_gate_decision(
            session_id=session_id,
            workflow_id="",
            workflow_version=1,
            gate_node_id=gate_node_id,
            condition=condition,
            result=result,
            chosen_target=chosen_target,
            fallback_used=fallback_used,
            all_evaluations=evaluations,
        )
    except Exception:
        logger.debug("Failed to log gate decision to audit", exc_info=True)


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
        # F-10: Clamp to at least 1 so max_rounds=0 doesn't allow
        # the extension branch to fire for regular rounds.
        effective = max(max_rounds, 1)

        # Normal round budget
        if current_round <= effective:
            logger.info("Feedback loop: round %d <= max %d, continuing", current_round, max_rounds)
            return "continue"

        # Extension zone — allow up to max_rounds + 2 if extension was granted
        if enable_extra and current_round <= effective + 2:
            extension_granted = state.get("extension_granted")
            if extension_granted is True:
                logger.info(
                    "Feedback loop: extra round %d (of max %d+2) granted, continuing",
                    current_round,
                    effective,
                )
                return "continue"
            logger.info(
                "Feedback loop: extra round %d (of max %d+2) not granted, exiting",
                current_round,
                effective,
            )
            return "exit"

        logger.info("Feedback loop: round %d > max %d, exiting", current_round, effective)
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


def route_decision(
    max_rounds: int = 5,
    verdict_map: dict[str, str] | None = None,
) -> Any:
    """Factory that returns a router for the Moderator's decision in Transactional Drafting.

    If the current round exceeds ``max_rounds``, returns ``"construction_deadlock"``
    to terminate.  Otherwise inspects ``state["consensus_result"]["verdict"]``
    and translates it to a mapping key via ``verdict_map``.

    The :class:`WorkflowCompiler` builds ``verdict_map`` from the actual
    decision edges in the workflow template, so the router return value
    always matches a real edge target.  This fixes the silent-breakage
    bug where a template designer renaming a condition (e.g. from
    ``"approved"`` to ``"accept"``) would route the workflow to the
    wrong node.

    Deadlock fallback: if ``draft_version >= max_draft_versions`` (read from
    ``termination_conditions`` or 5 by default), returns
    ``"construction_deadlock"``.  Workflow authors can override the threshold
    per template — see :func:`_resolve_max_draft_versions`.

    Args:
        max_rounds: Maximum number of drafting rounds before forced termination.
        verdict_map: Mapping from ``consensus_result["verdict"]`` values
            to mapping keys understood by ``graph.add_conditional_edges``.
            Defaults to the historical mapping
            ``{"approved": "approved", "revision_required": "return_to_builder"}``
            which preserves the behaviour of pre-Sprint-32 templates.
    """
    if verdict_map is None:
        verdict_map = {
            "approved": "approved",
            "revision_required": "return_to_builder",
        }
    # Default key returned when ``verdict_map`` has no entry for the
    # actual verdict value.  Falling back to "return_to_builder" keeps
    # the legacy "approve-or-revise" semantics for unrecognised verdicts.
    fallback_key = "return_to_builder"
    # Prefer the explicit "revision_required" entry, else any
    # non-"approved" entry, else the fallback.
    for verdict_value, key in verdict_map.items():
        if verdict_value != "approved":
            fallback_key = key
            break

    def _router(state: WorkflowState) -> str:
        current_round = state.get("current_round", 1)
        draft_version = state.get("draft_version", 1)
        effective_max = max_rounds or state.get("max_rounds", 5)
        max_draft_versions = _resolve_max_draft_versions(state)

        if current_round > effective_max:
            # Extension zone: ``route_feedback`` allows up to
            # ``max_rounds + 2`` when ``enable_extra_rounds`` is set
            # and the user has granted an extension via the
            # moderator's HITL wait loop.  ``route_decision`` must
            # honour the same grant — otherwise the extension is
            # silently discarded and the workflow terminates with
            # ``"construction_deadlock"`` even though the user
            # explicitly asked for more rounds.  See audit M11.
            enable_extra = state.get("enable_extra_rounds", False)
            extension_granted = state.get("extension_granted") is True
            in_extension_zone = current_round <= effective_max + 2
            if enable_extra and extension_granted and in_extension_zone:
                logger.info(
                    "Decision router: round %d within extension zone (max=%d+2) — extension granted, continuing",
                    current_round,
                    effective_max,
                )
            else:
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
        mapping_key = verdict_map.get(verdict, fallback_key)
        if mapping_key == "approved":
            logger.info(
                "Decision router: approved (round=%d, draft_version=%d, key=%s)",
                current_round,
                draft_version,
                mapping_key,
            )
        else:
            logger.info(
                "Decision router: %s (round=%d, draft_version=%d, verdict=%s, concerns=%s)",
                mapping_key,
                current_round,
                draft_version,
                verdict,
                result.get("concerns", []),
            )
        return mapping_key

    return _router
