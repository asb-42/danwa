"""Debate SSE streaming endpoint.

Extracted from ``backend.api.routers.debate`` to isolate the real-time
Server-Sent Events (SSE) concern from CRUD and workflow logic.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_debate_store_for_case
from backend.api.events import subscribe, unsubscribe
from backend.models.schemas import DebateStatus
from backend.persistence.debate_store import DebateStore

router = APIRouter()


async def _sse_events(debate_id: str, project_id: str, store: DebateStore):
    """Yield SSE events for a debate using the event bus.

    Subscribes to the event bus for pending AND running debates so that
    events published after ``start_debate()`` are not missed (the frontend
    connects SSE *before* calling start).
    """
    debate = store.get(debate_id)
    if not debate:
        yield {"event": "error", "data": json.dumps({"detail": "Debate not found"})}
        return

    status = debate["status"]
    status_val = status.value if hasattr(status, "value") else status

    # Send initial status
    yield {
        "event": "status_change",
        "data": json.dumps({"debate_id": debate_id, "status": status_val}),
    }

    # If debate is already completed/failed, send all rounds at once and return
    if status == DebateStatus.COMPLETED:
        for i, round_data in enumerate(debate.get("rounds", [])):
            yield {
                "event": "round_update",
                "data": json.dumps({"round": i + 1, "data": round_data}),
            }
        yield {
            "event": "status_change",
            "data": json.dumps({"debate_id": debate_id, "status": "completed"}),
        }
        return

    if status == DebateStatus.FAILED:
        yield {
            "event": "status_change",
            "data": json.dumps({"debate_id": debate_id, "status": "failed"}),
        }
        return

    # For pending or running debates: subscribe to the event bus.
    queue = subscribe(debate_id)
    try:
        while True:
            try:
                event_type, payload = await asyncio.wait_for(queue.get(), timeout=300.0)
            except TimeoutError:
                yield {"event": "keepalive", "data": "{}"}
                continue

            yield {"event": event_type, "data": payload}

            if event_type == "status_change":
                data = json.loads(payload)
                if data.get("status") in ("completed", "failed"):
                    break
    finally:
        unsubscribe(debate_id, queue)


@router.get("/{debate_id}/stream")
async def stream_debate(
    debate_id: str,
    project_id: str = Query(
        ...,
        description="Case/project UUID (query param, since EventSource cannot send headers)",
    ),
):
    """SSE endpoint for real-time debate updates.

    Accepts ``project_id`` as a **query parameter** because the browser's
    ``EventSource`` API cannot send custom HTTP headers.
    """
    store = get_debate_store_for_case(project_id)
    return EventSourceResponse(_sse_events(debate_id, project_id, store))
