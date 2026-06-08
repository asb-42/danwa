"""Tests for F-06 — wake event must be cleared while holding the lock.

The L6 ``clear()`` method cleared the wake event *after* releasing the
async lock, which created a window where a concurrent ``submit()``
could set the event, then ``clear()`` would erase its signal —
causing the consumer to miss the new item until the next interaction.

The fix moves ``event.clear()`` *inside* the ``async with self._lock``
block so that no ``submit()`` can race with it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from backend.state.pubsub import reset_pubsub_cache
from backend.workflow.interjection import InterjectionService


@pytest.fixture
def service(tmp_path: Path):
    """Create an isolated InterjectionService for each test."""
    reset_pubsub_cache()
    svc = InterjectionService(db_path=tmp_path / "i.db")
    yield svc
    reset_pubsub_cache()


class TestClearRaceCondition:
    """Verify ``clear()`` and ``submit()`` don't race on the wake event."""

    @pytest.mark.asyncio
    async def test_clear_removes_items_and_wake_event(self, service: InterjectionService) -> None:
        """After ``clear()``, the session queue is empty and the wake
        event is not set."""
        await service.submit("sess-cr-1", "hello", "user")
        assert len(service._queues.get("sess-cr-1", [])) == 1

        event = service._wake_events.get("sess-cr-1")
        assert event is not None

        await service.clear("sess-cr-1")

        queue = service._queues.get("sess-cr-1")
        assert queue is None or len(queue) == 0

        event_after = service._wake_events.get("sess-cr-1")
        if event_after is not None:
            assert not event_after.is_set(), "Wake event should be cleared after clear(), but it was still set — race condition likely"

    @pytest.mark.asyncio
    async def test_clear_then_submit_recreates_wake_event(self, service: InterjectionService) -> None:
        """After ``clear()``, a fresh ``submit()`` creates a new item
        and sets the wake event again — the cleared state doesn't
        permanently break the session."""
        await service.submit("sess-cr-2", "first", "user")
        await service.clear("sess-cr-2")

        await service.submit("sess-cr-2", "second", "user")
        queue = service._queues.get("sess-cr-2", [])
        assert len(queue) == 1
        assert queue[0].content == "second"

        event = service._wake_events.get("sess-cr-2")
        assert event is not None
        assert event.is_set(), "Wake event should be set after new submit"

    @pytest.mark.asyncio
    async def test_wake_event_not_clobbered_by_clear_after_submit(self, service: InterjectionService) -> None:
        """The core F-06 scenario: ``submit()`` sets the wake event,
        then ``clear()`` must not erase it after releasing the lock.

        Before the fix ``event.clear()`` ran *after* the lock was
        released, so a submit() that set the event between lock-
        release and clear() would have its signal wiped.

        With the fix, ``event.clear()`` runs inside the lock, so
        if clear() acquires the lock *after* submit(), the event
        is already cleared by the time submit() returns.
        """
        # Seed the queue.
        await service.submit("sess-cr-4", "seed", "user")

        # Run clear and submit concurrently.  Whichever acquires the
        # lock first will run to completion before the other starts
        # (asyncio.Lock is not re-entrant).
        await asyncio.gather(
            service.clear("sess-cr-4"),
            service.submit("sess-cr-4", "new-after-clear", "user"),
        )

        # The important invariant: if the queue has items (submit
        # won the race), the wake event MUST be set so the consumer
        # will be woken.  Before the fix, the wake event could be
        # cleared even though submit() had queued an item.
        queue = service._queues.get("sess-cr-4", [])
        event = service._wake_events.get("sess-cr-4")

        if len(queue) > 0 and event is not None:
            assert event.is_set(), (
                "Queue has items but wake event is not set — submit() queued an item but clear() wiped the signal (F-06 race condition)"
            )
