"""Node functions for LangGraph workflow execution.

Each function (or factory) produces a partial state update dict that LangGraph
merges into the shared ``WorkflowState``.  Agent nodes resolve their
``AgentBlueprint`` at runtime and call the LLM via ``LLMService``.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

from backend.api.events import publish_async
from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService
from backend.services.prompt_service import PromptService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level service singletons (lazy-initialized)
# ---------------------------------------------------------------------------

_profile_service: ProfileService | None = None
_prompt_service: PromptService | None = None


def _get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service


def _get_prompt_service() -> PromptService:
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


# ---------------------------------------------------------------------------
# Simple node functions
# ---------------------------------------------------------------------------


async def input_node(state: WorkflowState) -> dict:
    """Input node — sets the context from the workflow input.

    No LLM call.  Simply passes through the user's case text.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-input")

    await publish_async(session_id, "node.start", {
        "node_id": node_id,
        "node_type": "wf-input",
        "round": state.get("current_round", 1),
    })

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-input",
        "role": "input",
        "content": state.get("context", ""),
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(session_id, "node.complete", {
        "node_id": node_id,
        "node_type": "wf-input",
        "role": "input",
        "content": output["content"][:200],
        "tokens_used": 0,
        "duration_ms": 0,
    })

    # --- Audit log ---
    try:
        get_audit_logger().log_node_execution(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            node_id=node_id,
            actor="input",
            input_data={"context": state.get("context", "")},
            output_data=output,
        )
    except Exception:
        logger.debug("Audit logging failed for input_node", exc_info=True)

    return {
        "node_outputs": [output],
        "current_draft": state.get("context", ""),
    }


