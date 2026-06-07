"""WaitEvent — asyncio.Event equivalent backed by Pub/Sub.

The standard ``asyncio.Event`` is bound to a single event loop, so it
cannot be shared across processes.  ``WaitEvent`` provides the same
``wait()`` / ``set()`` / ``clear()`` semantics, but uses
``backend.state.pubsub`` for cross-process wake-up signals.

Each ``WaitEvent`` is bound to a pub/sub channel name (e.g.
``"danwa:wf:pause:<session_id>"``).  A ``set()`` publishes a message
on the channel; ``wait()`` listens for messages on the channel and
returns when one arrives.

The first ``set()`` after a ``clear()`` is what the waiter is blocked
on.  Multiple ``set()`` calls in a row are coalesced — there's no
queue of "I need to be set N times" semantics.  This matches
``asyncio.Event``.

Local proxy:
  * In the InMemory backend, ``wait()`` subscribes to the channel and
    blocks on a local ``asyncio.Queue``.  Same loop semantics as
    ``asyncio.Event`` plus a small overhead.
  * In the Redis backend, ``wait()`` subscribes via Redis and
    consumes messages.  ``is_set()`` is a local boolean, so polling
    ``is_set()`` is cheap.  ``set()`` sets the local boolean and
    publishes a single wake-up message; existing waiters consume
    it and return.

The class is intentionally not a singleton — callers own the lifetime
of a WaitEvent (create on first use, store, close on cleanup).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

from backend.state.pubsub import PubSubBackend, RedisPubSub, get_pubsub

logger = logging.getLogger(__name__)


class WaitEvent(Protocol):
    """asyncio.Event-equivalent that survives process boundaries."""

    def is_set(self) -> bool:
        """Return ``True`` if the event is currently set."""
        ...

    def set(self) -> None:
        """Set the event and wake all waiters."""
        ...

    def clear(self) -> None:
        """Clear the event so future wait calls block."""
        ...

    async def wait(self, timeout: float | None = None) -> bool:
        """Block until the event is set or ``timeout`` expires.

        Returns ``True`` if the event was set, ``False`` on timeout.
        Mirrors the Python 3.11+ ``asyncio.Event.wait(timeout)`` API.
        """
        ...

    async def aclose(self) -> None:
        """Release the underlying subscription.  Idempotent."""
        ...


# ---------------------------------------------------------------------------
# In-memory implementation
# ---------------------------------------------------------------------------


class InMemoryWaitEvent:
    """asyncio.Event wrapper, no Redis required.

    The pub/sub layer is used for the wake-up signal, but it's all
    in-process so the semantics are identical to a plain
    ``asyncio.Event``.

    State is read from the channel (``is_set()`` consults the
    per-channel ``_set_count``), so multiple WaitEvent instances
    on the same channel share the set state — this is the cross-
    instance property needed for multi-process coordination
    (test or future Redis).
    """

    def __init__(self, channel: str, pubsub: PubSubBackend) -> None:
        """Initialise the instance."""
        self._channel_name = channel
        self._pubsub = pubsub

    def _channel(self):
        """Return the underlying pub/sub channel."""
        return self._pubsub.channel(self._channel_name)

    def is_set(self) -> bool:
        """Return True if the event is currently set."""
        return self._channel().is_set()

    def set(self) -> None:
        """Set the event and wake all waiters."""
        # Synchronously bump the channel's set counter so
        # ``is_set()`` reflects the new state immediately.  Then
        # fire the publish as a background task to deliver the
        # wake-up message to current subscribers.  The split
        # means local ``is_set()`` is always consistent, and
        # remote waiters still get a wake-up.
        ch = self._channel()
        ch._set_count += 1
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ch.publish("set"))
        except RuntimeError:
            # No running loop — only ``is_set()`` semantics work;
            # message delivery is best-effort.
            pass

    def clear(self) -> None:
        """Clear the event so future wait() calls block."""
        self._channel().clear()

    async def wait(self, timeout: float | None = None) -> bool:
        """Block until the event is set or timeout expires."""
        # Fast path — the channel has been set since the last clear.
        if self.is_set():
            return True
        sub = self._channel().subscribe()
        try:
            if timeout is None:
                async for _msg in sub:
                    if self.is_set():
                        return True
                return self.is_set()
            # Bounded wait.  After each delivered message we
            # re-check ``is_set()`` because the publish for
            # ``set()`` is fired via ``loop.create_task`` — a
            # racing ``clear()`` can reset the channel's set
            # count back to 0 before the publish completes, in
            # which case the message is stale and we must keep
            # waiting.
            try:
                await asyncio.wait_for(self._drain_until_set(sub), timeout=timeout)
                return True
            except TimeoutError:
                return self.is_set()
        finally:
            await sub.close()
        return self.is_set()

    async def _drain_until_set(self, sub) -> None:
        """Iterate the subscription until the channel is set.

        ``asyncio.wait_for`` cancels this coroutine on timeout,
        which propagates through the subscription.  We do NOT
        swallow the cancellation — that would make wait_for
        think the task completed normally.

        Returns when ``is_set()`` is True.  Stale messages (where
        a racing ``clear()`` reset the channel's set count) are
        skipped via the ``continue`` inside ``async for``.
        """
        async for _msg in sub:
            if self.is_set():
                return
            # Stale message — keep waiting for a fresh set signal.

    async def aclose(self) -> None:
        """Release the underlying subscription. Idempotent."""
        # No persistent resources in in-memory.
        return None


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------


class RedisWaitEvent:
    """WaitEvent backed by Redis pub/sub.

    State is shared via the per-channel flag counter in Redis
    (``is_set()`` reads the counter, ``clear()`` deletes it).
    Multiple WaitEvent instances on the same channel in
    different processes share the set state — this is the
    multi-process property the migration is about.
    """

    def __init__(self, channel: str, pubsub: PubSubBackend) -> None:
        """Initialise the instance."""
        self._channel_name = channel
        self._pubsub = pubsub
        self._active_subscriptions: list = []

    def _channel(self):
        """Return the underlying pub/sub channel."""
        return self._pubsub.channel(self._channel_name)

    def is_set(self) -> bool:
        """Return True if the event is currently set."""
        return self._channel().is_set()

    def set(self) -> None:
        """Set the event and wake all waiters."""
        # In the Redis case, ``publish()`` increments the flag
        # atomically, but only after the await.  We can do a
        # synchronous INCR here to make ``is_set()`` consistent
        # immediately.  Then fire the publish for message delivery.
        ch = self._channel()
        try:
            ch._redis.incr(ch._flag_key)
        except Exception:
            pass
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(ch.publish("set"))
        except RuntimeError:
            pass

    def clear(self) -> None:
        """Clear the event so future wait() calls block."""
        self._channel().clear()

    async def wait(self, timeout: float | None = None) -> bool:
        """Block until the event is set or timeout expires."""
        if self.is_set():
            return True
        sub = self._channel().subscribe()
        self._active_subscriptions.append(sub)
        try:
            if timeout is None:
                async for _msg in sub:
                    if self.is_set():
                        return True
                return self.is_set()
            try:
                await asyncio.wait_for(self._drain_until_set(sub), timeout=timeout)
                return True
            except TimeoutError:
                return self.is_set()
        finally:
            try:
                self._active_subscriptions.remove(sub)
            except ValueError:
                pass
            await sub.close()
        return self.is_set()

    async def _drain_until_set(self, sub) -> None:
        """Iterate the subscription until the channel is set.

        Stale messages (where a racing ``clear()`` deleted the
        channel flag) are skipped by the ``continue`` inside
        ``async for``.
        """
        async for _msg in sub:
            if self.is_set():
                return

    async def aclose(self) -> None:
        """Close any lingering subscriptions. Idempotent."""
        # Close any lingering subscriptions
        for sub in list(self._active_subscriptions):
            try:
                await sub.close()
            except Exception:
                logger.debug("Subscription close failed", exc_info=True)
        self._active_subscriptions.clear()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_wait_event(channel: str, pubsub: PubSubBackend | None = None) -> WaitEvent:
    """Create a WaitEvent on the given channel.

    The channel name is the unique key — two WaitEvents on the same
    channel share the same set/clear state across processes.  Use a
    session-scoped channel like ``"danwa:wf:pause:<session_id>"``.

    If ``pubsub`` is not provided, ``get_pubsub()`` is called.
    """
    if pubsub is None:
        pubsub = get_pubsub()
    # Type-dispatch on the impl class — same protocol, different
    # concrete behavior.
    if isinstance(pubsub, RedisPubSub):
        return RedisWaitEvent(channel, pubsub)
    return InMemoryWaitEvent(channel, pubsub)
