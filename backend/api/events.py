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

# Counter for periodic stale-subscriber cleanup (2.3 fix)
_publish_count: int = 0


def _cleanup_stale_subscribers() -> None:
    """Remove debate_ids whose subscriber list is empty.

    Clients that disconnect without calling ``unsubscribe()`` (browser
    tab close, network drop) leave behind empty lists.  This is called
    every 100 publishes to prevent unbounded growth of the map.
    """
    stale = [did for did, subs in _subscribers.items() if not subs]
    for did in stale:
        _subscribers.pop(did, None)
    if stale:
        logger.debug("Cleaned up %d stale SSE subscriber entries", len(stale))


def subscribe(debate_id: str) -> asyncio.Queue:
    """Create a new subscriber queue for a debate. Returns the queue."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers.setdefault(debate_id, []).append(q)
    logger.debug("SSE subscriber added for debate %s (total: %d)", debate_id, len(_subscribers[debate_id]))
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
    global _publish_count
    _publish_count += 1
    if _publish_count % 100 == 0:
        _cleanup_stale_subscribers()

    subs = _subscribers.get(debate_id, [])
    if not subs:
        return

    payload = json.dumps(data, default=str)
    logger.debug("Publishing event '%s' to %d subscribers for debate %s", event_type, len(subs), debate_id)

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.debug("No running event loop — cannot dispatch SSE event for %s", debate_id)
        return
    for q in subs:
        loop.call_soon_threadsafe(q.put_nowait, (event_type, payload))


async def publish_async(debate_id: str, event_type: str, data: Any) -> None:
    """Async version of publish — for use inside async nodes."""
    global _publish_count
    _publish_count += 1
    if _publish_count % 100 == 0:
        _cleanup_stale_subscribers()

    subs = _subscribers.get(debate_id, [])
    if not subs:
        return

    payload = json.dumps(data, default=str)
    logger.debug("Publishing event '%s' to %d subscribers for debate %s", event_type, len(subs), debate_id)

    for q in subs:
        q.put_nowait((event_type, payload))
