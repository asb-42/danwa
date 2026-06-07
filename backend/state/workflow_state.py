"""Workflow state store — Redis-backed or in-memory fallback.

Provides a unified API for workflow pause/resume/cancel/status that works
both with Redis (multi-process) and without (single-process in-memory).

Sprint 37 (part 2/3) — adds ``wait_for_pause`` / ``wait_for_resume`` that
block on a per-session ``WaitEvent`` (see ``backend.state.wait_event``)
instead of a process-local ``asyncio.Event``.  The wake-up is delivered
across processes via the configured pub/sub backend, so a worker that
issues ``pause(session_id)`` can wake a workflow loop running on a
different worker.

Sprint 38 (part 1/3) — adds ``set_extension_signal`` /
``wait_for_extension_signal`` to replace the 2-second polling loop in
``moderator_nodes.py`` for the extra-rounds extension decision.  The
HITL API endpoint fires the signal after saving the decision to the
debate store, and the moderator's wait unblocks immediately.  Falls
back to ``timeout`` (5 min) on no decision.

Sprint 38 (part 3/3) — adds ``get_hitl_pause`` / ``set_hitl_pause`` /
``clear_hitl_pause`` to consolidate the last process-local singleton
(``hitl/api.py:_paused_debates``) into the workflow state backend.
The HITL pause stores ``{paused_at, reason}`` per debate; the
existing ``is_paused()`` is session-level workflow pause (a
different concern) and is not changed.
"""

from __future__ import annotations

import json
import logging
from typing import Protocol

from backend.state.pubsub import PubSubBackend, get_pubsub
from backend.state.wait_event import WaitEvent, get_wait_event

logger = logging.getLogger(__name__)


class WorkflowStateBackend(Protocol):
    """Interface for workflow state operations."""

    def get_status(self, session_id: str) -> str:
        """Return the current workflow status for *session_id*."""
        ...

    def set_status(self, session_id: str, status: str) -> None:
        """Persist a new workflow status for *session_id*."""
        ...

    def is_cancelled(self, session_id: str) -> bool:
        """Return ``True`` if *session_id* has been cancelled."""
        ...

    def cancel(self, session_id: str) -> None:
        """Cancel the workflow for *session_id*."""
        ...

    def clear_cancel(self, session_id: str) -> None:
        """Remove the cancellation flag for *session_id*."""
        ...

    def is_paused(self, session_id: str) -> bool:
        """Return ``True`` if *session_id* is currently paused."""
        ...

    def pause(self, session_id: str) -> None:
        """Pause the workflow for *session_id*."""
        ...

    def resume(self, session_id: str) -> None:
        """Resume a paused workflow for *session_id*."""
        ...

    def wait_for_pause(self, session_id: str, timeout: float | None = None) -> bool:
        """Block until the session is paused or *timeout* expires."""
        ...

    def wait_for_resume(self, session_id: str, timeout: float | None = None) -> bool:
        """Block until the session is resumed or *timeout* expires."""
        ...

    def set_extension_signal(self, session_id: str) -> None:
        """Fire the per-session extension-decision signal."""
        ...

    def wait_for_extension_signal(self, session_id: str, timeout: float | None = None) -> bool:
        """Block until the extension-decision signal fires or *timeout* expires."""
        ...

    def get_hitl_pause(self, debate_id: str) -> dict | None:
        """Return the HITL pause record for *debate_id*, or ``None``."""
        ...

    def set_hitl_pause(self, debate_id: str, paused_at: str, reason: str | None) -> None:
        """Mark *debate_id* as HITL-paused."""
        ...

    def clear_hitl_pause(self, debate_id: str) -> None:
        """Clear the HITL pause record for *debate_id*."""
        ...

    def cleanup(self, session_id: str) -> None:
        """Remove all state for *session_id* (status, cancel, pause, wait events)."""
        ...


# Channel name builders — kept as module-level so the InMemory and
# Redis impls share the exact same string (consumers should never
# see a divergence between backends).
def _pause_channel(session_id: str) -> str:
    """Return the pub/sub channel name for pause signals."""
    return f"danwa:wf:pause:{session_id}"


def _resume_channel(session_id: str) -> str:
    """Return the pub/sub channel name for resume signals."""
    return f"danwa:wf:resume:{session_id}"


def _extension_channel(session_id: str) -> str:
    """Return the pub/sub channel name for extension signals."""
    return f"danwa:wf:extension:{session_id}"


