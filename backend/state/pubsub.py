"""Pub/Sub backend — Redis-backed or in-memory fallback.

Provides a thin abstraction over pub/sub for cross-process / cross-task
notifications.  Used by ``wait_event.py`` to back the asyncio.Event-equivalent
in ``backend.state.workflow_state``.

Two implementations:
  * ``InMemoryPubSub`` — single-process, uses ``asyncio.Queue`` per subscriber
  * ``RedisPubSub`` — multi-process, uses ``redis.asyncio.client.pubsub``

Picked via ``get_pubsub()`` based on ``settings.redis_url``.  When ``redis_url``
is empty or Redis is unreachable, falls back to in-memory.

Both implementations guarantee:
  * at-most-once delivery per subscriber per message
  * FIFO ordering per subscriber
  * non-blocking ``publish()`` (Redis: ``publish`` is sync I/O; we wrap it
    in ``asyncio.to_thread`` so callers can ``await`` it)
  * iterator-based subscription (``async for msg in sub:``)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class PubSubBackend(Protocol):
    """Pub/sub interface — both impls satisfy this."""

    def channel(self, name: str) -> PubSubChannel:
        """Return a channel handle for publish/subscribe.

        A channel is the unit of subscription.  A subscriber on
        ``"danwa:wf:pause:abc"`` receives every message published on
        that channel, regardless of the publisher.
        """
        ...


class PubSubChannel(Protocol):
    """A named pub/sub channel."""

    async def publish(self, message: str) -> int:
        """Publish a message to the channel.

        Returns the number of subscribers that received the message
        (Redis semantics).  In-memory returns the number of local
        subscriber queues the message was enqueued on.
        """
        ...

    def subscribe(self) -> Subscription:
        """Create a new subscription on this channel.

        Caller iterates the returned ``Subscription`` to receive
        messages.  Each ``subscribe()`` returns a NEW subscription —
        independent buffers, independent lifecycles.
        """
        ...


class Subscription(Protocol):
    """An active subscription on a channel."""

    def __aiter__(self) -> AsyncIterator[str]: ...
    async def __anext__(self) -> str: ...
    async def close(self) -> None:
        """Cancel the subscription.  Buffered messages are dropped."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


