"""Tests for F-04 — observability and rollback for failed DB writes.

The L6 (Sprint 49) InterjectionService ran every ``_persist_*`` call
on a best-effort basis, swallowing ``sqlite3.DatabaseError`` with a
``logger.warning`` and returning ``None``.  Two failure modes followed:

1. **Silent data loss** — a chronically broken DB (disk full,
   permissions, corrupt file) was invisible to operations because no
   metric was exposed.
2. **Silent divergence** — when ``_persist_mark_consumed`` failed
   after a successful in-memory drain, the in-memory queue said
   ``consumed`` while the DB still had the rows as ``pending``.  A
   process restart would then re-deliver the rows the running session
   had already considered done — a silent double-processing bug.

These tests cover both fixes:

* The ``get_persist_failure_count()`` counter — exposed for
  operations to poll, incremented on every failed ``_persist_*``.
* The symmetric rollback — when ``_persist_mark_consumed`` returns
  ``False`` the in-memory status of the affected items is reset to
  ``pending`` and the dedup set is restored, so the next drain
  re-delivers them in the same session and a process restart sees
  consistent state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.workflow.interjection import InterjectionService


def _break_persist(method_name: str) -> callable:  # type: ignore[type-arg]
    """Return a ``_persist_*`` replacement that always returns ``False``."""

    def always_fails(self_obj, *args, **kwargs):  # type: ignore[no-untyped-def]
        self_obj._persist_failure_count += 1
        return False

    return always_fails


class TestPersistFailureCounter:
    """Verify ``get_persist_failure_count`` tracks every failed write."""

    @pytest.mark.asyncio
    async def test_counter_starts_at_zero(self, tmp_path: Path) -> None:
        """A fresh service exposes a zero counter."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        assert service.get_persist_failure_count() == 0

    @pytest.mark.asyncio
    async def test_counter_increments_on_insert_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed ``_persist_insert`` bumps the counter."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        monkeypatch.setattr(InterjectionService, "_persist_insert", _break_persist("_persist_insert"))

        await service.submit("sess-counter-1", "Hello")

        assert service.get_persist_failure_count() == 1

    @pytest.mark.asyncio
    async def test_counter_increments_on_mark_consumed_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed ``_persist_mark_consumed`` bumps the counter."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        await service.submit("sess-counter-2", "Hello")

        # Now break the next persist and drain.
        monkeypatch.setattr(InterjectionService, "_persist_mark_consumed", _break_persist("_persist_mark_consumed"))
        await service.consume("sess-counter-2")

        assert service.get_persist_failure_count() == 1

    @pytest.mark.asyncio
    async def test_counter_increments_on_delete_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A failed ``_persist_delete_session`` bumps the counter."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        await service.submit("sess-counter-3", "Hello")

        monkeypatch.setattr(
            InterjectionService,
            "_persist_delete_session",
            _break_persist("_persist_delete_session"),
        )
        await service.clear("sess-counter-3")

        assert service.get_persist_failure_count() == 1

    @pytest.mark.asyncio
    async def test_counter_accumulates_across_calls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The counter is cumulative over the worker lifetime."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        monkeypatch.setattr(InterjectionService, "_persist_insert", _break_persist("_persist_insert"))

        for _ in range(5):
            await service.submit("sess-counter-4", "Hello")

        assert service.get_persist_failure_count() == 5

    @pytest.mark.asyncio
    async def test_counter_does_not_increment_on_success(self, tmp_path: Path) -> None:
        """A successful persist does not touch the counter."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        await service.submit("sess-counter-5", "Hello")
        await service.consume("sess-counter-5")
        await service.clear("sess-counter-5")

        assert service.get_persist_failure_count() == 0


class TestRollbackOnPersistFailure:
    """Verify the F-04 symmetric rollback for ``_persist_mark_consumed``."""

    @pytest.mark.asyncio
    async def test_items_remain_pending_after_mark_consumed_failure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Items are re-marked ``pending`` if the DB update fails.

        Without the rollback the in-memory queue would say
        ``consumed`` while the DB still has the rows as ``pending``,
        and a process restart would re-deliver them — silently
        double-processing user input.
        """
        service = InterjectionService(db_path=tmp_path / "i.db")
        await service.submit("sess-rb-1", "Hello")

        # Break the mark_consumed persist and drain.
        monkeypatch.setattr(InterjectionService, "_persist_mark_consumed", _break_persist("_persist_mark_consumed"))
        results = await service.consume("sess-rb-1")
        assert len(results) == 1

        # The in-memory queue must still hold the item as ``pending``
        # so the next drain re-delivers it.
        pending = await service.get_pending("sess-rb-1")
        assert len(pending) == 1
        assert pending[0]["content"] == "Hello"
        assert pending[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_items_redelivered_on_next_drain_after_rollback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The next drain after a rolled-back persist re-delivers the items.

        This mirrors the DB state: the DB still has the rows as
        ``pending`` (the mark-consumed UPDATE failed), so a
        restarted process would re-deliver them.  The running
        process must behave the same — otherwise we would have a
        silent divergence between in-memory and persisted state.
        """
        service = InterjectionService(db_path=tmp_path / "i.db")
        await service.submit("sess-rb-2", "Hello")

        # First drain — persist fails, items roll back to pending.
        monkeypatch.setattr(InterjectionService, "_persist_mark_consumed", _break_persist("_persist_mark_consumed"))
        results1 = await service.consume("sess-rb-2")
        assert len(results1) == 1

        # Second drain on the same service (with the persist still
        # broken) must re-deliver the same item.
        results2 = await service.consume("sess-rb-2")
        assert len(results2) == 1
        assert results2[0]["interjection_id"] == results1[0]["interjection_id"]

    @pytest.mark.asyncio
    async def test_dedup_set_restored_after_rollback(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """``_queued_ids`` is restored after a rollback so a subsequent
        cross-process re-hydration does not double-add the row.

        The dedup set is the safety net for cross-process
        re-hydration (F-01): the DB row is skipped if its id is
        already in the set.  After a successful mark-consumed, the
        id is removed.  The rollback must add it back, otherwise a
        cross-process ``_ensure_loaded`` would re-add the same row
        that the in-memory queue still holds as ``pending`` (or
        re-rolled-back ``pending``).
        """
        service = InterjectionService(db_path=tmp_path / "i.db")
        iid = await service.submit("sess-rb-3", "Hello")
        assert iid in service._queued_ids

        # First drain — persist fails, rollback restores status + dedup.
        monkeypatch.setattr(InterjectionService, "_persist_mark_consumed", _break_persist("_persist_mark_consumed"))
        await service.consume("sess-rb-3")
        assert iid in service._queued_ids

    @pytest.mark.asyncio
    async def test_successful_drain_does_not_rollback(self, tmp_path: Path) -> None:
        """Sanity check: a successful drain still removes the items."""
        service = InterjectionService(db_path=tmp_path / "i.db")
        await service.submit("sess-rb-4", "Hello")
        await service.submit("sess-rb-4", "World")

        results = await service.consume("sess-rb-4")
        assert len(results) == 2

        pending = await service.get_pending("sess-rb-4")
        assert pending == []

    @pytest.mark.asyncio
    async def test_persistence_failure_count_visible_to_operations(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Operations can poll the counter via the public method.

        This is the F-04 observability contract: the counter is
        exposed as a public method so a healthz-style endpoint can
        report it and trigger an alert.  Without the public method
        the only signal would be grepping logs, which doesn't scale.
        """
        service = InterjectionService(db_path=tmp_path / "i.db")
        monkeypatch.setattr(InterjectionService, "_persist_insert", _break_persist("_persist_insert"))

        # Public method must exist and return an int.
        assert hasattr(service, "get_persist_failure_count")
        assert isinstance(service.get_persist_failure_count(), int)

        await service.submit("sess-rb-5", "Hello")
        assert service.get_persist_failure_count() == 1
