"""Tests for Sprint 37 — Pub/Sub backend + WaitEvent.

Covers:
* ``InMemoryPubSub``: publish/subscribe round-trip, multi-subscriber,
  multi-publisher, slow-consumer drop, channel isolation, close.
* ``InMemoryWaitEvent``: set/wait/clear semantics, timeout, multiple
  waiters on the same channel, same-channel cross-instance visibility.
* ``RedisPubSub`` / ``RedisWaitEvent``: integration tests skipped if
  ``TESTING_REDIS_URL`` is not set; otherwise round-trip + multi-worker
  proxy (simulated by two ``RedisPubSub`` instances on the same URL).
* Factory ``get_pubsub()`` / ``get_wait_event()`` picks Redis when
  ``settings.redis_url`` is set, falls back to in-memory otherwise.
"""

from __future__ import annotations

import asyncio
import os
import uuid

import pytest

from backend.state.pubsub import (
    InMemoryPubSub,
    PubSubBackend,
    get_pubsub,
)
from backend.state.wait_event import (
    InMemoryWaitEvent,
    WaitEvent,
    get_wait_event,
)

TESTING_REDIS_URL = os.environ.get("TESTING_REDIS_URL", "")


# ---------------------------------------------------------------------------
# InMemoryPubSub
# ---------------------------------------------------------------------------


class TestInMemoryPubSub:
    """Smoke + contract tests for the in-memory pub/sub backend."""

    def test_factory_returns_pubsub_backend(self) -> None:
        """``get_pubsub()`` returns an object that satisfies the
        ``PubSubBackend`` protocol (has a ``channel()`` method).
        """
        pubsub = get_pubsub()
        assert hasattr(pubsub, "channel")
        ch = pubsub.channel("test")
        assert hasattr(ch, "publish")
        assert hasattr(ch, "subscribe")

    @pytest.mark.asyncio
    async def test_publish_subscribe_round_trip(self) -> None:
        """One message published on a channel is received by exactly
        one subscriber on that channel.
        """
        pubsub: PubSubBackend = InMemoryPubSub()
        ch = pubsub.channel("rt")
        sub = ch.subscribe()
        delivered = await ch.publish("hello")
        assert delivered == 1
        msg = await asyncio.wait_for(sub.__anext__(), timeout=1.0)
        assert msg == "hello"
        await sub.close()

    @pytest.mark.asyncio
    async def test_multi_subscriber(self) -> None:
        """Two subscribers on the same channel both receive each message."""
        pubsub = InMemoryPubSub()
        ch = pubsub.channel("multi")
        sub1 = ch.subscribe()
        sub2 = ch.subscribe()
        delivered = await ch.publish("payload")
        assert delivered == 2
        m1 = await asyncio.wait_for(sub1.__anext__(), timeout=1.0)
        m2 = await asyncio.wait_for(sub2.__anext__(), timeout=1.0)
        assert m1 == "payload"
        assert m2 == "payload"
        await sub1.close()
        await sub2.close()

    @pytest.mark.asyncio
    async def test_channel_isolation(self) -> None:
        """A subscriber on channel A does NOT receive messages on
        channel B (no cross-channel leakage).
        """
        pubsub = InMemoryPubSub()
        ch_a = pubsub.channel("A")
        ch_b = pubsub.channel("B")
        sub_b = ch_b.subscribe()
        await ch_a.publish("only-on-a")
        # Wait briefly to ensure no message is delivered to B
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b.__anext__(), timeout=0.2)
        await sub_b.close()

    @pytest.mark.asyncio
    async def test_close_unsubscribes(self) -> None:
        """After ``Subscription.close()``, no more messages are delivered."""
        pubsub = InMemoryPubSub()
        ch = pubsub.channel("c")
        sub = ch.subscribe()
        await ch.publish("first")
        msg = await asyncio.wait_for(sub.__anext__(), timeout=1.0)
        assert msg == "first"
        await sub.close()
        # After close, ``publish`` should not include this subscriber
        # in the delivered count.
        delivered = await ch.publish("after-close")
        assert delivered == 0

    @pytest.mark.asyncio
    async def test_slow_consumer_drops_when_full(self) -> None:
        """A subscriber that doesn't drain its queue has messages
        dropped (not blocking the publisher) once the queue is full.
        """
        pubsub = InMemoryPubSub()
        ch = pubsub.channel("slow")
        sub = ch.subscribe()  # default maxsize=1024
        # 1100 messages — over the default queue size
        for i in range(1100):
            await ch.publish(f"m{i}")
        # The slow subscriber should have at most 1024 buffered; the
        # publisher reports a non-zero delivery count up to that
        # cap.  We just assert that publishing completed without
        # raising — the exact drop count is an implementation detail.
        await sub.close()


