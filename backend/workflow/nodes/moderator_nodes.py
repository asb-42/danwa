"""Moderator, gate, and tone-profile node factories for LangGraph workflows.

These nodes orchestrate debate rounds (moderator), evaluate conditions
(gate), and load tone profiles for downstream agents.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)


def moderator_node_factory(
    node_id: str,
    resolved_config: dict,
    threshold: float = 0.7,
) -> Callable[[WorkflowState], dict]:
    """Create a moderator node that also evaluates consensus.

    Same as ``agent_node_factory`` but additionally computes a consensus
    score, increments ``current_round``, and publishes SSE events.
    """
    from backend.workflow.nodes.agent_nodes import agent_node_factory

    base_fn = agent_node_factory(node_id, "wf-moderator", resolved_config)

    async def _moderator_node(state: WorkflowState) -> dict:
        result = await base_fn(state)

        # Transactional Drafting: evaluate from pragmatist_output if present
        num_outputs = len(state.get("node_outputs", [])) + len(result.get("node_outputs", []))
        pragmatist_output = state.get("pragmatist_output")
        if pragmatist_output:
            reality_score = pragmatist_output.get("reality_score", 0.0)
            blocking_concerns = pragmatist_output.get("blocking_concerns", [])
            approved = reality_score >= 0.6 and not blocking_concerns
            consensus = reality_score
            verdict = "approved" if approved else "revision_required"
            result["consensus_result"] = {
                "verdict": verdict,
                "reality_score": reality_score,
                "blocking_concerns": blocking_concerns,
            }
            # Increment draft_version on revision (loop detection)
            current_dv = state.get("draft_version", 1)
            if verdict == "revision_required":
                result["draft_version"] = current_dv + 1
        else:
            # Standard debate: simple consensus heuristic based on draft length
            current_draft = result.get("current_draft", state.get("current_draft", ""))
            draft_length = len(current_draft)
            consensus = min(1.0, (num_outputs * 0.15) + (draft_length / 10000))

        current_round = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 10)
        next_round = current_round + 1

        # Safety cap: if we've exceeded max_rounds, log a warning and cap
        # This is a belt-and-suspenders check in addition to route_feedback
        if current_round > max_rounds + 1:
            logger.warning(
                "Moderator (node %s): current_round=%d exceeds max_rounds=%d — forcing round cap to prevent infinite loop",
                node_id,
                current_round,
                max_rounds,
            )
            next_round = current_round  # Don't increment further

        session_id = state.get("session_id", "")
        await publish_async(
            session_id,
            "consensus.reached",
            {
                "score": round(consensus, 2),
                "threshold": threshold,
                "round": current_round,
            },
        )

        # Publish round update for UI
        total_tokens = sum(no.get("tokens_used", 0) for no in state.get("node_outputs", []) + result.get("node_outputs", []))
        await publish_async(
            session_id,
            "round_update",
            {
                "type": "round_update",
                "round": current_round,
                "consensus": round(consensus, 2),
                "threshold": threshold,
                "agent_count": num_outputs,
                "total_tokens": total_tokens,
            },
        )

        result["final_consensus"] = round(consensus, 2)
        # Increment current_round so the feedback router can cap at max_rounds
        result["current_round"] = next_round

        # --- Extract final assessment, usability score, remaining blockers ---
        # Get moderator's own LLM output text from the base agent's result
        mod_outputs = result.get("node_outputs", [])
        final_assessment = ""
        for o in mod_outputs:
            c = o.get("content", "")
            if c and not c.startswith("["):
                final_assessment = c
                break
        result["final_assessment"] = final_assessment

        if pragmatist_output:
            result["usability_score"] = pragmatist_output.get("reality_score")
            result["remaining_blockers"] = pragmatist_output.get("blocking_concerns", [])
        else:
            result["usability_score"] = round(consensus, 2)
            result["remaining_blockers"] = []

        # --- Extension request (extra rounds) for MVP debates ---
        enable_extra = state.get("enable_extra_rounds", False)
        if enable_extra and current_round >= max_rounds and current_round <= max_rounds + 2:
            extension_granted = state.get("extension_granted")
            if extension_granted is None and consensus < threshold:
                debate_id = state.get("debate_id", "")
                session_id = state.get("session_id", "")
                project_id = state.get("project_id", "")
                logger.info(
                    "Moderator: requesting extension for debate %s (round %d/%d, consensus=%.2f)",
                    debate_id,
                    current_round,
                    max_rounds,
                    consensus,
                )

                # Publish SSE event for the frontend
                await publish_async(
                    session_id,
                    "extension_request",
                    {
                        "type": "extension_request",
                        "debate_id": debate_id,
                        "session_id": session_id,
                        "current_consensus": round(consensus, 3),
                        "threshold": threshold,
                        "current_round": current_round,
                        "max_rounds": max_rounds,
                    },
                )

                # Poll debate store for user decision (up to 5 minutes)
                if debate_id:
                    from backend.api.deps import get_debate_store_for_project
                    from backend.persistence.project_store import ProjectStore
                    from backend.workflow.workflow_runner import is_cancelled

                    project_store = ProjectStore()
                    try:
                        debate_store = get_debate_store_for_project(project_id, project_store)
                        poll_deadline = time.monotonic() + 300  # 5 min timeout
                        while time.monotonic() < poll_deadline:
                            if is_cancelled(session_id):
                                logger.info("Extension poll cancelled for session %s", session_id)
                                result["extension_granted"] = False
                                break
                            debate = debate_store.get(debate_id)
                            if debate and debate.get("extension_granted") is not None:
                                result["extension_granted"] = debate["extension_granted"]
                                logger.info(
                                    "Extension decision received: %s",
                                    "granted" if result["extension_granted"] else "denied",
                                )
                                break
                            await asyncio.sleep(2)
                        else:
                            # Timeout — treat as denied
                            logger.info("Extension poll timed out for debate %s — denying", debate_id)
                            result["extension_granted"] = False
                    except Exception:
                        logger.warning("Extension poll failed for debate %s", debate_id, exc_info=True)
                        result["extension_granted"] = False

        logger.info(
            "Moderator (node %s, round %d): consensus=%.2f, next_round=%d, max_rounds=%d",
            node_id,
            current_round,
            consensus,
            next_round,
            max_rounds,
        )

        return result

    return _moderator_node


def gate_node_factory(
    node_id: str,
    condition_expr: str = "",
) -> Callable[[WorkflowState], dict]:
    """Create a gate node that evaluates a condition.

    The gate node itself doesn't route — routing is handled by
    ``workflow_routers.route_conditional()``.  This function just
    publishes SSE events and records the gate evaluation.

    Args:
        node_id: The workflow node ID.
        condition_expr: The condition expression (for logging).
    """

    async def _gate_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-gate",
                "round": current_round,
            },
        )

        # Evaluate condition for logging
        condition_result = False
        try:
            if condition_expr:
                condition_result = bool(
                    eval(condition_expr, {"__builtins__": {}}, dict(state))  # noqa: S307
                )
        except Exception as exc:
            logger.warning("Gate condition '%s' raised: %s", condition_expr, exc)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-gate",
            "role": "gate",
            "content": f"Gate evaluated: {condition_expr} → {condition_result}",
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "completed",
        }

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-gate",
                "role": "gate",
                "content": output["content"],
                "tokens_used": 0,
                "duration_ms": 0,
            },
        )

        # --- Audit log ---
        try:
            get_audit_logger().log_node_execution(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=node_id,
                actor="gate",
                input_data={"condition": condition_expr},
                output_data={"result": condition_result},
            )
        except Exception:
            logger.debug("Audit logging failed for gate_node %s", node_id, exc_info=True)

        return {"node_outputs": [output]}

    return _gate_node


def tone_profile_node_factory(
    node_id: str,
    node_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create a tone profile node function.

    Loads the ToneProfile (from catalog or inline) and writes it into
    ``state["tone_profiles"][node_id]``.  No LLM call, no output.

    Args:
        node_id: The workflow node ID.
        node_config: The node config dict with keys ``tone_profile_id``
            or ``inline_profile``.
    """
    from backend.blueprints.models import ToneProfile
    from backend.blueprints.repository import BlueprintRepository

    tone_profile_id = node_config.get("tone_profile_id")
    inline_profile_data = node_config.get("inline_profile")

    async def _tone_profile_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-tone-profile",
                "role": "tone-profile",
            },
        )

        profile: ToneProfile | None = None

        if tone_profile_id:
            # Load from catalog
            try:
                repo = BlueprintRepository()
                profile = repo.get_tone_profile(tone_profile_id)
                if profile is None:
                    logger.warning("ToneProfile '%s' not found in catalog", tone_profile_id)
            except Exception as exc:
                logger.error("Failed to load ToneProfile '%s': %s", tone_profile_id, exc)

        elif inline_profile_data:
            # Use inline profile
            try:
                if isinstance(inline_profile_data, dict):
                    profile = ToneProfile.model_validate(inline_profile_data)
                else:
                    profile = inline_profile_data
            except Exception as exc:
                logger.error("Failed to parse inline ToneProfile: %s", exc)

        # Update tone_profiles in state
        tone_profiles = dict(state.get("tone_profiles", {}))
        if profile is not None:
            tone_profiles[node_id] = profile.model_dump()

        output = {
            "node_id": node_id,
            "node_type": "wf-tone-profile",
            "role": "tone-profile",
            "content": f"Tone profile loaded: {profile.name if profile else 'none'}",
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "completed" if profile else "failed",
        }

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-tone-profile",
                "role": "tone-profile",
                "content": output["content"],
                "tokens_used": 0,
                "duration_ms": 0,
            },
        )

        # --- Audit log ---
        try:
            get_audit_logger().log_node_execution(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=node_id,
                actor="tone-profile",
                input_data={"tone_profile_id": tone_profile_id},
                output_data={"profile_name": profile.name if profile else None},
            )
        except Exception:
            logger.debug("Audit logging failed for tone_profile_node %s", node_id, exc_info=True)

        return {
            "tone_profiles": tone_profiles,
            "node_outputs": [output],
        }

    return _tone_profile_node
