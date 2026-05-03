"""In-memory event bus for real-time debate streaming.

Each debate gets a list of subscriber queues.  Workflow nodes publish
events, and SSE endpoints consume them via async generators.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# debate_id → list of subscriber queues
_subscribers: dict[str, list[asyncio.Queue]] = {}


def subscribe(debate_id: str) -> asyncio.Queue:
    """Create a new subscriber queue for a debate. Returns the queue."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(debate_id, []).append(q)
    logger.debug(
        "SSE subscriber added for debate %s (total: %d)", debate_id, len(_subscribers[debate_id])
    )
    return q


def unsubscribe(debate_id: str, q: asyncio.Queue) -> None:
    """Remove a subscriber queue."""
    subs = _subscribers.get(debate_id, [])
    if q in subs:
        subs.remove(q)
    if not subs:
        _subscribers.pop(debate_id, None)
    logger.debug("SSE subscriber removed for debate %s", debate_id)


def publish(debate_id: str, event_type: str, data: Any) -> None:
    """Publish an event to all subscribers of a debate.

    This is called from sync workflow nodes, so it uses
    ``call_soon_threadsafe`` to enqueue on the event loop.
    """
    subs = _subscribers.get(debate_id, [])
    if not subs:
        return

    payload = json.dumps(data, default=str)
    logger.debug(
        "Publishing event '%s' to %d subscribers for debate %s", event_type, len(subs), debate_id
    )

    loop = asyncio.get_event_loop()
    for q in subs:
        loop.call_soon_threadsafe(q.put_nowait, (event_type, payload))


async def publish_async(debate_id: str, event_type: str, data: Any) -> None:
    """Async version of publish — for use inside async nodes."""
    subs = _subscribers.get(debate_id, [])
    if not subs:
        return

    payload = json.dumps(data, default=str)
    logger.debug(
        "Publishing event '%s' to %d subscribers for debate %s", event_type, len(subs), debate_id
    )

    for q in subs:
        q.put_nowait((event_type, payload))
