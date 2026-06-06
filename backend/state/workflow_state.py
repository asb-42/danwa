"""Workflow state store — Redis-backed or in-memory fallback.

Provides a unified API for workflow pause/resume/cancel/status that works
both with Redis (multi-process) and without (single-process in-memory).

Sprint 37 (part 2/3) — adds ``wait_for_pause`` / ``wait_for_resume`` that
block on a per-session ``WaitEvent`` (see ``backend.state.wait_event``)
instead of a process-local ``asyncio.Event``.  The wake-up is delivered
across processes via the configured pub/sub backend, so a worker that
issues ``pause(session_id)`` can wake a workflow loop running on a
different worker.
"""

from __future__ import annotations

import logging
from typing import Protocol

from backend.state.pubsub import PubSubBackend, get_pubsub
from backend.state.wait_event import WaitEvent, get_wait_event

logger = logging.getLogger(__name__)


class WorkflowStateBackend(Protocol):
    """Interface for workflow state operations."""

    def get_status(self, session_id: str) -> str: ...
    def set_status(self, session_id: str, status: str) -> None: ...
    def is_cancelled(self, session_id: str) -> bool: ...
    def cancel(self, session_id: str) -> None: ...
    def clear_cancel(self, session_id: str) -> None: ...
    def is_paused(self, session_id: str) -> bool: ...
    def pause(self, session_id: str) -> None: ...
    def resume(self, session_id: str) -> None: ...
    def wait_for_pause(self, session_id: str, timeout: float | None = None) -> bool: ...
    def wait_for_resume(self, session_id: str, timeout: float | None = None) -> bool: ...
    def cleanup(self, session_id: str) -> None: ...


# Channel name builders — kept as module-level so the InMemory and
# Redis impls share the exact same string (consumers should never
# see a divergence between backends).
def _pause_channel(session_id: str) -> str:
    return f"danwa:wf:pause:{session_id}"


def _resume_channel(session_id: str) -> str:
    return f"danwa:wf:resume:{session_id}"


class InMemoryWorkflowState:
    """In-memory workflow state — single-process only.

    The pub/sub backend is shared across all instances created in
    the same process (the factory caches it), so within one
    process the wait/notify semantics are reliable.
    """

    def __init__(self, pubsub: PubSubBackend | None = None) -> None:
        self._status: dict[str, str] = {}
        self._cancelled: set[str] = set()
        # ``_pause_events`` is the legacy per-session asyncio.Event,
        # still used by ``get_pause_event()`` for callers that
        # want a raw asyncio.Event.  Sprint 37 part 3 will retire
        # it once ``workflow_runner`` migrates fully.
        self._pause_events: dict = {}
        # ``_wait_events`` is the new cross-process primitive,
        # keyed by ``(<channel>, pubsub)``.  We keep strong refs
        # so the underlying subscription isn't GC'd while a
        # waiter is iterating.
        self._pubsub = pubsub if pubsub is not None else get_pubsub()
        self._wait_events: dict[str, WaitEvent] = {}

    def _get_pause_wait_event(self, session_id: str) -> WaitEvent:
        ch = _pause_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def _get_resume_wait_event(self, session_id: str) -> WaitEvent:
        ch = _resume_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def get_status(self, session_id: str) -> str:
        return self._status.get(session_id, "unknown")

    def set_status(self, session_id: str, status: str) -> None:
        self._status[session_id] = status

    def is_cancelled(self, session_id: str) -> bool:
        return session_id in self._cancelled

    def cancel(self, session_id: str) -> None:
        self._cancelled.add(session_id)
        self._status[session_id] = "cancelled"

    def clear_cancel(self, session_id: str) -> None:
        self._cancelled.discard(session_id)

    def is_paused(self, session_id: str) -> bool:
        event = self._pause_events.get(session_id)
        if event is None:
            return False
        return not event.is_set()

    def pause(self, session_id: str) -> None:
        if session_id not in self._pause_events:
            import asyncio

            self._pause_events[session_id] = asyncio.Event()
            self._pause_events[session_id].set()
        self._pause_events[session_id].clear()
        self._status[session_id] = "paused"
        # Cross-process wake-up: fire the resume-cancel event so
        # anyone waiting on wait_for_pause() returns immediately.
        self._get_pause_wait_event(session_id).set()

    def resume(self, session_id: str) -> None:
        if session_id not in self._pause_events:
            import asyncio

            self._pause_events[session_id] = asyncio.Event()
        self._pause_events[session_id].set()
        self._status[session_id] = "running"
        # Cross-process wake-up: fire the resume event so
        # anyone waiting on wait_for_resume() returns immediately.
        self._get_resume_wait_event(session_id).set()

    def get_pause_event(self, session_id: str):
        """Return the raw ``asyncio.Event`` for this session.

        Kept for backward compatibility with callers that need a
        process-local event (e.g.  ``run_workflow_background``
        uses ``event.wait()`` directly).  New code should use
        ``wait_for_pause`` / ``wait_for_resume`` instead.
        """
        import asyncio

        if session_id not in self._pause_events:
            self._pause_events[session_id] = asyncio.Event()
            self._pause_events[session_id].set()
        return self._pause_events[session_id]

    async def wait_for_pause(
        self, session_id: str, timeout: float | None = None
    ) -> bool:
        """Block until the session is paused (or timeout expires).

        Returns ``True`` if the pause channel was set (locally
        or via cross-process signal) at the time of return,
        ``False`` on timeout.  If the local ``is_paused()`` is
        already True when called, returns ``True`` immediately.

        The post-wait check consults ``ev.is_set()`` (channel
        state) rather than ``self.is_paused()`` (local state) so
        that wake-ups from another instance on a shared pub/sub
        are reflected correctly.  ``is_paused()`` is per-instance
        for backward compat with the legacy ``asyncio.Event``
        API; ``is_set()`` is the cross-process truth.
        """
        if self.is_paused(session_id):
            return True
        ev = self._get_pause_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    async def wait_for_resume(
        self, session_id: str, timeout: float | None = None
    ) -> bool:
        """Block until the session is resumed (or timeout expires).

        Returns ``True`` if the resume channel was set (locally
        or via cross-process signal) at the time of return,
        ``False`` on timeout.  If the local ``is_paused()`` is
        already False when called (i.e. not paused), returns
        ``True`` immediately.

        Same rationale as ``wait_for_pause``: we check the
        channel state for the post-wait condition.  Note that
        cross-instance ``wait_for_resume`` only works if the
        calling instance believes the session is paused — the
        local ``is_paused()`` fast-path guards against a
        different instance calling ``wait_for_resume`` on a
        session it never paused, in which case there is nothing
        to wait for.
        """
        if not self.is_paused(session_id):
            return True
        ev = self._get_resume_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    def cleanup(self, session_id: str) -> None:
        self._status.pop(session_id, None)
        self._cancelled.discard(session_id)
        self._pause_events.pop(session_id, None)
        # Close the wait events so any pending subscriptions are
        # released.  Idempotent — safe to call even if the events
        # were never created.
        for ch in (_pause_channel(session_id), _resume_channel(session_id)):
            ev = self._wait_events.pop(ch, None)
            if ev is not None:
                # ``aclose`` is async but cleanup is sync; we use
                # the underlying close-event mechanism indirectly.
                # The WaitEvent's pubsub subscription, if any,
                # gets released when its waiter loop exits.
                pass


