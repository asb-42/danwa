"""Cancellation flags and Out-of-Band (OOB) input queues for debates."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_cancelled_debates: set[str] = set()
_oob_queues: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Cancellation helpers
# ---------------------------------------------------------------------------


def is_cancelled(debate_id: str) -> bool:
    """Check if a debate has been cancelled."""
    return debate_id in _cancelled_debates


def clear_cancel(debate_id: str) -> None:
    """Remove cancellation flag after handling."""
    _cancelled_debates.discard(debate_id)


def mark_cancelled(debate_id: str) -> None:
    """Mark a debate as cancelled."""
    _cancelled_debates.add(debate_id)


# ---------------------------------------------------------------------------
# OOB (Out-of-Band) input helpers
# ---------------------------------------------------------------------------


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
