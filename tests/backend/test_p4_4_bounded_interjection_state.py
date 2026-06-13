"""Tests for P4.4 — bounded in-process state in InterjectionService.

The 2026-06-12 review (§3.5) flagged that ``_queued_ids`` (and the
session-keyed dicts ``_queues``, ``_wake_events``,
``_hydration_version``) only ever *grew* across the worker's
lifetime.  Even though ``consume()`` and ``clear()`` clean up after
themselves on the happy path, a misbehaving caller that submits
faster than it drains could push process memory up over time.

The fix caps each structure with a process-wide LRU
(``BoundedSet`` / ``BoundedLRU``) and exposes the cap as module-level
constants.  These tests pin the contract:

* Each cap is honoured.  Submitting past the cap drops the oldest
  entries; submitting *within* the cap works as before.
* Eviction is silent — no exception, no breaking change to existing
  consume/clear semantics.
* ``consume()`` and ``clear()`` continue to remove the obvious
  references, so the LRU only ever fires as a backstop.
* The same eviction logic applies to the per-session dicts
  (``_queues``, ``_wake_events``, ``_hydration_version``).
* The unit-level ``BoundedSet`` / ``BoundedLRU`` classes behave as
  advertised (``add``, ``discard``, ``difference_update``, ``set``
  membership, ``dict`` accessors, etc.).
"""

# Async tests are individually marked with @pytest.mark.asyncio.
# We deliberately do *not* set a module-level ``pytestmark`` because
# the unit tests for ``BoundedSet`` / ``BoundedLRU`` are sync and a
# global asyncio mark produces a PytestWarning for every one of
# them.
from __future__ import annotations

import pytest

