"""System-level node functions for LangGraph workflow execution.

Input, initialize, complete, and interjection nodes that manage the
workflow lifecycle without making LLM calls.
"""

from __future__ import annotations

import logging

from backend.api.events import publish_async
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.interjection import interjection_service
from backend.workflow.nodes._draft_helpers import truncate_running_draft
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

    # Reconstruct final output from all node outputs instead of the
    # truncated current_draft — preserves full debate text for export
    node_outputs = state.get("node_outputs", [])
    final_parts: list[str] = []
    for no in node_outputs:
        r = no.get("role", "")
        rnd = no.get("round", "")
        c = no.get("content", "")
        if r and c:
            header = f"[{r.upper()} Round {rnd}]" if rnd else f"[{r.upper()}]"
            final_parts.append(f"\n\n{header}\n{c}")
    final_output = "".join(final_parts) if final_parts else state.get("current_draft", "")

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

    # Only include Transactional-Drafting fields in output if they carry data
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

    Behaviour
    ---------
    1. If the in-state ``interjection_queue`` has items, drain them and
       continue (legacy / engine-injected path).
    2. Otherwise, also pull from the module-level
       :data:`interjection_service` (the path used by the API
       ``POST /sessions/{id}/interject`` endpoint).  This makes the
       node robust to items arriving *after* the previous node finished
       but *before* the engine reached this interjection point.
    3. If both sources are empty **and** the state carries a positive
       ``pause_timeout``, block on the service queue's wake-up event
       so the workflow actually waits for human input instead of
       immediately setting ``is_paused=True`` and racing the resume
       handler.
    4. If nothing arrived within ``pause_timeout`` (or the state has
       no ``pause_timeout`` set), fall back to the legacy behaviour of
       setting ``is_paused=True`` and emitting ``workflow.paused``.
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

    # Step 1: legacy in-state queue.
    queue: list[dict] = list(state.get("interjection_queue", []))

    # Step 2: pull anything the API has already submitted.  This is
    # non-blocking — if there is nothing, we move on to step 3.
    service_items = await interjection_service.consume(session_id, node_id)
    for item in service_items:
        queue.append(
            {
                "id": item.get("interjection_id", ""),
                "content": item.get("content", ""),
                "source": item.get("source", "user"),
                "metadata": item.get("metadata", {}),
            }
        )

    # Step 3: if both sources were empty, optionally block waiting for
    # the user to submit something.  pause_timeout=0 (the default for
    # tests and pre-existing callers) keeps the old "set is_paused
    # immediately" behaviour intact.
    pause_timeout = float(state.get("pause_timeout", 0.0) or 0.0)
    if not queue and pause_timeout > 0:
        blocked = await interjection_service.consume_blocking(session_id, node_id, timeout=pause_timeout)
        for item in blocked:
            queue.append(
                {
                    "id": item.get("interjection_id", ""),
                    "content": item.get("content", ""),
                    "source": item.get("source", "user"),
                    "metadata": item.get("metadata", {}),
                }
            )

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
            # Sprint 39 (H2 fix): bound the running ``current_draft``
            # log via the shared helper.  Previously the
            # interjection node accumulated without any cap, so a
            # long debate with many interjections would grow the
            # draft without bound and bloat every subsequent
            # agent's user prompt.  See ``_draft_helpers.py`` for
            # the tail-only truncation semantics.
            "current_draft": truncate_running_draft(state.get("current_draft", "") + "\n" + combined_content),
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
                metadata={
                    "node_id": node_id,
                    "reason": "no_pending_interjections",
                    "pause_timeout": pause_timeout,
                },
            )
        except Exception:
            logger.debug("Audit logging failed for interjection_node pause", exc_info=True)

        return {
            "is_paused": True,
            "node_outputs": [output_pause],
        }
