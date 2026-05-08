"""Blueprint Canvas — SSE stub router for real-time updates.

Stub implementation that returns a keep-alive stream.
Will be extended in Phase 3+ for canvas collaboration and live debate status.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/stream")
async def stream_blueprint_events() -> EventSourceResponse:
    """SSE endpoint for real-time blueprint/canvas updates.

    Stub implementation — sends a ``ping`` event every 30 seconds.
    Will be extended in Phase 3+ for canvas collaboration.
    """

    async def event_generator():
        while True:
            yield {"event": "ping", "data": "{}"}
            await asyncio.sleep(30)

    return EventSourceResponse(event_generator())