async def initialize_wf_node(state: WorkflowState) -> dict:
    """Initialize node — resets runtime state for a new workflow execution.

    Sets ``current_round=1``, clears accumulators.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-initialize")

    await publish_async(session_id, "node.start", {
        "node_id": node_id,
        "node_type": "wf-initialize",
        "round": 1,
    })

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-initialize",
        "role": "initialize",
        "content": "Workflow initialized",
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(session_id, "node.complete", {
        "node_id": node_id,
        "node_type": "wf-initialize",
        "role": "initialize",
        "content": "Workflow initialized",
        "tokens_used": 0,
        "duration_ms": 0,
    })

    # --- Audit log ---
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            event_type="workflow_started",
            actor="system",
        )
    except Exception:
        logger.debug("Audit logging failed for initialize_wf_node", exc_info=True)

    return {
        "current_round": 1,
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "node_outputs": [output],
    }


async def complete_wf_node(state: WorkflowState) -> dict:
    """Complete node — assembles final output and marks workflow as done."""
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-complete")

    final_output = state.get("current_draft", "")

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-complete",
        "role": "complete",
        "content": final_output[:500],
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(session_id, "workflow.complete", {
        "session_id": session_id,
        "total_rounds": state.get("current_round", 1),
        "final_consensus": state.get("final_consensus", 0.0),
    })

    # --- Audit log ---
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            event_type="workflow_completed",
            actor="system",
            metadata={"consensus": state.get("final_consensus", 0.0)},
        )
    except Exception:
        logger.debug("Audit logging failed for complete_wf_node", exc_info=True)

    return {
        "output": final_output,
        "status": "completed",
        "node_outputs": [output],
    }


# ---------------------------------------------------------------------------
# Agent node factory
# ---------------------------------------------------------------------------


def agent_node_factory(
    node_id: str,
    node_type: str,
    resolved_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create an agent node function for a workflow node.

    Args:
        node_id: The workflow node ID (e.g. ``"node_strategist_1"``).
        node_type: The node type (e.g. ``"wf-strategist"``).
        resolved_config: Dict with keys ``blueprint_id``, ``blueprint_name``,
            ``llm_profile_id``, ``llm_model``, ``role_definition_id``,
            ``role``, ``prompt_template_id``.

    Returns:
        An async callable that takes ``WorkflowState`` and returns a partial
        state update dict.
    """
    role = resolved_config.get("role", node_type.replace("wf-", ""))
    llm_profile_id = resolved_config.get("llm_profile_id", "")
    blueprint_name = resolved_config.get("blueprint_name", role)

    async def _agent_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        # --- Publish: node started ---
        await publish_async(session_id, "node.start", {
            "node_id": node_id,
            "node_type": node_type,
            "role": role,
            "round": current_round,
        })

        # --- Build system prompt ---
        system_prompt = _resolve_system_prompt(resolved_config, state)

        # --- Build user prompt ---
        context = state.get("context", "")
        current_draft = state.get("current_draft", "")
        language = state.get("language", "de")

        user_prompt = f"Case: {context}"
        if current_draft:
            user_prompt += f"\n\nCurrent draft:\n{current_draft}"

        # Inject pending interjections
        interjections = state.get("interjection_queue", [])
        if interjections:
            inj_text = "\n\n--- ADDITIONAL CONTEXT (User) ---\n"
            inj_text += "\n".join(f"- {inj['content']}" for inj in interjections)
            user_prompt += inj_text

        if language == "en":
            user_prompt += "\n\nPlease respond in English."
        else:
            user_prompt += "\n\nBitte antworte auf Deutsch."

        # --- LLM call ---
        content = ""
        tokens_used = 0
        duration_ms = 0
        status = "completed"

        try:
            llm_service = LLMService(
                profile_id=llm_profile_id,
                profile_service=_get_profile_service(),
            )
            gen_result = await llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            content = gen_result.content
            tokens_used = gen_result.tokens_out if gen_result.tokens_out > 0 else len(content.split())
            duration_ms = gen_result.duration_ms

            logger.info(
                "Agent %s (node %s, round %d): LLM response (%d tokens, %dms)",
                role, node_id, current_round, tokens_used, duration_ms,
            )

        except Exception as exc:
            logger.error(
                "Agent %s (node %s, round %d): LLM call FAILED: %s",
                role, node_id, current_round, exc, exc_info=True,
            )
            content = f"[{role}] Round {current_round}: LLM call failed ({exc})"
            tokens_used = len(content.split())
            status = "failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": node_type,
            "role": role,
            "content": content,
            "tokens_used": tokens_used,
            "duration_ms": elapsed_ms,
            "status": status,
        }

        # --- Publish: node completed ---
        await publish_async(session_id, "node.complete", {
            "node_id": node_id,
            "node_type": node_type,
            "role": role,
            "content": content[:500],
            "tokens_used": tokens_used,
            "duration_ms": elapsed_ms,
        })

        # --- Audit log ---
        try:
            al = get_audit_logger()
            if status == "failed":
                al.log_node_failed(
                    session_id=session_id,
                    workflow_id=state.get("workflow_id", ""),
                    workflow_version=state.get("workflow_version", 1),
                    node_id=node_id,
                    actor=role,
                    error=content,
                )
            else:
                al.log_node_execution(
                    session_id=session_id,
                    workflow_id=state.get("workflow_id", ""),
                    workflow_version=state.get("workflow_version", 1),
                    node_id=node_id,
                    actor=role,
                    input_data={"system_prompt": system_prompt, "user_prompt": user_prompt},
                    output_data={"content": content, "tokens_used": tokens_used},
                    llm_profile_id=llm_profile_id,
                    latency_ms=duration_ms,
                    prompt_tokens=0,
                    completion_tokens=tokens_used,
                )
        except Exception:
            logger.debug("Audit logging failed for agent_node %s", node_id, exc_info=True)

        return {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "current_draft": state.get("current_draft", "") + "\n" + content,
        }

    return _agent_node


def moderator_node_factory(
    node_id: str,
    resolved_config: dict,
    threshold: float = 0.7,
) -> Callable[[WorkflowState], dict]:
    """Create a moderator node that also evaluates consensus.

    Same as ``agent_node_factory`` but additionally computes a consensus
    score and publishes a ``consensus.reached`` SSE event.
    """
    base_fn = agent_node_factory(node_id, "wf-moderator", resolved_config)

    async def _moderator_node(state: WorkflowState) -> dict:
        result = await base_fn(state)

        # Simple consensus heuristic: based on draft length stability
        # In a real implementation, this would use LLM-based evaluation
        current_draft = result.get("current_draft", state.get("current_draft", ""))
        draft_length = len(current_draft)
        # Heuristic: longer drafts with more contributions = higher consensus
        num_outputs = len(state.get("node_outputs", [])) + len(result.get("node_outputs", []))
        consensus = min(1.0, (num_outputs * 0.15) + (draft_length / 10000))

        session_id = state.get("session_id", "")
        await publish_async(session_id, "consensus.reached", {
            "score": round(consensus, 2),
            "threshold": threshold,
            "round": state.get("current_round", 1),
        })

        result["final_consensus"] = round(consensus, 2)
        return result

    return _moderator_node