class RedisWorkflowState:
    """Redis-backed workflow state — multi-process safe.

    Requires redis package and a configured redis_url.  Wait events
    are backed by the Redis pub/sub + per-channel flag counter
    (see ``backend.state.wait_event.RedisWaitEvent``).
    """

    def __init__(self, redis_url: str, pubsub: PubSubBackend | None = None) -> None:
        import redis

        self.redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "danwa:wf:"
        self._pubsub = pubsub if pubsub is not None else get_pubsub()
        self._wait_events: dict[str, WaitEvent] = {}
        logger.info("RedisWorkflowState connected to %s", redis_url)

    def _key(self, session_id: str, suffix: str) -> str:
        return f"{self._prefix}{suffix}:{session_id}"

    def _get_pause_wait_event(self, session_id: str) -> WaitEvent:
        ch = _pause_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def _get_resume_wait_event(self, session_id: str) -> WaitEvent:
        ch = _resume_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def get_status(self, session_id: str) -> str:
        val = self.redis.get(self._key(session_id, "status"))
        return val or "unknown"

    def set_status(self, session_id: str, status: str) -> None:
        self.redis.setex(self._key(session_id, "status"), 3600, status)

    def is_cancelled(self, session_id: str) -> bool:
        return self.redis.exists(self._key(session_id, "cancelled")) == 1

    def cancel(self, session_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self._key(session_id, "cancelled"), "1")
        pipe.setex(self._key(session_id, "status"), 3600, "cancelled")
        pipe.execute()

    def clear_cancel(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id, "cancelled"))

    def is_paused(self, session_id: str) -> bool:
        return self.redis.exists(self._key(session_id, "paused")) == 1

    def pause(self, session_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self._key(session_id, "paused"), "1")
        pipe.setex(self._key(session_id, "status"), 3600, "paused")
        pipe.execute()
        # Cross-process wake-up: anyone waiting on
        # ``wait_for_pause`` returns.
        self._get_pause_wait_event(session_id).set()

    def resume(self, session_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.delete(self._key(session_id, "paused"))
        pipe.setex(self._key(session_id, "status"), 3600, "running")
        pipe.execute()
        # Cross-process wake-up: anyone waiting on
        # ``wait_for_resume`` returns.
        self._get_resume_wait_event(session_id).set()

    async def wait_for_pause(
        self, session_id: str, timeout: float | None = None
    ) -> bool:
        if self.is_paused(session_id):
            return True
        ev = self._get_pause_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    async def wait_for_resume(
        self, session_id: str, timeout: float | None = None
    ) -> bool:
        if not self.is_paused(session_id):
            return True
        ev = self._get_resume_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    def cleanup(self, session_id: str) -> None:
        self.redis.delete(
            self._key(session_id, "status"),
            self._key(session_id, "cancelled"),
            self._key(session_id, "paused"),
        )
        # Drop the in-process WaitEvent cache; the Redis-backed
        # wait events have no persistent state to release.
        self._wait_events.pop(_pause_channel(session_id), None)
        self._wait_events.pop(_resume_channel(session_id), None)


def get_workflow_state() -> InMemoryWorkflowState | RedisWorkflowState:
    """Get the appropriate workflow state backend based on configuration.

    Returns RedisWorkflowState if redis_url is configured, otherwise
    InMemoryWorkflowState.
    """
    from backend.core.config import settings

    if settings.redis_url:
        try:
            return RedisWorkflowState(settings.redis_url)
        except Exception as e:
            logger.warning("Redis unavailable (%s), falling back to in-memory state", e)

    return InMemoryWorkflowState()