class InMemoryWorkflowState:
    """In-memory workflow state — single-process only.

    The pub/sub backend is shared across all instances created in
    the same process (the factory caches it), so within one
    process the wait/notify semantics are reliable.
    """

    def __init__(self, pubsub: PubSubBackend | None = None) -> None:
        """Initialise the backend."""
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
        # HITL debate pause state (Sprint 38 3/3).  Per-debate
        # ``{paused_at, reason}`` record; ``None`` = not paused.
        # Separate from session-level ``_pause_events`` (workflow
        # runner semantics).
        self._hitl_pauses: dict[str, dict] = {}

    def _get_pause_wait_event(self, session_id: str) -> WaitEvent:
        """Return (or lazily create) the pause WaitEvent for *session_id*."""
        ch = _pause_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def _get_resume_wait_event(self, session_id: str) -> WaitEvent:
        """Return (or lazily create) the resume WaitEvent for *session_id*."""
        ch = _resume_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def _get_extension_wait_event(self, session_id: str) -> WaitEvent:
        """Return (or lazily create) the extension WaitEvent for *session_id*."""
        ch = _extension_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def get_status(self, session_id: str) -> str:
        """Return the current workflow status for *session_id*."""
        return self._status.get(session_id, "unknown")

    def set_status(self, session_id: str, status: str) -> None:
        """Persist a new workflow status for *session_id*."""
        self._status[session_id] = status

    def is_cancelled(self, session_id: str) -> bool:
        """Return True if *session_id* has been cancelled."""
        return session_id in self._cancelled

    def cancel(self, session_id: str) -> None:
        """Cancel the workflow for *session_id*."""
        self._cancelled.add(session_id)
        self._status[session_id] = "cancelled"

    def clear_cancel(self, session_id: str) -> None:
        """Remove the cancellation flag for *session_id*."""
        self._cancelled.discard(session_id)

    def is_paused(self, session_id: str) -> bool:
        """Return True if *session_id* is currently paused."""
        event = self._pause_events.get(session_id)
        if event is None:
            return False
        return not event.is_set()

    def pause(self, session_id: str) -> None:
        """Pause the workflow for *session_id*."""
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
        """Resume a paused workflow for *session_id*."""
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

    async def wait_for_pause(self, session_id: str, timeout: float | None = None) -> bool:
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

    async def wait_for_resume(self, session_id: str, timeout: float | None = None) -> bool:
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

    def set_extension_signal(self, session_id: str) -> None:
        """Fire the per-session extension-decision signal.

        Called by the HITL API endpoint after saving the user's
        extension decision (``granted`` / ``denied``) to the
        debate store.  Wakes any ``wait_for_extension_signal``
        waiter on the same session across processes.

        Note: the signal carries no payload.  Callers must read
        the decision (granted vs denied) from the debate store
        after wake-up.  This keeps the state backend
        payload-agnostic — the debate store is the single source
        of truth for the decision value.
        """
        self._get_extension_wait_event(session_id).set()

    async def wait_for_extension_signal(self, session_id: str, timeout: float | None = None) -> bool:
        """Block until the extension-decision signal fires (or timeout).

        Returns ``True`` if the extension channel was set (locally
        or via cross-process signal), ``False`` on timeout.  If
        the channel was already set when called, returns ``True``
        immediately via the channel-state fast path.

        Replaces the 2-second ``asyncio.sleep`` polling loop that
        ``moderator_nodes.py`` used to do for the extra-rounds
        extension request.  Typical wake-up latency: a few
        milliseconds after the HITL API call, instead of up to 2
        seconds.
        """
        ev = self._get_extension_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    def get_hitl_pause(self, debate_id: str) -> dict | None:
        """Return the HITL pause record for a debate, or ``None``.

        The record contains ``paused_at`` (ISO timestamp string)
        and ``reason`` (free-form text from the user, may be
        ``None``).  A ``None`` return means the debate is not
        currently HITL-paused.

        Distinct from session-level ``is_paused()``: this is
        user-driven pause (the user clicked the pause button),
        while ``is_paused()`` tracks workflow-runner pause
        (used by ``task_dispatch`` to suspend a running
        workflow).  Both can coexist on the same debate.
        """
        record = self._hitl_pauses.get(debate_id)
        if record is None:
            return None
        # Return a copy so callers cannot mutate our internal
        # state by holding a reference.
        return dict(record)

    def set_hitl_pause(self, debate_id: str, paused_at: str, reason: str | None) -> None:
        """Mark a debate as HITL-paused.

        Stores ``{paused_at, reason}`` keyed by ``debate_id``.
        Idempotent — calling twice overwrites the prior record
        (and updates ``paused_at`` to the latest timestamp).
        """
        self._hitl_pauses[debate_id] = {
            "paused_at": paused_at,
            "reason": reason,
        }

    def clear_hitl_pause(self, debate_id: str) -> None:
        """Clear the HITL pause record for a debate.

        Idempotent — safe to call when no pause record exists.
        """
        self._hitl_pauses.pop(debate_id, None)

    def cleanup(self, session_id: str) -> None:
        """Remove all state for *session_id*."""
        self._status.pop(session_id, None)
        self._cancelled.discard(session_id)
        self._pause_events.pop(session_id, None)
        # Close the wait events so any pending subscriptions are
        # released.  Idempotent — safe to call even if the events
        # were never created.
        for ch in (
            _pause_channel(session_id),
            _resume_channel(session_id),
            _extension_channel(session_id),
        ):
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
        """Initialise the backend."""
        import redis

        self.redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "danwa:wf:"
        self._pubsub = pubsub if pubsub is not None else get_pubsub()
        self._wait_events: dict[str, WaitEvent] = {}
        logger.info("RedisWorkflowState connected to %s", redis_url)

    def _key(self, session_id: str, suffix: str) -> str:
        """Build a namespaced Redis key for *session_id* and *suffix*."""
        return f"{self._prefix}{suffix}:{session_id}"

    def _get_pause_wait_event(self, session_id: str) -> WaitEvent:
        """Return (or lazily create) the pause WaitEvent for *session_id*."""
        ch = _pause_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def _get_resume_wait_event(self, session_id: str) -> WaitEvent:
        """Return (or lazily create) the resume WaitEvent for *session_id*."""
        ch = _resume_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def _get_extension_wait_event(self, session_id: str) -> WaitEvent:
        """Return (or lazily create) the extension WaitEvent for *session_id*."""
        ch = _extension_channel(session_id)
        ev = self._wait_events.get(ch)
        if ev is None:
            ev = get_wait_event(ch, pubsub=self._pubsub)
            self._wait_events[ch] = ev
        return ev

    def get_status(self, session_id: str) -> str:
        """Return the current workflow status for *session_id*."""
        val = self.redis.get(self._key(session_id, "status"))
        return val or "unknown"

    def set_status(self, session_id: str, status: str) -> None:
        """Persist a new workflow status for *session_id*."""
        self.redis.setex(self._key(session_id, "status"), 3600, status)

    def is_cancelled(self, session_id: str) -> bool:
        """Return True if *session_id* has been cancelled."""
        return self.redis.exists(self._key(session_id, "cancelled")) == 1

    def cancel(self, session_id: str) -> None:
        """Cancel the workflow for *session_id*."""
        pipe = self.redis.pipeline()
        pipe.set(self._key(session_id, "cancelled"), "1")
        pipe.setex(self._key(session_id, "status"), 3600, "cancelled")
        pipe.execute()

    def clear_cancel(self, session_id: str) -> None:
        """Remove the cancellation flag for *session_id*."""
        self.redis.delete(self._key(session_id, "cancelled"))

    def is_paused(self, session_id: str) -> bool:
        """Return True if *session_id* is currently paused."""
        return self.redis.exists(self._key(session_id, "paused")) == 1

    def pause(self, session_id: str) -> None:
        """Pause the workflow for *session_id*."""
        pipe = self.redis.pipeline()
        pipe.set(self._key(session_id, "paused"), "1")
        pipe.setex(self._key(session_id, "status"), 3600, "paused")
        pipe.execute()
        # Cross-process wake-up: anyone waiting on
        # ``wait_for_pause`` returns.
        self._get_pause_wait_event(session_id).set()

    def resume(self, session_id: str) -> None:
        """Resume a paused workflow for *session_id*."""
        pipe = self.redis.pipeline()
        pipe.delete(self._key(session_id, "paused"))
        pipe.setex(self._key(session_id, "status"), 3600, "running")
        pipe.execute()
        # Cross-process wake-up: anyone waiting on
        # ``wait_for_resume`` returns.
        self._get_resume_wait_event(session_id).set()

    async def wait_for_pause(self, session_id: str, timeout: float | None = None) -> bool:
        """Wait for for pause."""
        if self.is_paused(session_id):
            return True
        ev = self._get_pause_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    async def wait_for_resume(self, session_id: str, timeout: float | None = None) -> bool:
        """Wait for for resume."""
        if not self.is_paused(session_id):
            return True
        ev = self._get_resume_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    def set_extension_signal(self, session_id: str) -> None:
        """Fire the per-session extension-decision signal.

        See :meth:`InMemoryWorkflowState.set_extension_signal`
        for the protocol contract.  In the Redis backend, the
        signal is delivered through the per-channel WaitEvent,
        which uses Redis pub/sub + a per-channel flag counter
        for cross-process visibility.
        """
        self._get_extension_wait_event(session_id).set()

    async def wait_for_extension_signal(self, session_id: str, timeout: float | None = None) -> bool:
        """Block until the extension-decision signal fires.

        See :meth:`InMemoryWorkflowState.wait_for_extension_signal`
        for the protocol contract.
        """
        ev = self._get_extension_wait_event(session_id)
        return await ev.wait(timeout=timeout)

    def cleanup(self, session_id: str) -> None:
        """Remove all state for *session_id*."""
        self.redis.delete(
            self._key(session_id, "status"),
            self._key(session_id, "cancelled"),
            self._key(session_id, "paused"),
        )
        # Drop the in-process WaitEvent cache; the Redis-backed
        # wait events have no persistent state to release.
        self._wait_events.pop(_pause_channel(session_id), None)
        self._wait_events.pop(_resume_channel(session_id), None)
        self._wait_events.pop(_extension_channel(session_id), None)

    def get_hitl_pause(self, debate_id: str) -> dict | None:
        """Return the HITL pause record for a debate, or ``None``.

        See :meth:`InMemoryWorkflowState.get_hitl_pause` for the
        contract.  Backed by a JSON-encoded string at
        ``danwa:wf:hitl_pause:<debate_id>`` with a 12 h TTL
        (matches the existing session-status TTL).  The TTL
        bounds growth from abandoned debates that never call
        ``clear_hitl_pause``.
        """
        raw = self.redis.get(self._key(debate_id, "hitl_pause"))
        if raw is None:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError) as e:
            logger.warning(
                "Corrupt hitl_pause record for %s: %s — treating as None",
                debate_id,
                e,
            )
            return None
        return data

    def set_hitl_pause(self, debate_id: str, paused_at: str, reason: str | None) -> None:
        """Mark a debate as HITL-paused.

        Stores a JSON-encoded record at
        ``danwa:wf:hitl_pause:<debate_id>`` with a 12 h TTL.
        See :meth:`InMemoryWorkflowState.set_hitl_pause` for
        the contract.
        """
        record = json.dumps({"paused_at": paused_at, "reason": reason})
        self.redis.setex(self._key(debate_id, "hitl_pause"), 43200, record)

    def clear_hitl_pause(self, debate_id: str) -> None:
        """Clear the HITL pause record for a debate.

        Idempotent — see :meth:`InMemoryWorkflowState.clear_hitl_pause`.
        """
        self.redis.delete(self._key(debate_id, "hitl_pause"))