from backend.workflow.interjection import (
    _MAX_QUEUED_IDS,
    _MAX_SESSION_KEYS,
    BoundedLRU,
    BoundedSet,
    InterjectionService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service() -> InterjectionService:
    """Fresh InterjectionService (in-memory mode) for each test."""
    return InterjectionService()


# ---------------------------------------------------------------------------
# TestCapsAreConfigured
# ---------------------------------------------------------------------------


class TestCapsAreConfigured:
    """The cap constants are present and positive."""

    def test_caps_are_positive(self) -> None:
        assert _MAX_QUEUED_IDS > 0
        assert _MAX_SESSION_KEYS > 0

    def test_queued_ids_cap_is_larger_than_session_cap(self) -> None:
        # The dedup set tracks one id per item; the per-session dicts
        # track one entry per session.  A worker that has seen N
        # sessions with M items each holds M ids in ``_queued_ids``
        # and N session keys in ``_queues``.  The caps should reflect
        # that: the dedup cap is sized to hold a few items per active
        # session.
        assert _MAX_QUEUED_IDS > _MAX_SESSION_KEYS

    def test_queued_ids_uses_bounded_set(self, service: InterjectionService) -> None:
        assert isinstance(service._queued_ids, BoundedSet)
        assert service._queued_ids.maxlen == _MAX_QUEUED_IDS

    def test_session_dicts_use_bounded_lru(self, service: InterjectionService) -> None:
        for attr in ("_queues", "_wake_events", "_hydration_version"):
            obj = getattr(service, attr)
            assert isinstance(obj, BoundedLRU), f"{attr} should be a BoundedLRU"
            assert obj.maxlen == _MAX_SESSION_KEYS


# ---------------------------------------------------------------------------
# TestBoundedSetUnit
# ---------------------------------------------------------------------------


class TestBoundedSetUnit:
    """``BoundedSet`` behaves like a ``set`` for the methods the
    service actually uses, and respects the cap."""

    def test_basic_set_protocol(self) -> None:
        s = BoundedSet(maxlen=10)
        s.add("a")
        s.add("b")
        assert "a" in s
        assert "b" in s
        assert "c" not in s
        assert len(s) == 2
        assert bool(s) is True
        assert set(s) == {"a", "b"}

    def test_discard(self) -> None:
        s = BoundedSet(maxlen=10)
        s.add("a")
        s.discard("a")
        assert "a" not in s
        s.discard("missing")  # silent

    def test_difference_update(self) -> None:
        s = BoundedSet(maxlen=10)
        s.add("a")
        s.add("b")
        s.add("c")
        s.difference_update(["a", "c", "missing"])
        assert set(s) == {"b"}

    def test_clear(self) -> None:
        s = BoundedSet(maxlen=10)
        for i in range(5):
            s.add(f"k{i}")
        s.clear()
        assert len(s) == 0
        assert bool(s) is False

    def test_re_add_refreshes_lru_position(self) -> None:
        s = BoundedSet(maxlen=3)
        s.add("a")
        s.add("b")
        s.add("c")
        # Re-adding ``a`` should NOT evict it; it should refresh
        # its position so a future ``add`` of ``d`` evicts ``b``
        # (the now-oldest), not ``a``.
        s.add("a")
        s.add("d")
        assert "a" in s
        assert "b" not in s
        assert set(s) == {"a", "c", "d"}

    def test_eviction_drops_oldest(self) -> None:
        s = BoundedSet(maxlen=3)
        s.add("a")
        s.add("b")
        s.add("c")
        s.add("d")
        # ``a`` was the oldest → evicted.
        assert set(s) == {"b", "c", "d"}
        assert s.evictions_total == 1

    def test_eviction_counter_is_cumulative(self) -> None:
        s = BoundedSet(maxlen=2)
        for i in range(10):
            s.add(f"k{i}")
        assert s.evictions_total == 8  # 10 - 2

    def test_invalid_maxlen(self) -> None:
        with pytest.raises(ValueError):
            BoundedSet(maxlen=0)
        with pytest.raises(ValueError):
            BoundedSet(maxlen=-1)


class TestBoundedLRUUnit:
    """``BoundedLRU`` behaves like a ``dict`` and respects the cap."""

    def test_basic_dict_protocol(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=10)
        d["a"] = 1
        d["b"] = 2
        assert d["a"] == 1
        assert d.get("missing", "fallback") == "fallback"
        assert "a" in d
        assert len(d) == 2

    def test_setdefault(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=10)
        assert d.setdefault("a", "x") == "x"
        assert d.setdefault("a", "y") == "x"  # already there

    def test_pop_with_default(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=10)
        d["a"] = 1
        assert d.pop("a") == 1
        assert d.pop("missing", None) is None

    def test_clear_and_delete(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=10)
        d["a"] = 1
        del d["a"]
        assert "a" not in d
        d.clear()
        assert len(d) == 0

    def test_eviction_drops_oldest(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        d["d"] = 4
        # ``a`` was the oldest → evicted.
        assert "a" not in d
        assert set(d.keys()) == {"b", "c", "d"}

    def test_get_refreshes_lru(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=3)
        d["a"] = 1
        d["b"] = 2
        d["c"] = 3
        # Read ``a`` so it becomes the most-recently-used.
        _ = d.get("a")
        d["d"] = 4
        # ``b`` was the oldest (since ``a`` was just touched) →
        # ``b`` is evicted, not ``a``.
        assert "a" in d
        assert "b" not in d
        assert set(d.keys()) == {"a", "c", "d"}

    def test_items_keys_values(self) -> None:
        d: BoundedLRU = BoundedLRU(maxlen=10)
        d["a"] = 1
        d["b"] = 2
        assert set(d.keys()) == {"a", "b"}
        assert set(d.values()) == {1, 2}
        assert set(d.items()) == {("a", 1), ("b", 2)}


# ---------------------------------------------------------------------------
# TestBoundedSetInService
# ---------------------------------------------------------------------------


class TestBoundedSetInService:
    """``_queued_ids`` exposes the same surface area the service
    always used; the underlying cap is invisible until the cap is
    actually exceeded."""

    @pytest.mark.asyncio
    async def test_submit_then_drain_keeps_set_clean(self, service: InterjectionService) -> None:
        """The happy path still works: submit, drain, set shrinks."""
        iid = await service.submit("sess-clean", "hello")
        assert iid in service._queued_ids
        await service.consume("sess-clean")
        assert iid not in service._queued_ids
        # And the cap is unchanged (no eviction triggered).
        assert service._queued_ids.evictions_total == 0

    @pytest.mark.asyncio
    async def test_clear_drops_all_session_ids(self, service: InterjectionService) -> None:
        """``clear()`` continues to purge the dedup set for the session."""
        iid1 = await service.submit("sess-clear-1", "a")
        iid2 = await service.submit("sess-clear-1", "b")
        assert iid1 in service._queued_ids
        assert iid2 in service._queued_ids
        await service.clear("sess-clear-1")
        assert iid1 not in service._queued_ids
        assert iid2 not in service._queued_ids
        assert service._queued_ids.evictions_total == 0

    @pytest.mark.asyncio
    async def test_many_sessions_stay_within_cap(self, service: InterjectionService) -> None:
        """Submitting into N distinct sessions (each with one item)
        must not trigger any LRU eviction.  The cap is
        ``_MAX_QUEUED_IDS`` which is 50 000 — we submit fewer than
        that here so the test is fast."""
        n = 100
        for i in range(n):
            await service.submit(f"sess-many-{i}", "x")
        assert len(service._queued_ids) == n
        assert service._queued_ids.evictions_total == 0

    def test_set_protocol_works_after_eviction(self) -> None:
        """After a LRU eviction the BoundedSet's set API is still
        internally consistent: ``in``, ``len``, ``__iter__``."""
        s = BoundedSet(maxlen=3)
        for i in range(10):
            s.add(f"k{i}")
        assert len(s) == 3
        # The oldest 7 entries were evicted; the newest 3 remain.
        assert s == {"k7", "k8", "k9"}
        assert "k0" not in s
        assert "k9" in s


# ---------------------------------------------------------------------------
# TestCapIsRespected
# ---------------------------------------------------------------------------


class TestCapIsRespected:
    """End-to-end: submitting past the cap must not crash and must
    keep the dedup set bounded."""

    @pytest.mark.asyncio
    async def test_queued_ids_does_not_grow_past_cap(self) -> None:
        # Use a small, custom cap so the test runs in well under a
        # second while still being a meaningful exercise of the LRU
        # code path.
        service = InterjectionService()
        original = service._queued_ids
        service._queued_ids = BoundedSet(maxlen=50)
        try:
            ids: list[str] = []
            for i in range(200):
                iid = await service.submit(f"sess-cap-{i}", "x")
                ids.append(iid)
            assert len(service._queued_ids) == 50
            assert service._queued_ids.evictions_total == 150
            # The *oldest* 150 ids are gone, the *newest* 50 remain.
            for iid in ids[:150]:
                assert iid not in service._queued_ids
            for iid in ids[150:]:
                assert iid in service._queued_ids
        finally:
            service._queued_ids = original

    @pytest.mark.asyncio
    async def test_per_session_queue_capped(self) -> None:
        """``_queues`` and ``_wake_events`` are session-keyed dicts
        and they must also be bounded."""
        service = InterjectionService()
        # Replace with a tiny cap to keep the test cheap.
        from backend.workflow.interjection import BoundedLRU

        original_queues = service._queues
        original_events = service._wake_events
        original_hyd = service._hydration_version
        service._queues = BoundedLRU(maxlen=5)
        service._wake_events = BoundedLRU(maxlen=5)
        service._hydration_version = BoundedLRU(maxlen=5)
        try:
            for i in range(20):
                await service.submit(f"sess-perf-{i}", "x")
                # Touch _hydration_version the same way _ensure_loaded does.
                service._hydration_version[f"sess-perf-{i}"] = i
            assert len(service._queues) == 5
            assert len(service._wake_events) == 5
            assert len(service._hydration_version) == 5
        finally:
            service._queues = original_queues
            service._wake_events = original_events
            service._hydration_version = original_hyd


# ---------------------------------------------------------------------------
# TestConsumeAndClearStillWork
# ---------------------------------------------------------------------------


class TestConsumeAndClearStillWork:
    """The post-P4.4 code must preserve the original consume/clear
    semantics — the LRU is *only* a backstop."""

    @pytest.mark.asyncio
    async def test_consume_drains_queue_and_shrinks_set(self, service: InterjectionService) -> None:
        iid1 = await service.submit("sess-drain", "first")
        iid2 = await service.submit("sess-drain", "second")
        assert len(service._queues["sess-drain"]) == 2
        results = await service.consume("sess-drain")
        assert len(results) == 2
        # Both ids removed from the dedup set.
        assert iid1 not in service._queued_ids
        assert iid2 not in service._queued_ids
        # The session queue itself is GC'd (every item consumed).
        assert "sess-drain" not in service._queues

    @pytest.mark.asyncio
    async def test_clear_removes_session_everywhere(self, service: InterjectionService) -> None:
        iid = await service.submit("sess-wipe", "x")
        # The session also occupies a wake event slot.
        service._get_wake_event("sess-wipe")
        assert "sess-wipe" in service._queues
        assert "sess-wipe" in service._wake_events
        assert iid in service._queued_ids
        await service.clear("sess-wipe")
        assert "sess-wipe" not in service._queues
        # _get_wake_event re-creates on demand — we check the *id*,
        # not membership, by inspecting the post-clear state.
        assert iid not in service._queued_ids

    @pytest.mark.asyncio
    async def test_submit_after_clear(self, service: InterjectionService) -> None:
        """Clearing a session and re-using the same id is allowed."""
        await service.submit("sess-recycle", "first")
        await service.clear("sess-recycle")
        iid2 = await service.submit("sess-recycle", "second")
        assert iid2 in service._queued_ids
        results = await service.consume("sess-recycle")
        assert results[0]["content"] == "second"


# ---------------------------------------------------------------------------
# TestDedupSetAfterEviction
# ---------------------------------------------------------------------------


class TestDedupSetAfterEviction:
    """When the LRU evicts a queued id, the *next* ``_ensure_loaded``
    will re-add the row from SQLite (since the DB still has it as
    ``pending``) — i.e. eviction is a no-op on correctness, just a
    memory release."""

    @pytest.mark.asyncio
    async def test_evicted_id_is_not_silently_lost_from_db(self, tmp_path) -> None:
        """If a row is in the DB and we evict it from the dedup set,
        the next ``_ensure_loaded`` should re-add it to the in-memory
        queue (the dedup-set miss is what allows the re-add)."""
        db = tmp_path / "i.db"
        service = InterjectionService(db_path=db)
        try:
            iid = await service.submit("sess-evict", "Hello")
            # Simulate a misbehaving caller that overruns the cap.
            original = service._queued_ids
            service._queued_ids = BoundedSet(maxlen=1)
            try:
                # Adding 5 ids will evict all but the newest.
                for j in range(5):
                    service._queued_ids.add(f"junk-{j}")
                assert iid not in service._queued_ids

                # Now trigger a re-hydration.  The row is still in
                # the DB as ``pending``, and because the dedup set
                # no longer knows about it, ``_ensure_loaded`` will
                # re-add it.
                service._ensure_loaded("sess-evict")
                assert iid in service._queued_ids
                assert iid in {ij.interjection_id for ij in service._queues["sess-evict"]}
            finally:
                service._queued_ids = original
        finally:
            service.close()
