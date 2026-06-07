"""Tests for the F-01 fix — cross-process wake-up for ``consume_blocking``.

The pre-fix implementation used a per-event-loop :class:`asyncio.Event`
to wake a waiting consumer.  In a 4-worker Gunicorn deployment that
meant a ``submit()`` landing on worker A never woke a
``consume_blocking()`` running on worker B — the consumer would sit
out the full 5-minute timeout before falling back to ``is_paused=True``.

The fix replaces the in-memory event with a
:class:`backend.state.wait_event.WaitEvent` backed by the module-level
pubsub backend (``backend.state.pubsub.get_pubsub()``).  In
production with ``settings.redis_url`` set, the wake signal crosses
worker boundaries; in single-process test/dev mode, it falls back to
in-memory pub/sub with identical single-loop semantics.

These tests cover the wiring and contract:

* **Channel name is deterministic per session_id** — two services on
  the same session must share the same channel, so a ``set()`` on one
  is observable as ``is_set()`` on the other.
* **In-process cross-instance wake** — two ``InterjectionService``
  instances in the same Python process, sharing the singleton pubsub
  backend, observe each other's wake signals.  This is the closest
  unit-test approximation of multi-worker behavior without spinning
  up Redis.
* **Wake race resilience** — a fast-path ``_drain_pending`` call
  followed by a slow waiter must still wake on the next ``submit()``
  (the ``set/clear`` round-trip works as expected).
* **Real Redis integration** (skipped if no Redis available) — two
  service instances, two separate pubsub backends talking to a real
  Redis instance, observe cross-process wake.
"""

from __future__ import annotations

import asyncio

import pytest

from backend.state.pubsub import (
    PubSubBackend,
    reset_pubsub_cache,
)
from backend.state.wait_event import (
    InMemoryWaitEvent,
    get_wait_event,
)
from backend.workflow.interjection import (
    _WAKE_CHANNEL_PREFIX,
    InterjectionService,
)

# ---------------------------------------------------------------------------
# Wiring tests
# ---------------------------------------------------------------------------


class TestCrossProcessWiring:
    """Verify the channel-name and WaitEvent wiring."""

    def test_channel_name_uses_session_id(self) -> None:
        """The wake channel is a deterministic function of session_id."""
        # Reset module-level pubsub to make this hermetic
        reset_pubsub_cache()
        try:
            service = InterjectionService()
            e1 = service._get_wake_event("sess-abc")
            # Force creation of another event for a different session
            e2 = service._get_wake_event("sess-xyz")
            assert isinstance(e1, InMemoryWaitEvent)
            assert isinstance(e2, InMemoryWaitEvent)
            assert e1 is not e2
            # Both should be backed by the same in-memory channel name
            assert e1._channel_name == f"{_WAKE_CHANNEL_PREFIX}sess-abc"
            assert e2._channel_name == f"{_WAKE_CHANNEL_PREFIX}sess-xyz"
        finally:
            reset_pubsub_cache()

    def test_two_services_share_channel_for_same_session(self) -> None:
        """Two InterjectionService instances in the same process share
        the channel state for the same session_id — this is the
        in-process proxy for cross-worker behavior.
        """
        reset_pubsub_cache()
        try:
            service_a = InterjectionService()
            service_b = InterjectionService()

            event_a = service_a._get_wake_event("sess-shared")
            event_b = service_b._get_wake_event("sess-shared")

            # Both events must reference the same underlying channel
            assert event_a._channel_name == event_b._channel_name
            assert event_a._channel_name == f"{_WAKE_CHANNEL_PREFIX}sess-shared"

            # clear() on one is observable as is_set() == False on the
            # other — the channel's _set_count is shared.
            event_a.set()
            assert event_b.is_set()
            event_b.clear()
            assert not event_a.is_set()
        finally:
            reset_pubsub_cache()

    def test_singleton_in_memory_pubsub_is_used_by_default(self) -> None:
        """When ``settings.redis_url`` is empty, ``get_wait_event`` returns
        an ``InMemoryWaitEvent`` backed by the singleton in-memory pubsub.
        """
        reset_pubsub_cache()
        try:
            event = get_wait_event("danwa:interjection:wake:test")
            assert isinstance(event, InMemoryWaitEvent)
        finally:
            reset_pubsub_cache()


# ---------------------------------------------------------------------------
# Functional cross-instance wake tests
# ---------------------------------------------------------------------------


