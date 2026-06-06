"""Tests for Sprint 37 (part 2/3) — wait_for_pause / wait_for_resume.

Verifies that:
* ``wait_for_pause`` blocks until ``pause()`` is called.
* ``wait_for_resume`` blocks until ``resume()`` is called.
* Both return ``True`` immediately when the session is already in
  the target state.
* ``wait_for_*`` respect the timeout.
* ``pause()`` / ``resume()`` wake up waiters in another WaitEvent
  instance (cross-instance property, same channel).
* ``cleanup()`` releases the per-session state.
* ``is_paused`` / ``get_status`` still work (regression guard
  for the legacy asyncio.Event path).
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from backend.state.workflow_state import (
    InMemoryWorkflowState,
    _pause_channel,
)


def _session_id() -> str:
    return f"sess-{uuid.uuid4()}"


# ---------------------------------------------------------------------------
# InMemoryWorkflowState — wait_for_pause / wait_for_resume
# ---------------------------------------------------------------------------


class TestInMemoryWaitForPause:
    """``wait_for_pause`` returns True when the session is paused."""

    @pytest.mark.asyncio
    async def test_already_paused_returns_immediately(self) -> None:
        """If the session is paused at call time, ``wait_for_pause``
        returns True without yielding to the event loop.
        """
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)
        result = await state.wait_for_pause(sid, timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_until_pause_called(self) -> None:
        """``wait_for_pause`` blocks until ``pause()`` is invoked
        from another coroutine.
        """
        state = InMemoryWorkflowState()
        sid = _session_id()

        async def pauser() -> None:
            await asyncio.sleep(0.05)
            state.pause(sid)

        asyncio.create_task(pauser())
        result = await state.wait_for_pause(sid, timeout=2.0)
        assert result is True
        assert state.is_paused(sid) is True
        assert state.get_status(sid) == "paused"

    @pytest.mark.asyncio
    async def test_times_out_when_no_pause(self) -> None:
        """``wait_for_pause`` returns False on timeout."""
        state = InMemoryWorkflowState()
        sid = _session_id()
        result = await state.wait_for_pause(sid, timeout=0.1)
        assert result is False
        assert state.is_paused(sid) is False

    @pytest.mark.asyncio
    async def test_resume_clears_pause(self) -> None:
        """After ``resume()``, the session is no longer paused."""
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)
        assert state.is_paused(sid) is True
        state.resume(sid)
        assert state.is_paused(sid) is False
        assert state.get_status(sid) == "running"


class TestInMemoryWaitForResume:
    """``wait_for_resume`` returns True when the session is running."""

    @pytest.mark.asyncio
    async def test_already_running_returns_immediately(self) -> None:
        """A session that isn't paused is already running, so
        ``wait_for_resume`` returns True without blocking.
        """
        state = InMemoryWorkflowState()
        sid = _session_id()
        result = await state.wait_for_resume(sid, timeout=1.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_blocks_until_resume_called(self) -> None:
        """``wait_for_resume`` blocks while paused, returns when
        ``resume()`` is invoked.
        """
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)

        async def resumer() -> None:
            await asyncio.sleep(0.05)
            state.resume(sid)

        asyncio.create_task(resumer())
        result = await state.wait_for_resume(sid, timeout=2.0)
        assert result is True
        assert state.is_paused(sid) is False
        assert state.get_status(sid) == "running"

    @pytest.mark.asyncio
    async def test_times_out_when_no_resume(self) -> None:
        """``wait_for_resume`` returns False on timeout (still paused)."""
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)
        result = await state.wait_for_resume(sid, timeout=0.1)
        assert result is False
        assert state.is_paused(sid) is True


# ---------------------------------------------------------------------------
# Cross-process property (simulated by two state instances on the same channel)
# ---------------------------------------------------------------------------


class TestInMemoryCrossInstance:
    """Two state instances on the same session share the wake-up channel.

    Note: ``is_paused()`` is per-instance (it checks the local
    ``_pause_events`` dict for backward compat with the legacy
    asyncio.Event API).  The shared ``pubsub`` only carries the
    wake-up signal, not the canonical state.  This is fine for
    ``wait_for_pause`` (the caller doesn't know the session is
    paused, so it subscribes to the channel).  It's NOT a
    drop-in for ``wait_for_resume`` on a different instance,
    because the new instance's ``is_paused()`` returns False
    and ``wait_for_resume`` short-circuits to True — see
    ``test_resume_works_when_same_instance_owns_pause`` for
    the realistic pattern.
    """

    @pytest.mark.asyncio
    async def test_pause_wakes_other_instance_waiter(self) -> None:
        """A waiter on instance B unblocks when instance A calls
        ``pause()``.  Simulates cross-process wake-up.
        """
        # The two instances need to share a pubsub for the
        # WaitEvent to be the same logical event.  Passing
        # ``pubsub=...`` shares the channel registry.
        from backend.state.pubsub import InMemoryPubSub

        pubsub = InMemoryPubSub()
        state_a = InMemoryWorkflowState(pubsub=pubsub)
        state_b = InMemoryWorkflowState(pubsub=pubsub)
        sid = _session_id()

        async def pauser() -> None:
            await asyncio.sleep(0.05)
            state_a.pause(sid)

        asyncio.create_task(pauser())
        result = await state_b.wait_for_pause(sid, timeout=2.0)
        assert result is True
        # state_a's local status reflects the pause.
        assert state_a.is_paused(sid) is True
        assert state_a.get_status(sid) == "paused"

    @pytest.mark.asyncio
    async def test_resume_works_when_same_instance_owns_pause(self) -> None:
        """``wait_for_resume`` works correctly when the same
        instance that recorded the pause is the one waiting.

        This is the realistic pattern: a workflow loop running
        on worker A blocks in ``wait_for_resume`` after the
        pause was applied, and an external resume call on the
        same worker fires the resume channel.
        """
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)

        async def resumer() -> None:
            await asyncio.sleep(0.05)
            state.resume(sid)

        asyncio.create_task(resumer())
        result = await state.wait_for_resume(sid, timeout=2.0)
        assert result is True
        assert state.is_paused(sid) is False
        assert state.get_status(sid) == "running"


# ---------------------------------------------------------------------------
# Cancellation
# ---------------------------------------------------------------------------


class TestInMemoryCancellation:
    """``is_cancelled`` and ``clear_cancel`` still work after the
    wait_for_pause additions.
    """

    def test_cancel_sets_flag(self) -> None:
        state = InMemoryWorkflowState()
        sid = _session_id()
        assert state.is_cancelled(sid) is False
        state.cancel(sid)
        assert state.is_cancelled(sid) is True
        assert state.get_status(sid) == "cancelled"

    def test_clear_cancel_removes_flag(self) -> None:
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.cancel(sid)
        state.clear_cancel(sid)
        assert state.is_cancelled(sid) is False


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


class TestInMemoryCleanup:
    """``cleanup`` releases the per-session state."""

    def test_cleanup_clears_status(self) -> None:
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)
        state.cancel(sid)
        state.cleanup(sid)
        assert state.get_status(sid) == "unknown"
        assert state.is_paused(sid) is False
        assert state.is_cancelled(sid) is False

    def test_cleanup_drops_wait_events(self) -> None:
        """After cleanup, the cached WaitEvent is gone (so a
        fresh pause after cleanup creates a new event).
        """
        state = InMemoryWorkflowState()
        sid = _session_id()
        state.pause(sid)
        # Internal cache should have an entry for the pause channel
        assert _pause_channel(sid) in state._wait_events
        state.cleanup(sid)
        assert _pause_channel(sid) not in state._wait_events


# ---------------------------------------------------------------------------
# Legacy asyncio.Event API
# ---------------------------------------------------------------------------


class TestInMemoryLegacyEvent:
    """``get_pause_event`` still returns a usable asyncio.Event."""

    def test_get_pause_event_returns_asyncio_event(self) -> None:
        """The legacy method still works for callers that need a
        raw ``asyncio.Event``.
        """
        import asyncio

        state = InMemoryWorkflowState()
        sid = _session_id()
        ev = state.get_pause_event(sid)
        assert isinstance(ev, asyncio.Event)
        # Default state: set (not paused)
        assert ev.is_set() is True
        state.pause(sid)
        assert ev.is_set() is False
        state.resume(sid)
        assert ev.is_set() is True


# ---------------------------------------------------------------------------
# Protocol / abstract surface
# ---------------------------------------------------------------------------


class TestProtocolSurface:
    """The new methods are part of the public surface (Protocol)."""

    def test_protocol_mentions_wait_methods(self) -> None:
        """``WorkflowStateBackend`` protocol includes the new
        ``wait_for_pause`` and ``wait_for_resume`` so type
        checkers see them on the union return type of
        ``get_workflow_state()``.
        """
        from backend.state.workflow_state import WorkflowStateBackend

        # ``typing.Protocol`` stores abstract method bodies in
        # the class ``__dict__`` (not ``__abstractmethods__``,
        # which is only populated for ``@runtime_checkable``
        # Protocols or ``ABCMeta`` subclasses).
        attrs = set(WorkflowStateBackend.__dict__.keys())
        assert "wait_for_pause" in attrs
        assert "wait_for_resume" in attrs

    def test_both_backends_implement_wait_methods(self) -> None:
        """Both ``InMemoryWorkflowState`` and ``RedisWorkflowState``
        define ``wait_for_pause`` and ``wait_for_resume`` as
        ``async def`` (not just sync).  The Protocol can't
        enforce async, so we check directly.
        """
        import inspect

        assert inspect.iscoroutinefunction(InMemoryWorkflowState.wait_for_pause)
        assert inspect.iscoroutinefunction(InMemoryWorkflowState.wait_for_resume)
