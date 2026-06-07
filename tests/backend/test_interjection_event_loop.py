"""Tests for F-02 — sync SQLite I/O must not block the asyncio event loop.

The InterjectionService used to run every ``_persist_*`` call inside the
``async with self._lock`` block, so a slow ``conn.commit()`` (EBS throttle,
NFS hiccup, fsync spike) would wedge every coroutine in the worker
process for the duration of the disk I/O.  The fix moves the persist to
``asyncio.to_thread`` *after* the lock is released, so the event loop
stays free to serve other requests while the thread does the I/O.

These tests monkey-patch the persist to block on a ``threading.Event``
and assert that another coroutine can acquire ``self._lock`` while the
persist is in progress.  Without the F-02 fix the assertion would
deadlock the worker and the ``asyncio.wait_for`` guard would fire.
"""

from __future__ import annotations

import asyncio
import threading
import time
from pathlib import Path

import pytest

from backend.workflow.interjection import InterjectionService


def _make_slow_persist(
    service: InterjectionService,
    started: threading.Event,
    release: threading.Event,
):
    """Return a ``_persist_insert`` wrapper that blocks on ``release``.

    The wrapper records when it was called (``started.set()``) and then
    waits for the test to release it (``release.wait()``).  When the
    test finally sets ``release`` the original method runs and the
    wrapper returns.
    """

    original = service._persist_insert.__func__  # type: ignore[attr-defined]

    def slow_persist(self_obj, interjection):  # type: ignore[no-untyped-def]
        started.set()
        if not release.wait(timeout=5.0):
            raise AssertionError("Persist was not released within 5s — test bug?")
        return original(self_obj, interjection)

    return slow_persist


class TestEventLoopStaysFreeDuringPersist:
    """Verify that a slow ``_persist_*`` does not block the asyncio.Lock.

    Without F-02, the asyncio.Lock is held while the disk I/O runs, so
    every other coroutine that tries to acquire it blocks too.  With
    F-02, the lock is released before the persist starts, so other
    coroutines can run normally.
    """

    @pytest.mark.asyncio
    async def test_consume_not_blocked_by_slow_persist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``consume()`` must not be blocked by a slow ``_persist_insert``."""
        db = tmp_path / "i.db"
        service = InterjectionService(db_path=db)

        persist_started = threading.Event()
        persist_release = threading.Event()
        monkeypatch.setattr(
            InterjectionService,
            "_persist_insert",
            _make_slow_persist(service, persist_started, persist_release),
        )

        # Start the submit; it will queue the in-memory append, release
        # the lock, then ``await`` the slow persist in a worker thread.
        submit_task = asyncio.create_task(service.submit("sess-free", "Hello"))

        # Wait for the persist thread to actually start running.  Use
        # ``asyncio.to_thread`` so the event loop stays responsive —
        # the test is itself running on the event loop thread.
        await asyncio.to_thread(persist_started.wait, 2.0)
        if not persist_started.is_set():
            persist_release.set()
            pytest.fail("Persist thread never started")

        # ``consume()`` acquires the same asyncio.Lock.  Without F-02
        # the lock would be held until ``persist_release`` is set, so
        # this ``asyncio.wait_for`` would time out at 1 s.  With F-02
        # the lock is free and ``consume()`` returns in milliseconds.
        # The item IS in the in-memory queue (it was appended under
        # the lock before the persist started), so we expect to
        # receive it — what matters is the call returns quickly.
        consume_task = asyncio.create_task(service.consume("sess-free"))
        t0 = time.monotonic()
        results = await asyncio.wait_for(consume_task, timeout=1.0)
        elapsed = time.monotonic() - t0
        assert len(results) == 1, f"Expected 1 consumed item, got {results}"
        assert elapsed < 0.5, f"consume() took {elapsed:.3f}s — lock was held!"

        # Clean up: release the persist and wait for the submit to complete.
        persist_release.set()
        iid = await asyncio.wait_for(submit_task, timeout=2.0)
        assert iid.startswith("inj-")

    @pytest.mark.asyncio
    async def test_get_pending_not_blocked_by_slow_persist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``get_pending()`` must not be blocked by a slow ``_persist_insert``."""
        db = tmp_path / "i.db"
        service = InterjectionService(db_path=db)

        persist_started = threading.Event()
        persist_release = threading.Event()
        monkeypatch.setattr(
            InterjectionService,
            "_persist_insert",
            _make_slow_persist(service, persist_started, persist_release),
        )

        submit_task = asyncio.create_task(service.submit("sess-free-2", "Hello"))
        await asyncio.to_thread(persist_started.wait, 2.0)
        if not persist_started.is_set():
            persist_release.set()
            pytest.fail("Persist thread never started")

        pending_task = asyncio.create_task(service.get_pending("sess-free-2"))
        t0 = time.monotonic()
        pending = await asyncio.wait_for(pending_task, timeout=1.0)
        elapsed = time.monotonic() - t0
        # The submit has queued the item but the persist has not
        # completed; ``get_pending`` reads from the in-memory queue
        # which already has the item (it was appended before the
        # lock was released).
        assert len(pending) == 1
        assert elapsed < 0.5, f"get_pending() took {elapsed:.3f}s — lock was held!"

        persist_release.set()
        await asyncio.wait_for(submit_task, timeout=2.0)

    @pytest.mark.asyncio
    async def test_clear_not_blocked_by_slow_persist(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``clear()`` must not be blocked by a slow ``_persist_insert``."""
        db = tmp_path / "i.db"
        service = InterjectionService(db_path=db)

        persist_started = threading.Event()
        persist_release = threading.Event()
        monkeypatch.setattr(
            InterjectionService,
            "_persist_insert",
            _make_slow_persist(service, persist_started, persist_release),
        )

        submit_task = asyncio.create_task(service.submit("sess-free-3", "Hello"))
        await asyncio.to_thread(persist_started.wait, 2.0)
        if not persist_started.is_set():
            persist_release.set()
            pytest.fail("Persist thread never started")

        clear_task = asyncio.create_task(service.clear("sess-free-3"))
        t0 = time.monotonic()
        await asyncio.wait_for(clear_task, timeout=1.0)
        elapsed = time.monotonic() - t0
        assert elapsed < 0.5, f"clear() took {elapsed:.3f}s — lock was held!"

        persist_release.set()
        await asyncio.wait_for(submit_task, timeout=2.0)


class TestPersistRunsOnWorkerThread:
    """Verify that ``_persist_*`` is invoked on a thread, not the event loop."""

    @pytest.mark.asyncio
    async def test_persist_does_not_run_on_event_loop_thread(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``_persist_insert`` must be called from a non-event-loop thread.

        The event-loop thread id is captured before the submit; the
        persist records the thread it actually runs on.  The two ids
        must differ — otherwise the disk I/O is still blocking the
        loop and F-02 has not actually been applied.
        """
        import threading

        loop_thread_id = threading.get_ident()

        db = tmp_path / "i.db"
        service = InterjectionService(db_path=db)

        persist_thread_id: list[int] = []
        original_persist = service._persist_insert.__func__  # type: ignore[attr-defined]

        def recording_persist(self_obj, interjection):  # type: ignore[no-untyped-def]
            persist_thread_id.append(threading.get_ident())
            return original_persist(self_obj, interjection)

        monkeypatch.setattr(InterjectionService, "_persist_insert", recording_persist)

        await service.submit("sess-thread", "Hello")

        assert persist_thread_id, "_persist_insert was never called"
        assert persist_thread_id[0] != loop_thread_id, "_persist_insert ran on the event loop thread — F-02 not applied (asyncio.to_thread missing?)"
