"""Workflow runner — background execution of compiled workflow graphs.

Handles the lifecycle of a workflow execution: invoke the LangGraph graph,
manage pause/resume/cancel, save state snapshots, and publish SSE events.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from backend.api.events import publish_async
from backend.models.artifact import (
    DebateArtifact,
    Injection,
    Turn,
)
from backend.services.artifact_store import ArtifactStore
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.immutability import lock_session
from backend.workflow.interjection import interjection_service
from backend.workflow.state_snapshot import StateSnapshotStore
from backend.workflow.workflow_compiler import CompiledWorkflow

logger = logging.getLogger(__name__)

# Module-level shared state for pause/resume/cancel
_pause_events: dict[str, asyncio.Event] = {}
_cancelled_sessions: set[str] = set()
_session_status: dict[str, str] = {}  # session_id → status string


def is_cancelled(session_id: str) -> bool:
    """Check if a session has been cancelled."""
    return session_id in _cancelled_sessions


def cancel_session(session_id: str) -> None:
    """Mark a session as cancelled."""
    _cancelled_sessions.add(session_id)
    _session_status[session_id] = "cancelled"


def get_session_status(session_id: str) -> str:
    """Get the current status of a session."""
    return _session_status.get(session_id, "unknown")


def set_session_status(session_id: str, status: str) -> None:
    """Set the status of a session."""
    _session_status[session_id] = status


def get_pause_event(session_id: str) -> asyncio.Event:
    """Get or create the pause event for a session."""
    if session_id not in _pause_events:
        _pause_events[session_id] = asyncio.Event()
        _pause_events[session_id].set()  # Not paused by default
    return _pause_events[session_id]


def pause_session(session_id: str) -> None:
    """Pause a running session."""
    event = get_pause_event(session_id)
    event.clear()  # Block until resumed
    _session_status[session_id] = "paused"
    # --- Audit log ---
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id="",
            workflow_version=1,
            event_type="workflow_paused",
            actor="user",
        )
    except Exception:
        logger.debug("Audit logging failed for pause_session", exc_info=True)


def resume_session(session_id: str) -> None:
    """Resume a paused session."""
    event = get_pause_event(session_id)
    event.set()  # Unblock
    _session_status[session_id] = "running"
    # --- Audit log ---
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id="",
            workflow_version=1,
            event_type="workflow_resumed",
            actor="user",
        )
    except Exception:
        logger.debug("Audit logging failed for resume_session", exc_info=True)


async def run_workflow_background(
    session_id: str,
    workflow_id: str,
    project_id: str,
    initial_state: dict[str, Any],
    compiled_workflow: CompiledWorkflow,
    snapshot_store: StateSnapshotStore,
) -> None:
    """Run a compiled workflow graph as a background task.

    This is the main execution loop for workflow-based debates.

    Args:
        session_id: Unique session identifier for this execution.
        workflow_id: The workflow definition ID.
        project_id: The project ID.
        initial_state: The initial WorkflowState dict.
        compiled_workflow: The compiled LangGraph graph and metadata.
        snapshot_store: Store for persisting state snapshots.
    """
    set_session_status(session_id, "running")

    # Publish workflow.started event
    await publish_async(
        session_id,
        "workflow.started",
        {
            "type": "workflow.started",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "node_sequence": compiled_workflow.node_sequence,
        },
    )

    start_time = time.monotonic()

    try:
        graph = compiled_workflow.graph

        # Invoke the compiled graph
        # The graph will call node functions which publish their own SSE events
        final_state = await graph.ainvoke(initial_state)

        # Save final snapshot
        snapshot_store.save(
            session_id=session_id,
            workflow_id=workflow_id,
            node_id="__final__",
            node_type="final",
            round_number=final_state.get("current_round", 0),
            state_dict=_serialize_state(final_state),
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # --- Build and save DebateArtifact for Output Composer ---
        try:
            artifact = _build_artifact_from_state(
                session_id=session_id,
                workflow_id=workflow_id,
                state=final_state,
                duration_ms=duration_ms,
            )
            ArtifactStore().save(artifact)
        except Exception:
            logger.warning(
                "Failed to build/save DebateArtifact for session %s",
                session_id,
                exc_info=True,
            )

        # Publish workflow.complete event
        await publish_async(
            session_id,
            "workflow.complete",
            {
                "type": "workflow.complete",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "output": final_state.get("output", ""),
                "final_consensus": final_state.get("final_consensus", 0.0),
                "duration_ms": duration_ms,
                "node_outputs": final_state.get("node_outputs", []),
            },
        )

        set_session_status(session_id, "completed")

        # --- Auto-lock session and snapshots ---
        try:
            lock_session(session_id)
        except Exception:
            logger.warning("Failed to lock session %s", session_id, exc_info=True)

        # --- Audit log ---
        try:
            get_audit_logger().log_workflow_event(
                session_id=session_id,
                workflow_id=workflow_id,
                workflow_version=initial_state.get("workflow_version", 1),
                event_type="workflow_completed",
                actor="system",
                metadata={"duration_ms": duration_ms},
            )
        except Exception:
            logger.debug("Audit logging failed for workflow_completed", exc_info=True)

        logger.info(
            "Workflow %s completed for session %s in %dms",
            workflow_id,
            session_id,
            duration_ms,
        )

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Workflow %s failed for session %s: %s",
            workflow_id,
            session_id,
            exc,
            exc_info=True,
        )

        # Publish node.error event
        await publish_async(
            session_id,
            "node.error",
            {
                "type": "node.error",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "error": str(exc),
                "duration_ms": duration_ms,
            },
        )

        set_session_status(session_id, "failed")

        # --- Auto-lock session and snapshots ---
        try:
            lock_session(session_id)
        except Exception:
            logger.warning("Failed to lock session %s", session_id, exc_info=True)

        # --- Audit log ---
        try:
            get_audit_logger().log_workflow_event(
                session_id=session_id,
                workflow_id=workflow_id,
                workflow_version=initial_state.get("workflow_version", 1),
                event_type="workflow_failed",
                actor="system",
                metadata={"error": str(exc), "duration_ms": duration_ms},
            )
        except Exception:
            logger.debug("Audit logging failed for workflow_failed", exc_info=True)

    finally:
        # Cleanup shared state
        _pause_events.pop(session_id, None)
        _cancelled_sessions.discard(session_id)
        await interjection_service.clear(session_id)


def _serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Serialize WorkflowState for snapshot storage.

    Converts non-JSON-serializable values to strings.
    """
    serialized: dict[str, Any] = {}
    for key, value in state.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            serialized[key] = value
        elif isinstance(value, list):
            serialized[key] = [str(item) if not isinstance(item, (str, int, float, bool, dict, type(None))) else item for item in value]
        elif isinstance(value, dict):
            serialized[key] = {k: str(v) for k, v in value.items()}
        else:
            serialized[key] = str(value)
    return serialized