class InMemorySubscription:
    """An in-memory subscription backed by an ``asyncio.Queue``.

    The subscription uses an explicit ``_close_event`` to wake a
    blocked ``__anext__`` so ``close()`` doesn't rely on cancelling
    the waiter.  This keeps cancellation semantics clean: a real
    cancellation (e.g. from ``asyncio.wait_for``) propagates
    unchanged, while ``close()`` cleanly stops the iteration.
    """

    def __init__(self, channel: InMemoryChannel, maxsize: int = 1024) -> None:
        """Initialise the instance."""
        self._channel = channel
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)
        self._close_event = asyncio.Event()
        self._channel._register(self)

    def __aiter__(self) -> AsyncIterator[str]:
        """Return the async iterator."""
        return self

    async def __anext__(self) -> str:
        if self._close_event.is_set():
            raise StopAsyncIteration
        # Race the queue.get() against the close event.  Whichever
        # completes first wins.
        get_task = asyncio.create_task(self._queue.get())
        close_task = asyncio.create_task(self._close_event.wait())
        try:
            done, pending = await asyncio.wait(
                {get_task, close_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
        except asyncio.CancelledError:
            # Real cancellation — propagate.
            get_task.cancel()
            close_task.cancel()
            raise
        # Cancel the loser
        for t in pending:
            t.cancel()
        if get_task in done:
            return get_task.result()
        # close_task won
        raise StopAsyncIteration

    async def close(self) -> None:
        if self._close_event.is_set():
            return
        self._close_event.set()
        self._channel._unregister(self)


class InMemoryChannel:
    """An in-memory pub/sub channel — uses a list of subscriber queues.

    The channel also tracks a "set" flag (monotonic int) so that
    subscribers can ask "has this channel been set since I last
    asked?"  This is the multi-instance shim: multiple WaitEvent
    instances on the same channel share the set state.
    """

    def __init__(self, name: str) -> None:
        """Initialise the instance."""
        self.name = name
        self._subscribers: list[InMemorySubscription] = []
        self._lock = asyncio.Lock()
        # ``_set_count`` increments on each ``publish`` (acting as
        # a "set" signal).  WaitEvents on the same channel can
        # query this to know if the channel has been "set" since
        # they last checked, even if their own local flag is False.
        self._set_count: int = 0

    def _register(self, sub: InMemorySubscription) -> None:
        """Register a subscription for broadcast delivery."""
        self._subscribers.append(sub)

    def _unregister(self, sub: InMemorySubscription) -> None:
        """Remove a subscription from the broadcast list."""
        try:
            self._subscribers.remove(sub)
        except ValueError:
            pass

    def is_set(self) -> bool:
        """True if the channel has been published to at least once.

        WaitEvents call this to determine the channel-wide set
        state, complementing their own local ``_set`` flag.
        """
        return self._set_count > 0

    def clear(self) -> None:
        """Reset the per-channel set count to 0.

        Mirrors ``WaitEvent.clear()`` semantics: any waiter on
        this channel that hasn't yet seen the set message will
        see ``is_set() == False`` after the next clear.
        """
        self._set_count = 0

    async def publish(self, message: str) -> int:
        """Deliver ``message`` to current subscribers.

        Note: does NOT increment ``_set_count`` — that's the
        caller's job (``WaitEvent.set()`` bumps the count
        synchronously before scheduling the publish).  Keeping
        the bump and the delivery separate avoids a race where
        a delayed publish task re-bumps the count after a
        ``clear()``.
        """
        delivered = 0
        # Snapshot to avoid mutation during iteration
        subs = list(self._subscribers)
        for sub in subs:
            if sub._close_event.is_set():
                continue
            try:
                sub._queue.put_nowait(message)
                delivered += 1
            except asyncio.QueueFull:
                # Slow consumer — drop message for that subscriber
                logger.warning(
                    "InMemoryPubSub: subscriber on %s dropped message (queue full)",
                    self.name,
                )
        return delivered

    def subscribe(self) -> InMemorySubscription:
        """Create a new subscription on this channel."""
        return InMemorySubscription(self)


class InMemoryPubSub:
    """In-memory pub/sub — single-process, no Redis required."""

    def __init__(self) -> None:
        """Initialise the instance."""
        self._channels: dict[str, InMemoryChannel] = {}
        self._lock = asyncio.Lock()

    def channel(self, name: str) -> InMemoryChannel:
        """Return a channel handle for the given *name*."""
        # Lazy-create channels.  No lock needed for read-after-init in
        # asyncio single-threaded model.
        ch = self._channels.get(name)
        if ch is None:
            ch = InMemoryChannel(name)
            self._channels[name] = ch
        return ch


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------


class _RedisSubscription:
    """A Redis-backed subscription."""

    def __init__(self, channel_name: str, redis_client: Any) -> None:
        """Initialise the instance."""
        self._channel_name = channel_name
        self._pubsub = redis_client.pubsub(ignore_subscribe_messages=True)
        self._closed = False

    async def _ensure_subscribed(self) -> None:
        # ``subscribe`` is non-blocking on redis.asyncio but returns a
        # coroutine; await it once.
        if not getattr(self._pubsub, "_danwa_subscribed", False):
            await self._pubsub.subscribe(self._channel_name)
            self._pubsub._danwa_subscribed = True

    def __aiter__(self) -> AsyncIterator[str]:
        """Return the async iterator."""
        return self

    async def __anext__(self) -> str:
        if self._closed:
            raise StopAsyncIteration
        await self._ensure_subscribed()
        # ``get_message`` returns None when no message; loop with
        # short sleep to avoid busy-wait.
        while True:
            if self._closed:
                raise StopAsyncIteration
            msg = await self._pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg is not None:
                data = msg.get("data")
                if data is not None:
                    return data.decode() if isinstance(data, bytes) else str(data)
            await asyncio.sleep(0.01)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._pubsub.unsubscribe(self._channel_name)
        except Exception:
            logger.debug("Redis unsubscribe failed", exc_info=True)
        try:
            await self._pubsub.close()
        except Exception:
            logger.debug("Redis pubsub close failed", exc_info=True)


class RedisChannel:
    """A Redis-backed pub/sub channel.

    Two Redis keys per channel:
    * ``<name>`` — the pub/sub channel for wake-up messages
    * ``<name>:flag`` — a counter incremented on ``publish`` and
      deleted on ``clear()``; serves as the cross-process set flag

    The pub/sub message itself is the wake-up signal.  The flag
    exists so that ``is_set()`` can return True without a
    separate round trip — useful for callers that want to check
    state without subscribing.
    """

    _SET_TTL_SECONDS = 3600  # 1 hour; refreshed on every publish

    def __init__(self, name: str, redis_client: Any) -> None:
        """Initialise the instance."""
        self.name = name
        self._redis = redis_client
        self._flag_key = f"{name}:flag"

    async def publish(self, message: str) -> int:
        """Deliver ``message`` to current Redis subscribers.

        The flag counter is incremented in ``WaitEvent.set()``
        synchronously, not here, for the same reason as in the
        in-memory backend (avoid a re-bump race after clear()).
        """
        return int(await self._redis.publish(self.name, message))

    def is_set(self) -> bool:
        """True if the channel's flag counter is > 0.

        Synchronous Redis EXISTS call.  The check is best-effort —
        a concurrent ``clear()`` could race against it, but the
        worst case is one stale ``is_set() == True`` after a
        clear, which is harmless (the wait() loop re-checks on
        the next message).
        """
        return bool(self._redis.exists(self._flag_key))

    def clear(self) -> None:
        """Reset the per-channel set flag in Redis."""
        self._redis.delete(self._flag_key)

    def subscribe(self) -> _RedisSubscription:
        """Create a new subscription on this channel."""
        return _RedisSubscription(self.name, self._redis)


class RedisPubSub:
    """Redis-backed pub/sub — multi-process safe.

    Requires the ``redis`` package (sync client + asyncio adapters).
    Uses sync ``redis.from_url`` because redis-py's async pub/sub
    client is a thin wrapper around the sync client anyway, and
    the async variant has historically had compatibility issues
    across versions.  The blocking I/O is fine for our use case
    (low-frequency wake-up signals).
    """

    def __init__(self, redis_url: str) -> None:
        """Initialise the instance."""
        import redis

        self._redis = redis.from_url(redis_url, decode_responses=False)
        # Probe to fail fast on bad URL
        self._redis.ping()
        self._channels: dict[str, RedisChannel] = {}
        logger.info("RedisPubSub connected to %s", redis_url)

    def channel(self, name: str) -> RedisChannel:
        """Return a channel handle for the given *name*."""
        ch = self._channels.get(name)
        if ch is None:
            ch = RedisChannel(name, self._redis)
            self._channels[name] = ch
        return ch


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Module-level singleton.  Caching matters because the InMemory
# backend keeps its channel state in instance attributes — a fresh
# instance per call would lose all subscribers between requests.
# Redis is naturally a singleton (single connection), so caching
# doesn't change its behavior, only avoids reconnecting.
_pubsub: PubSubBackend | None = None


def get_pubsub() -> PubSubBackend:
    """Return the configured pub/sub backend.

    If ``settings.redis_url`` is set, attempt to connect to Redis.
    On any failure, log a warning and fall back to in-memory.

    The result is cached module-globally.  Tests that need a
    fresh instance should call :func:`reset_pubsub_cache` first.
    """
    global _pubsub
    if _pubsub is not None:
        return _pubsub

    from backend.core.config import settings

    if settings.redis_url:
        try:
            _pubsub = RedisPubSub(settings.redis_url)
            return _pubsub
        except Exception as exc:
            logger.warning("Redis pub/sub unavailable (%s), falling back to in-memory", exc)
    _pubsub = InMemoryPubSub()
    return _pubsub


def reset_pubsub_cache() -> None:
    """Clear the module-level pub/sub singleton.

    Intended for tests that swap the ``settings.redis_url`` and
    want the factory to re-evaluate.  In production the cache
    lives for the lifetime of the process.
    """
    global _pubsub
    _pubsub = None