# Module-level singleton.  Same rationale as ``get_pubsub``: the
# InMemory backend keeps its state in instance attributes, so a
# fresh instance per call would lose cross-request coordination
# (e.g. cancel flag set by API request never visible to the
# background workflow loop).  Caching ensures ``get_workflow_state()``
# returns the same object within a process.
_workflow_state: WorkflowStateBackend | None = None


def get_workflow_state() -> WorkflowStateBackend:
    """Get the appropriate workflow state backend based on configuration.

    Returns ``RedisWorkflowState`` if ``settings.redis_url`` is
    configured and reachable, otherwise ``InMemoryWorkflowState``.
    The result is cached module-globally — see
    :func:`reset_workflow_state_cache` for the test-only escape
    hatch.

    Multi-process safety: with Redis configured, all processes
    see the same state.  Without Redis, the InMemory backend only
    works within a single process; multi-worker deployments must
    configure ``redis_url``.
    """
    global _workflow_state
    if _workflow_state is not None:
        return _workflow_state

    from backend.core.config import settings

    if settings.redis_url:
        try:
            _workflow_state = RedisWorkflowState(settings.redis_url)
            return _workflow_state
        except Exception as e:
            logger.warning("Redis unavailable (%s), falling back to in-memory state", e)
    _workflow_state = InMemoryWorkflowState()
    return _workflow_state


def reset_workflow_state_cache() -> None:
    """Clear the module-level workflow state singleton.

    Intended for tests that swap the ``settings.redis_url`` and
    want the factory to re-evaluate the configuration.  In
    production the cache lives for the lifetime of the process.
    """
    global _workflow_state
    _workflow_state = None