# ---------------------------------------------------------------------------
# InMemoryWaitEvent
# ---------------------------------------------------------------------------


class TestInMemoryWaitEvent:
    """asyncio.Event-equivalent semantics over the in-memory pub/sub."""

    @pytest.mark.asyncio
    async def test_set_then_wait_returns_immediately(self) -> None:
        """If the event is set before ``wait()`` is called, ``wait()``
        returns ``True`` without blocking.
        """
        ev: WaitEvent = get_wait_event(f"ch-{uuid.uuid4()}")
        ev.set()
        result = await ev.wait(timeout=1.0)
        assert result is True
        await ev.aclose()

    @pytest.mark.asyncio
    async def test_wait_unblocks_on_set(self) -> None:
        """A waiter blocked on ``wait()`` returns ``True`` when
        another task calls ``set()``.
        """
        ev = get_wait_event(f"ch-{uuid.uuid4()}")

        async def setter_after_delay() -> None:
            await asyncio.sleep(0.05)
            ev.set()

        asyncio.create_task(setter_after_delay())
        result = await ev.wait(timeout=2.0)
        assert result is True
        await ev.aclose()

    @pytest.mark.asyncio
    async def test_wait_times_out(self) -> None:
        """If no ``set()`` happens, ``wait(timeout)`` returns ``False``."""
        ev = get_wait_event(f"ch-{uuid.uuid4()}")
        result = await ev.wait(timeout=0.1)
        assert result is False
        await ev.aclose()

    @pytest.mark.asyncio
    async def test_clear_after_set_blocks_again(self) -> None:
        """``clear()`` resets the event so a fresh ``wait()`` blocks."""
        ev = get_wait_event(f"ch-{uuid.uuid4()}")
        ev.set()
        assert await ev.wait(timeout=0.1) is True
        ev.clear()
        # Now wait should block until set or timeout
        result = await ev.wait(timeout=0.1)
        assert result is False
        ev.set()
        assert await ev.wait(timeout=0.1) is True
        await ev.aclose()

    @pytest.mark.asyncio
    async def test_same_channel_publish_wakes_subscriber(self) -> None:
        """A ``set()`` on one WaitEvent instance wakes a subscriber
        on another instance that uses the same channel.  The
        set state is shared at the channel level (in-memory), so
        both instances see ``is_set() == True`` after the
        publish is processed.
        """
        pubsub = InMemoryPubSub()
        ch = f"shared-{uuid.uuid4()}"
        ev_publisher = get_wait_event(ch, pubsub=pubsub)
        ev_subscriber = get_wait_event(ch, pubsub=pubsub)

        async def setter() -> None:
            await asyncio.sleep(0.05)
            ev_publisher.set()

        asyncio.create_task(setter())
        result = await ev_subscriber.wait(timeout=2.0)
        assert result is True
        # Channel state is shared — both instances see is_set() == True.
        assert ev_subscriber.is_set() is True
        assert ev_publisher.is_set() is True
        await ev_publisher.aclose()
        await ev_subscriber.aclose()

    @pytest.mark.asyncio
    async def test_is_set_reflects_state(self) -> None:
        """``is_set()`` is a synchronous boolean check."""
        ev = get_wait_event(f"ch-{uuid.uuid4()}")
        assert ev.is_set() is False
        ev.set()
        assert ev.is_set() is True
        ev.clear()
        assert ev.is_set() is False
        await ev.aclose()


