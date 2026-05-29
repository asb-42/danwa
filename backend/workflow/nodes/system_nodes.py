"""System-level node functions for LangGraph workflow execution.

Input, initialize, complete, and interjection nodes that manage the
workflow lifecycle without making LLM calls.
"""

from __future__ import annotations

import logging

from backend.api.events import publish_async
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)


async def input_node(state: WorkflowState) -> dict:
    """Input node — sets the context from the workflow input.

    No LLM call.  Simply passes through the user's case text.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-input")

    await publish_async(
        session_id,
        "node.start",
        {
            "node_id": node_id,
            "node_type": "wf-input",
            "round": state.get("current_round", 1),
        },
    )

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-input",
        "role": "input",
        "content": state.get("context", ""),
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(
        session_id,
        "node.complete",
        {
            "node_id": node_id,
            "node_type": "wf-input",
            "role": "input",
            "content": output["content"][:200],
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

    await publish_async(
        session_id,
        "node.start",
        {
            "node_id": node_id,
            "node_type": "wf-initialize",
            "round": 1,
        },
    )

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-initialize",
        "role": "initialize",
        "content": "Workflow initialized",
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(
        session_id,
        "node.complete",
        {
            "node_id": node_id,
            "node_type": "wf-initialize",
            "role": "initialize",
            "content": "Workflow initialized",
            "tokens_used": 0,
            "duration_ms": 0,
        },
    )

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
    """Complete node — assembles final output and marks workflow as done.

    For Transactional Drafting, includes constructivity_score, draft_version,
    consensus_result, and pragmatist reality_score in the final output.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-complete")

    final_output = state.get("current_draft", "")

    # --- Transactional Drafting metadata ---
    consensus_result = state.get("consensus_result")
    constructivity_score = state.get("constructivity_score", 0.0)
    draft_version = state.get("draft_version", 1)
    pragmatist_output = state.get("pragmatist_output")
    reality_score = pragmatist_output.get("reality_score", 0.0) if pragmatist_output else 0.0

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-complete",
        "role": "complete",
        "content": final_output,
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(
        session_id,
        "workflow.complete",
        {
            "session_id": session_id,
            "total_rounds": state.get("current_round", 1),
            "final_consensus": state.get("final_consensus", 0.0),
            "constructivity_score": constructivity_score,
            "reality_score": reality_score,
            "draft_version": draft_version,
            "consensus_verdict": consensus_result.get("verdict") if consensus_result else None,
        },
    )

    # --- Audit log ---
    try:
        metadata = {
            "consensus": state.get("final_consensus", 0.0),
            "constructivity_score": constructivity_score,
            "reality_score": reality_score,
            "draft_version": draft_version,
        }
        if consensus_result:
            metadata["consensus_verdict"] = consensus_result.get("verdict")
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            event_type="workflow_completed",
            actor="system",
            metadata=metadata,
        )
    except Exception:
        logger.debug("Audit logging failed for complete_wf_node", exc_info=True)

    # Only include transactional_drafting fields in output if they carry data
    result: dict = {
        "output": final_output,
        "status": "completed",
        "node_outputs": [output],
    }
    if consensus_result or constructivity_score > 0.0 or draft_version > 1:
        result["constructivity_score"] = constructivity_score
        result["draft_version"] = draft_version
        result["reality_score"] = reality_score
        if consensus_result:
            result["consensus_result"] = consensus_result
    return result


async def interjection_node(state: WorkflowState) -> dict:
    """Interjection node — consumes queued user input or pauses.

    If there are pending interjections in the queue, consumes them and
    appends to the state.  If the queue is empty, sets ``is_paused=True``
    to signal the execution engine to pause and wait for user input.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-user-injection")

    await publish_async(
        session_id,
        "node.start",
        {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "round": state.get("current_round", 1),
        },
    )

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

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-user-injection",
                "role": "user-injection",
                "content": combined_content[:500],
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

        await publish_async(
            session_id,
            "workflow.paused",
            {
                "session_id": session_id,
                "current_node_id": node_id,
            },
        )

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