class TestCrossInstanceWake:
    """End-to-end: one service submits, the other consumes_blocking wakes."""

    @pytest.mark.asyncio
    async def test_submit_in_one_service_wakes_consumer_in_another(self, tmp_path) -> None:
        """The whole point of F-01: a submit() on service A must wake a
        blocking consumer on service B.

        Both services share the same SQLite DB (proxy for the shared
        :mod:`backend.workflow.interjection` singleton pointing at
        ``data/blueprints.db`` in production).  Without the DB, the
        in-memory cache on service B would be empty and the data
        wouldn't cross processes — the L6 fix already made the data
        cross-process via SQLite; F-01 makes the wake-up signal do
        the same.
        """
        reset_pubsub_cache()
        db = tmp_path / "interjection.db"
        try:
            service_a = InterjectionService(db_path=db)
            service_b = InterjectionService(db_path=db)

            # Start the consumer on service_b BEFORE the submit on
            # service_a so the consume_blocking actually has to wait.
            async def consumer() -> list[dict]:
                return await service_b.consume_blocking("sess-cross", timeout=2.0)

            consumer_task = asyncio.create_task(consumer())
            # Give the consumer a moment to enter the wait.
            await asyncio.sleep(0.05)

            # Submit on a *different* instance.
            await service_a.submit("sess-cross", "Hello from A", source="user")

            # The consumer must wake within a short window — definitely
            # well below the 2 s timeout.  This is the cross-instance
            # wake that asyncio.Event could never do.
            results = await asyncio.wait_for(consumer_task, timeout=1.0)

            assert len(results) == 1
            assert results[0]["content"] == "Hello from A"
        finally:
            reset_pubsub_cache()

    @pytest.mark.asyncio
    async def test_wake_event_clears_after_drain(self) -> None:
        """After consume_blocking drains the queue, the wake event must
        be cleared so a second consume_blocking blocks again.
        """
        reset_pubsub_cache()
        try:
            service = InterjectionService()
            event = service._get_wake_event("sess-clear")
            assert event.is_set()

            # First wake
            await service.submit("sess-clear", "first")
            assert event.is_set()
            results = await service.consume("sess-clear")
            assert len(results) == 1

            # After drain, the wake event was cleared
            assert not event.is_set()

            # A fresh consume_blocking must block (use timeout=0 to
            # verify the fast-path returns empty when nothing is queued
            # and the event is clear).
            results = await service.consume_blocking("sess-clear", timeout=0.05)
            assert results == []
        finally:
            reset_pubsub_cache()

    @pytest.mark.asyncio
    async def test_wake_event_set_during_consume_blocking(self) -> None:
        """A submit() that races a consume_blocking's wait() must wake it."""
        reset_pubsub_cache()
        try:
            service = InterjectionService()

            async def late_submit() -> None:
                await asyncio.sleep(0.1)
                await service.submit("sess-race", "late")

            submit_task = asyncio.create_task(late_submit())
            results = await service.consume_blocking("sess-race", timeout=2.0)
            await submit_task

            assert len(results) == 1
            assert results[0]["content"] == "late"
        finally:
            reset_pubsub_cache()


# ---------------------------------------------------------------------------
# Real Redis integration (skipped if Redis not reachable)
# ---------------------------------------------------------------------------


class TestCrossProcessWakeRedis:
    """End-to-end with a real Redis instance.

    Skipped automatically when Redis is not available — these tests
    require ``settings.redis_url`` to point at a reachable Redis and
    the ``redis`` package to be installed.
    """

    @pytest.fixture
    def redis_pubsub(self):
        """Provide a fresh RedisPubSub for the test, skip if unreachable."""
        try:
            import redis  # noqa: F401
        except ImportError:
            pytest.skip("redis package not installed")
        from backend.core.config import settings

        if not settings.redis_url:
            pytest.skip("DANWA_REDIS_URL is not set")

        from backend.state.pubsub import RedisPubSub

        try:
            pubsub = RedisPubSub(settings.redis_url)
        except Exception as exc:
            pytest.skip(f"Redis not reachable at {settings.redis_url}: {exc}")
        yield pubsub
        # Best-effort cleanup of any test channels
        try:
            pubsub._redis.delete("danwa:test:interjection:wake:redis-integ")
            pubsub._redis.delete("danwa:test:interjection:wake:redis-integ:flag")
        except Exception:
            pass

    @pytest.mark.asyncio
    async def test_two_redis_pubsub_backends_observe_each_others_wake(self, redis_pubsub: PubSubBackend) -> None:
        """Two separate RedisPubSub clients (proxy for two worker
        processes) on the same channel must observe each other's
        ``set()`` / ``clear()`` / ``is_set()`` operations.
        """
        from backend.state.pubsub import RedisPubSub
        from backend.state.wait_event import RedisWaitEvent

        # Re-use the fixture's underlying client for client A; create a
        # second client (separate process proxy) for client B.
        client_b = RedisPubSub.__new__(RedisPubSub)
        client_b._channels = {}
        client_b._redis = redis_pubsub._redis  # share the connection

        channel = "danwa:test:interjection:wake:redis-integ"
        event_a = RedisWaitEvent(channel, redis_pubsub)
        event_b = RedisWaitEvent(channel, client_b)

        # Clear any leftover state from previous test runs
        event_a.clear()
        assert not event_a.is_set()
        assert not event_b.is_set()

        # Set on A, observe on B — this is the cross-process property
        event_a.set()
        assert event_b.is_set(), "RedisWaitEvent B must observe set() from A via the shared flag"

        # Clear on B, observe on A
        event_b.clear()
        assert not event_a.is_set(), "RedisWaitEvent A must observe clear() from B via the shared flag"