# ---------------------------------------------------------------------------
# Gate node factory
# ---------------------------------------------------------------------------


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

        await publish_async(session_id, "node.start", {
            "node_id": node_id,
            "node_type": "wf-gate",
            "round": current_round,
        })

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

        await publish_async(session_id, "node.complete", {
            "node_id": node_id,
            "node_type": "wf-gate",
            "role": "gate",
            "content": output["content"],
            "tokens_used": 0,
            "duration_ms": 0,
        })

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


# ---------------------------------------------------------------------------
# Interjection node
# ---------------------------------------------------------------------------


async def interjection_node(state: WorkflowState) -> dict:
    """Interjection node — consumes queued user input or pauses.

    If there are pending interjections in the queue, consumes them and
    appends to the state.  If the queue is empty, sets ``is_paused=True``
    to signal the execution engine to pause and wait for user input.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-user-injection")

    await publish_async(session_id, "node.start", {
        "node_id": node_id,
        "node_type": "wf-user-injection",
        "round": state.get("current_round", 1),
    })

    queue = state.get("interjection_queue", [])

    if queue:
        # Consume all pending interjections
        consumed_ids = [item.get("id", "") for item in queue]
        combined_content = "\n".join(item.get("content", "") for item in queue)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "role": "user-injection",
            "content": combined_content,
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "completed",
        }

        await publish_async(session_id, "node.complete", {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "role": "user-injection",
            "content": combined_content[:500],
            "tokens_used": 0,
            "duration_ms": 0,
        })

        # --- Audit log ---
        try:
            get_audit_logger().log_node_execution(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=node_id,
                actor="user",
                input_data={"interjection_count": len(queue)},
                output_data={"consumed_ids": consumed_ids, "content": combined_content},
            )
        except Exception:
            logger.debug("Audit logging failed for interjection_node", exc_info=True)

        return {
            "interjection_queue": [],  # Clear the queue
            "consumed_interjections": consumed_ids,
            "node_outputs": [output],
            "current_draft": state.get("current_draft", "") + "\n" + combined_content,
        }
    else:
        # No interjections pending — pause execution
        logger.info("Interjection node %s: no pending input, pausing", node_id)

        await publish_async(session_id, "workflow.paused", {
            "session_id": session_id,
            "current_node_id": node_id,
        })

        output_pause: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "role": "user-injection",
            "content": "[Paused — waiting for user input]",
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "pending",
        }

        # --- Audit log ---
        try:
            get_audit_logger().log_workflow_event(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                event_type="workflow_paused",
                actor="system",
                metadata={"node_id": node_id, "reason": "no_pending_interjections"},
            )
        except Exception:
            logger.debug("Audit logging failed for interjection_node pause", exc_info=True)

        return {
            "is_paused": True,
            "node_outputs": [output_pause],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_system_prompt(resolved_config: dict, state: WorkflowState) -> str:
    """Resolve the system prompt for an agent node from its config."""
    role = resolved_config.get("role", "agent")
    prompt_template_id = resolved_config.get("prompt_template_id")

    if prompt_template_id:
        try:
            prompt_service = _get_prompt_service()
            template = prompt_service.get_template(prompt_template_id)
            if template:
                return template.get("content", f"You are a {role}.")
        except Exception as exc:
            logger.warning("Failed to resolve prompt template '%s': %s", prompt_template_id, exc)

    # Fallback: generic system prompt based on role
    role_prompts = {
        "strategist": "You are a strategic analyst. Analyze the case and provide a structured initial assessment.",
        "critic": "You are a critical reviewer. Identify weaknesses, gaps, and potential issues in the analysis.",
        "optimizer": "You are an optimization expert. Refine and improve the draft by addressing the critiques.",
        "moderator": "You are a debate moderator. Synthesize all contributions and evaluate consensus.",
    }
    return role_prompts.get(role, f"You are a {role} participating in a structured debate.")
