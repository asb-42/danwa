"""Blueprint Canvas — SSE router for real-time updates.

Provides a real-time event stream for workflow execution and canvas updates.
Accepts an optional ``session_id`` query parameter to subscribe to
workflow-specific events from the event bus.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from backend.api.events import subscribe, unsubscribe

router = APIRouter()


@router.get("/stream")
async def stream_blueprint_events(
    session_id: str | None = Query(default=None, description="Workflow session ID to subscribe to"),
) -> EventSourceResponse:
    """SSE endpoint for real-time blueprint/canvas updates.

    If ``session_id`` is provided, subscribes to the event bus for that
    workflow session and yields workflow-specific events (node updates,
    completion, errors, interjections, etc.).

    If no ``session_id`` is provided, falls back to a keep-alive stream
    for general canvas updates.
    """

    async def event_generator():
        """Event generator the instance."""
        if session_id:
            # Subscribe to workflow event bus
            queue = subscribe(session_id)
            try:
                # Send initial connection event
                yield {
                    "event": "connected",
                    "data": json.dumps({"session_id": session_id}),
                }

                while True:
                    try:
                        event_type, payload = await asyncio.wait_for(queue.get(), timeout=300.0)
                        yield {"event": event_type, "data": payload}

                        # Stop on terminal events
                        if event_type in ("workflow.complete", "node.error"):
                            break
                    except TimeoutError:
                        # Send keepalive
                        yield {"event": "ping", "data": "{}"}
            finally:
                unsubscribe(session_id, queue)
        else:
            # Fallback: general canvas keep-alive
            while True:
                yield {"event": "ping", "data": "{}"}
                await asyncio.sleep(30)

    return EventSourceResponse(event_generator())
