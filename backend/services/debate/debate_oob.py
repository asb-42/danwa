"""Cancellation flags and Out-of-Band (OOB) input queues for debates.

Sprint 37 (part 3/3) — the cancellation flag (``is_cancelled`` /
``mark_cancelled`` / ``clear_cancel``) now delegates to
:func:`backend.state.workflow_state.get_workflow_state`, the same
backend used by ``workflow_runner`` and the ``WorkflowStateBackend``
protocol.  All three sources of truth are now a single object.

The OOB input queue (``enqueue_oob`` / ``consume_oob`` /
``get_oob_for_debate`` / ``clear_oob_queue``) is a different concern
— a per-debate message list, not a flag — and is intentionally kept
as module-local state for now.  A follow-up sprint should add a
queue backend to ``backend.state`` so the OOB pipeline can survive
multi-worker deployments.
"""

from __future__ import annotations

from backend.state.workflow_state import get_workflow_state

# ---------------------------------------------------------------------------
# OOB (Out-of-Band) input queue — module-local for now
# ---------------------------------------------------------------------------
#
# A simple per-debate list of interjection messages.  Not yet
# cross-process; each worker sees its own queue.  Follow-up:
# promote to a queue backend in ``backend.state``.
_oob_queues: dict[str, list[dict]] = {}


def get_oob_for_debate(debate_id: str) -> list[dict]:
    """Get all pending OOB inputs for a debate (used by workflow nodes)."""
    return [oob for oob in _oob_queues.get(debate_id, []) if oob["status"] == "pending"]


def consume_oob(debate_id: str, oob_ids: list[str]) -> None:
    """Mark OOB inputs as consumed."""
    for oob in _oob_queues.get(debate_id, []):
        if oob["oob_id"] in oob_ids:
            oob["status"] = "consumed"


def clear_oob_queue(debate_id: str) -> None:
    """Clean up OOB queue after debate completes."""
    _oob_queues.pop(debate_id, None)


def enqueue_oob(debate_id: str, entry: dict) -> None:
    """Add an OOB entry to the queue."""
    if debate_id not in _oob_queues:
        _oob_queues[debate_id] = []
    _oob_queues[debate_id].append(entry)


# ---------------------------------------------------------------------------
# Cancellation — delegates to the unified workflow state backend
# ---------------------------------------------------------------------------
#
# The debate_id doubles as the key in the workflow state backend.
# This is safe because the state backend is a flat ``str → value``
# map; session_id and debate_id are different keys and never
# collide.  Cross-process wake-up: a cancel API call on one
# worker fires the ``danwa:wf:pause:<debate_id>`` channel (via
# ``WorkflowStateBackend.cancel``), waking a waiter on any other
# worker.


def is_cancelled(debate_id: str) -> bool:
    """Check if a debate has been cancelled."""
    return get_workflow_state().is_cancelled(debate_id)


def clear_cancel(debate_id: str) -> None:
    """Remove cancellation flag after handling."""
    get_workflow_state().clear_cancel(debate_id)


def mark_cancelled(debate_id: str) -> None:
    """Mark a debate as cancelled."""
    get_workflow_state().cancel(debate_id)