def _build_artifact_from_state(
    *,
    session_id: str,
    workflow_id: str,
    state: dict[str, Any],
    duration_ms: int = 0,
) -> DebateArtifact:
    """Build a ``DebateArtifact`` from the final workflow state.

    Extracts transcript turns, interjections, user queries, and
    metadata from the LangGraph state dict.  This is the bridge
    between the workflow execution layer and the Output Composer.
    """
    from datetime import UTC, datetime

    # Build turns from node_outputs
    turns: list[Turn] = []
    for output in state.get("node_outputs", []):
        turns.append(
            Turn(
                node_id=output.get("node_id", ""),
                round=output.get("round", 0),
                agent_name=output.get("role", ""),
                role_type=output.get("node_type", ""),
                content=output.get("content", ""),
                latency_ms=output.get("duration_ms", 0),
                token_usage={"total": output.get("tokens_used", 0)},
            )
        )

    # Build interjections from consumed_interjections
    interjections: list[Injection] = []
    for ij in state.get("consumed_interjections", []):
        if isinstance(ij, dict):
            interjections.append(
                Injection(
                    id=ij.get("interjection_id", ""),
                    source=ij.get("source", "user"),
                    target_node_id=ij.get("target_node_id", ""),
                    content=ij.get("content", ""),
                )
            )

    # Build tone profile snapshot
    tone_snapshot = state.get("tone_profiles", {})

    # Metadata
    now = datetime.now(UTC)
    metadata: dict[str, Any] = {
        "token_usage": {
            "total": sum(t.token_usage.get("total", 0) for t in turns),
        },
        "timestamps": {
            "end": now.isoformat(),
        },
        "duration_ms": duration_ms,
    }

    return DebateArtifact(
        session_id=session_id,
        workflow_id=workflow_id,
        workflow_version=state.get("workflow_version", 1),
        workflow_name=state.get("workflow_name", ""),
        topic=state.get("context", ""),
        tone_profile_snapshot=tone_snapshot,
        transcript=turns,
        interjections=interjections,
        consensus_result={
            "score": state.get("final_consensus", 0.0),
            "summary": state.get("output", ""),
        },
        metadata=metadata,
    )
