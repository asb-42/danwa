"""Interjection service — manages user interjections during workflow execution.

Provides an in-memory, per-session queue for interjections that workflow
nodes can consume at interjection points.  Thread-safe via ``asyncio.Lock``.

Two consumption modes
---------------------
* :meth:`InterjectionService.consume` — non-blocking pull.  Returns
  immediately with whatever is queued, or an empty list.  Used by agent
  nodes that want to opportunistically inject user input as additional
  context.
* :meth:`InterjectionService.consume_blocking` — waits until at least
  one interjection is available, then returns the items.  Used by the
  :func:`backend.workflow.nodes.system_nodes.interjection_node` so a
  workflow actually *pauses* at user-injection points instead of
  continuing with no input.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Interjection:
    """A single interjection item in the queue."""

    interjection_id: str
    session_id: str
    content: str
    source: str  # "user" | "system" | "api"
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending" | "consumed"


class InterjectionService:
    """In-memory interjection queue per workflow session.

    Thread-safe via ``asyncio.Lock`` so it can be used from both
    API handlers (async) and workflow node functions (async).
    """

    def __init__(self) -> None:
        # session_id → list of Interjection objects
        self._queues: dict[str, list[Interjection]] = {}
        # session_id → asyncio.Event that is set when new items are queued
        # and cleared again after they are consumed.  Used by
        # consume_blocking() to suspend callers without polling.
        self._wake_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def _get_wake_event(self, session_id: str) -> asyncio.Event:
        """Return the wake-up event for ``session_id``, creating it on demand."""
        event = self._wake_events.get(session_id)
        if event is None:
            event = asyncio.Event()
            # New sessions start in the "set" state — there is no
            # consumer blocked on this session yet, so the first
            # consume_blocking() call must check the queue first and
            # only wait if it is empty.
            event.set()
            self._wake_events[session_id] = event
        return event

    async def submit(
        self,
        session_id: str,
        content: str,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add an interjection to the queue for a session.

        Args:
            session_id: The workflow session ID.
            content: The interjection text content.
            source: Origin of the interjection ("user", "system", "api").
            metadata: Optional metadata dict.

        Returns:
            The generated interjection_id.
        """
        interjection_id = f"inj-{uuid.uuid4().hex[:12]}"
        interjection = Interjection(
            interjection_id=interjection_id,
            session_id=session_id,
            content=content,
            source=source,
            metadata=metadata or {},
        )

        async with self._lock:
            self._queues.setdefault(session_id, []).append(interjection)
            queue_size = len(self._queues[session_id])
            # Wake any consumer waiting in consume_blocking().  The
            # event stays "set" until the queue is fully drained by
            # the next consume(); see consume_blocking() for the
            # reset logic.
            self._get_wake_event(session_id).set()

        # DIAGNOSTIC: Log submission with queue size so we can trace if consume() ever picks it up
        logger.info(
            "DIAG submit(): interjection=%s session=%s source=%s queue_size=%d",
            interjection_id,
            session_id,
            source,
            queue_size,
        )
        return interjection_id

    async def consume(self, session_id: str, node_id: str | None = None) -> list[dict[str, Any]]:
        """Pop all pending interjections for a session (non-blocking).

        Marks them as "consumed" and returns their data.  Returns
        immediately even if the queue is empty — use
        :meth:`consume_blocking` to wait for items.

        Args:
            session_id: The workflow session ID.
            node_id: Optional node ID for logging context.

        Returns:
            List of interjection dicts with keys: intervention_id, content,
            source, metadata.
        """
        results, _queue_size = await self._drain_pending(session_id, node_id)
        return results

    async def consume_blocking(
        self,
        session_id: str,
        node_id: str | None = None,
        timeout: float = 300.0,
    ) -> list[dict[str, Any]]:
        """Block until at least one interjection is available, then drain the queue.

        Polling-free: waits on a per-session :class:`asyncio.Event` that
        :meth:`submit` sets when it enqueues an item.  Cancels early
        if ``timeout`` elapses with no activity.

        Args:
            session_id: The workflow session ID.
            node_id: Optional node ID for logging context.
            timeout: Maximum seconds to wait for a submission.  Pass
                ``0`` to skip the wait (useful in tests).  Default is
                5 minutes — long enough to let a human respond
                interactively, short enough that forgotten sessions
                don't block the graph executor indefinitely.

        Returns:
            List of interjection dicts (possibly empty if the timeout
            fired before anything was submitted).
        """
        event = self._get_wake_event(session_id)

        # Cheap fast-path: if items are already queued, drain them
        # without awaiting.  This avoids the overhead of resetting and
        # re-setting the event for the common "submit and immediately
        # consume" pattern.
        results, queue_size = await self._drain_pending(session_id, node_id)
        if results:
            return results

        if timeout <= 0:
            return []

        logger.info(
            "consume_blocking: waiting for interjection session=%s node=%s timeout=%.1fs",
            session_id,
            node_id,
            timeout,
        )

        # Wait for the next submit().  We loop because multiple
        # consumers might race for the same event — the first one to
        # wake up drains the queue, the others find an empty queue
        # and have to wait for the next submit.
        while True:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except TimeoutError:
                logger.info(
                    "consume_blocking: timeout session=%s node=%s after %.1fs",
                    session_id,
                    node_id,
                    timeout,
                )
                return []

            results, queue_size = await self._drain_pending(session_id, node_id)
            if results:
                return results

            # Queue was drained by a concurrent consumer; reset the
            # event so we wait for the *next* submit() and try again.
            event.clear()
            # If timeout was reached during the loop, bail out.
            # (We don't track elapsed time precisely here — the outer
            # wait_for is the real timeout enforcement.)

        # Unreachable: the loop above always returns.
        _ = queue_size  # keep linter happy
        return []

    async def _drain_pending(self, session_id: str, node_id: str | None) -> tuple[list[dict[str, Any]], int]:
        """Mark all pending items for ``session_id`` as consumed and return them.

        Returns ``(results, queue_size)``.  When ``queue_size`` is zero
        after the call, the wake-up event is reset so that the next
        :meth:`consume_blocking` call will block.
        """
        async with self._lock:
            queue = self._queues.get(session_id, [])
            queue_size = len(queue)
            pending = [ij for ij in queue if ij.status == "pending"]

            results: list[dict[str, Any]] = []
            for ij in pending:
                ij.status = "consumed"
                results.append(
                    {
                        "interjection_id": ij.interjection_id,
                        "content": ij.content,
                        "source": ij.source,
                        "metadata": ij.metadata,
                    }
                )

            # Garbage-collect fully consumed queues so they don't
            # accumulate across many short-lived sessions.
            if queue and all(ij.status == "consumed" for ij in queue):
                self._queues.pop(session_id, None)
                queue_size_after = 0
            else:
                queue_size_after = len(self._queues.get(session_id, []))

        # Reset the wake-up event when the queue is empty so the next
        # consume_blocking() call will block.  Done outside the lock to
        # avoid mixing asyncio primitives with the asyncio.Lock.
        if queue_size_after == 0:
            event = self._wake_events.get(session_id)
            if event is not None:
                event.clear()

        # DIAGNOSTIC: Always log consume calls so we can trace the flow
        logger.info(
            "DIAG consume() called: session=%s node=%s | queue_size=%d pending=%d consumed=%d",
            session_id,
            node_id,
            queue_size,
            len(pending),
            len(results),
        )
        return results, queue_size_after

    async def get_pending(self, session_id: str) -> list[dict[str, Any]]:
        """List pending interjections for a session without consuming them.

        Args:
            session_id: The workflow session ID.

        Returns:
            List of pending interjection dicts.
        """
        async with self._lock:
            queue = self._queues.get(session_id, [])
            return [
                {
                    "interjection_id": ij.interjection_id,
                    "content": ij.content,
                    "source": ij.source,
                    "metadata": ij.metadata,
                    "status": ij.status,
                }
                for ij in queue
                if ij.status == "pending"
            ]

    async def clear(self, session_id: str) -> None:
        """Remove all interjections for a session.

        Args:
            session_id: The workflow session ID.
        """
        async with self._lock:
            self._queues.pop(session_id, None)
        # Reset the wake-up event so future consumers block.
        event = self._wake_events.get(session_id)
        if event is not None:
            event.clear()
        logger.info("Cleared interjection queue for session %s", session_id)


# Module-level singleton — shared across the application
interjection_service = InterjectionService()