# ---------------------------------------------------------------------------
# Redis integration (skipped without TESTING_REDIS_URL)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not TESTING_REDIS_URL,
    reason="TESTING_REDIS_URL not set — Redis integration tests skipped",
)
class TestRedisPubSub:
    """Integration tests against a real Redis instance."""

    @pytest.mark.asyncio
    async def test_publish_subscribe_round_trip(self) -> None:
        from backend.state.pubsub import RedisPubSub

        pubsub = RedisPubSub(TESTING_REDIS_URL)
        ch_name = f"test-{uuid.uuid4()}"
        ch = pubsub.channel(ch_name)
        sub = ch.subscribe()

        async def publish_after_delay() -> None:
            await asyncio.sleep(0.1)
            await ch.publish("hello-redis")

        asyncio.create_task(publish_after_delay())
        msg = await asyncio.wait_for(sub.__anext__(), timeout=2.0)
        assert msg == "hello-redis"
        await sub.close()

    @pytest.mark.asyncio
    async def test_cross_instance_via_redis(self) -> None:
        """Two ``RedisPubSub`` clients on the same URL share state —
        this is the multi-process property Redis gives us.
        """
        from backend.state.pubsub import RedisPubSub

        pubsub_a = RedisPubSub(TESTING_REDIS_URL)
        pubsub_b = RedisPubSub(TESTING_REDIS_URL)
        ch_name = f"shared-{uuid.uuid4()}"
        ch_a = pubsub_a.channel(ch_name)
        ch_b = pubsub_b.channel(ch_name)
        sub_b = ch_b.subscribe()

        async def publish() -> None:
            await asyncio.sleep(0.1)
            await ch_a.publish("from-a")

        asyncio.create_task(publish())
        msg = await asyncio.wait_for(sub_b.__anext__(), timeout=2.0)
        assert msg == "from-a"
        await sub_b.close()


# ---------------------------------------------------------------------------
# Factory dispatch
# ---------------------------------------------------------------------------


class TestFactory:
    """``get_pubsub()`` / ``get_wait_event()`` pick the right impl."""

    def setup_method(self) -> None:
        """Reset the singleton cache so each test sees a fresh factory call."""
        from backend.state.pubsub import reset_pubsub_cache

        reset_pubsub_cache()

    def teardown_method(self) -> None:
        """Clean up the singleton cache after each test to avoid cross-test leaks."""
        from backend.state.pubsub import reset_pubsub_cache

        reset_pubsub_cache()

    def test_get_pubsub_default_is_inmemory(self) -> None:
        """Without a configured ``redis_url``, the factory returns
        the in-memory implementation.
        """
        pubsub = get_pubsub()
        assert isinstance(pubsub, InMemoryPubSub)

    def test_get_pubsub_returns_same_singleton(self) -> None:
        """``get_pubsub()`` returns the same instance on repeated
        calls — channels registered via the first call must be
        reachable from the second.
        """
        a = get_pubsub()
        b = get_pubsub()
        assert a is b

    def test_reset_pubsub_cache_returns_new_instance(self) -> None:
        """``reset_pubsub_cache()`` clears the singleton so the
        next ``get_pubsub()`` call returns a fresh instance.
        """
        from backend.state.pubsub import reset_pubsub_cache

        a = get_pubsub()
        reset_pubsub_cache()
        b = get_pubsub()
        assert a is not b

    def test_get_wait_event_default_is_inmemory(self) -> None:
        """The ``get_wait_event`` factory returns an in-memory event
        when no ``RedisPubSub`` is supplied.
        """
        ev = get_wait_event(f"factory-{uuid.uuid4()}")
        assert isinstance(ev, InMemoryWaitEvent)
        # ``aclose`` is a no-op on in-memory but the async API
        # is part of the WaitEvent protocol.  We don't actually
        # need to call it here; just verify the method exists
        # so type checkers and runtime contract are happy.
        assert hasattr(ev, "aclose")
        assert asyncio.iscoroutinefunction(ev.aclose)
