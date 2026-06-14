"""Tests for P4.5+ §4.10 — best-effort but loud pub/sub failures.

The pub/sub layer is fire-and-forget by design: a slow or
unreachable Redis must not block a wake-up signal.  But the
swallow points used to be silent — operators had no signal that
the cross-process notification channel was chronically broken.

§4.10 introduces:
  * a module-level cumulative counter ``_publish_failures``
    exposed via :func:`backend.state.pubsub.get_publish_failure_count`
  * a per-``(channel, op)`` throttling set: the first failure is
    logged at ``error`` (with traceback), subsequent ones at
    ``debug``
  * a :func:`backend.state.pubsub.reset_publish_failure_count`
    for tests that need a clean baseline

These tests cover:
  * the counter starts at 0 and is per-process
  * :func:`reset_publish_failure_count` returns the previous value
  * the in-memory ``QueueFull`` path increments the counter
  * the ``RedisChannel.{publish,is_set,clear,set_count}`` swallow
    points increment the counter
  * the throttling behaviour: first failure logs at ``error``,
    subsequent at ``debug``
  * per-channel isolation: failures on channel A do not suppress
    failures on channel B
  * the :func:`get_pubsub` Redis-init fallback counts its failure
    via a synthetic ``"__init__"`` channel key

All Redis-channel tests use a MagicMock that raises on the
specific method we want to exercise, so they run in CI without a
real Redis.  The Redis wrapper logic in production is identical
to the in-memory one: ``try: ...; except Exception: _record_...``.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from backend.state import pubsub
from backend.state.pubsub import (
    InMemoryPubSub,
    RedisChannel,
    _record_publish_failure,
    get_publish_failure_count,
    reset_publish_failure_count,
)

# ---------------------------------------------------------------------------
# Module-level counter
# ---------------------------------------------------------------------------


class TestFailureCounter:
    """The module-level counter is the public diagnostic signal."""

    def setup_method(self) -> None:
        """Reset the counter before every test for a clean baseline."""
        reset_publish_failure_count()

    def teardown_method(self) -> None:
        """Reset the counter after every test so other test files
        that touch the pubsub module (e.g. interjection tests)
        start with a clean slate."""
        reset_publish_failure_count()

    def test_counter_starts_at_zero(self) -> None:
        """A fresh process has zero recorded failures."""
        assert get_publish_failure_count() == 0

    def test_record_publish_failure_increments(self) -> None:
        """Each call to :func:`_record_publish_failure` bumps the
        counter by one — even on the throttled path.
        """
        assert get_publish_failure_count() == 0
        _record_publish_failure("ch-1", "publish", RuntimeError("boom"))
        assert get_publish_failure_count() == 1
        _record_publish_failure("ch-1", "publish", RuntimeError("boom2"))
        assert get_publish_failure_count() == 2
        _record_publish_failure("ch-1", "publish", RuntimeError("boom3"))
        assert get_publish_failure_count() == 3

    def test_reset_returns_previous_value(self) -> None:
        """``reset_publish_failure_count()`` returns the value the
        counter held *before* the reset, so callers can assert
        on the delta.
        """
        _record_publish_failure("ch", "publish", RuntimeError("x"))
        _record_publish_failure("ch", "publish", RuntimeError("y"))
        assert get_publish_failure_count() == 2
        previous = reset_publish_failure_count()
        assert previous == 2
        assert get_publish_failure_count() == 0

    def test_counter_survives_pubsub_cache_reset(self) -> None:
        """``reset_pubsub_cache()`` (separate from
        ``reset_publish_failure_count``) must NOT clear the
        failure counter.  Rationale: a fresh backend on the
        same broken Redis would just keep failing — clearing
        the count would mask that.
        """
        _record_publish_failure("ch", "publish", RuntimeError("x"))
        assert get_publish_failure_count() == 1
        pubsub.reset_pubsub_cache()
        assert get_publish_failure_count() == 1


# ---------------------------------------------------------------------------
# Throttling — first failure error, subsequent debug
# ---------------------------------------------------------------------------


class TestPerChannelThrottling:
    """The first failure for a (channel, op) pair is loud, the rest are quiet."""

    def setup_method(self) -> None:
        reset_publish_failure_count()

    def teardown_method(self) -> None:
        reset_publish_failure_count()

    def test_first_failure_logs_at_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """The first failure for a (channel, op) pair is logged at
        ``error`` (with traceback) so it shows up in standard
        ``ERROR``-level alerting.
        """
        caplog.set_level(logging.DEBUG, logger="backend.state.pubsub")
        _record_publish_failure("ch-A", "publish", RuntimeError("first"))
        # The error-level record must be present
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) >= 1
        # And the message must mention the channel
        assert any("ch-A" in r.getMessage() for r in error_records)
        # And include a traceback (exc_info=True) — records have exc_info set
        assert any(r.exc_info is not None for r in error_records)

    def test_subsequent_failures_log_at_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """Subsequent failures for the same (channel, op) pair drop
        to ``debug`` so a persistent outage doesn't drown the log.
        """
        caplog.set_level(logging.DEBUG, logger="backend.state.pubsub")
        _record_publish_failure("ch-B", "publish", RuntimeError("first"))
        caplog.clear()
        # Second and third failure on the same (channel, op) pair
        _record_publish_failure("ch-B", "publish", RuntimeError("second"))
        _record_publish_failure("ch-B", "publish", RuntimeError("third"))
        # No NEW error-level records should have been emitted
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert error_records == []
        # But the debug records must be there
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) >= 2
        assert any("suppressed" in r.getMessage() for r in debug_records)

    def test_throttling_is_per_channel(self, caplog: pytest.LogCaptureFixture) -> None:
        """Failures on channel A do not suppress failures on
        channel B — operators need to see *every* distinct
        channel that is misbehaving.
        """
        caplog.set_level(logging.DEBUG, logger="backend.state.pubsub")
        # Two failures on channel A
        _record_publish_failure("ch-A", "publish", RuntimeError("a1"))
        _record_publish_failure("ch-A", "publish", RuntimeError("a2"))
        # First failure on channel B — should still be at error level
        caplog.clear()
        _record_publish_failure("ch-B", "publish", RuntimeError("b1"))
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "ch-B" in error_records[0].getMessage()

    def test_throttling_is_per_op_within_channel(self, caplog: pytest.LogCaptureFixture) -> None:
        """A failure on (channel, publish) does not suppress a
        failure on the same (channel, clear) — different ops
        are independent.
        """
        caplog.set_level(logging.DEBUG, logger="backend.state.pubsub")
        _record_publish_failure("ch-X", "publish", RuntimeError("p1"))
        _record_publish_failure("ch-X", "publish", RuntimeError("p2"))
        caplog.clear()
        _record_publish_failure("ch-X", "clear", RuntimeError("c1"))
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "clear" in error_records[0].getMessage()

    def test_reset_clears_throttle_set(self, caplog: pytest.LogCaptureFixture) -> None:
        """``reset_publish_failure_count()`` clears the throttle
        set so the *next* failure on a previously-logged channel
        is logged again at ``error`` level.
        """
        caplog.set_level(logging.DEBUG, logger="backend.state.pubsub")
        _record_publish_failure("ch-Y", "publish", RuntimeError("y1"))
        _record_publish_failure("ch-Y", "publish", RuntimeError("y2"))
        reset_publish_failure_count()
        caplog.clear()
        _record_publish_failure("ch-Y", "publish", RuntimeError("y3"))
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1


# ---------------------------------------------------------------------------
# InMemoryChannel.publish — QueueFull path counts
# ---------------------------------------------------------------------------


class TestInMemoryQueueFullCounts:
    """Slow-consumer drops in the in-memory backend are counted."""

    def setup_method(self) -> None:
        reset_publish_failure_count()

    def teardown_method(self) -> None:
        reset_publish_failure_count()

    @pytest.mark.asyncio
    async def test_queue_full_increments_counter(self, caplog: pytest.LogCaptureFixture) -> None:
        """When a subscriber's queue fills up, the drop is
        counted via the module-level counter.  We use a
        low-maxsize queue (4 messages) and publish 10 to
        guarantee multiple drops.
        """
        caplog.set_level(logging.WARNING, logger="backend.state.pubsub")
        pubsub_backend = InMemoryPubSub()
        ch = pubsub_backend.channel("slow")
        sub = ch.subscribe()  # default maxsize=1024
        # Publish 1100 messages — at least 76 should be dropped
        delivered_total = 0
        for i in range(1100):
            delivered_total += await ch.publish(f"m{i}")
        # At least one drop should have happened
        assert delivered_total < 1100
        # Counter must have ticked
        assert get_publish_failure_count() >= 1
        # And the existing warning must still be there
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("queue full" in r.getMessage() for r in warning_records)
        await sub.close()

    @pytest.mark.asyncio
    async def test_publish_succeeds_when_consumer_keeps_up(self) -> None:
        """Sanity check: a normal (non-full) publish does NOT
        increment the counter — only the failure path does.
        """
        pubsub_backend = InMemoryPubSub()
        ch = pubsub_backend.channel("normal")
        sub = ch.subscribe()
        for i in range(5):
            await ch.publish(f"m{i}")
        assert get_publish_failure_count() == 0
        await sub.close()


# ---------------------------------------------------------------------------
# RedisChannel swallow points — counted, no exception leaks
# ---------------------------------------------------------------------------


class TestRedisChannelSwallowPoints:
    """Redis-side failures must be counted and swallowed, not raised."""

    def setup_method(self) -> None:
        reset_publish_failure_count()

    def teardown_method(self) -> None:
        reset_publish_failure_count()

    @pytest.mark.asyncio
    async def test_publish_failure_returns_zero_and_counts(self) -> None:
        """``RedisChannel.publish`` wraps the Redis call in a
        try/except.  On failure it returns 0 (number of
        deliveries unknown) and increments the counter.
        """
        redis = MagicMock()
        # The async ``publish`` call must raise.  Use AsyncMock
        # so ``await self._redis.publish(...)`` returns a coroutine
        # that raises.
        from unittest.mock import AsyncMock

        redis.publish = AsyncMock(side_effect=ConnectionError("redis down"))
        ch = RedisChannel("ch-pub", redis)
        result = await ch.publish("hello")
        assert result == 0
        assert get_publish_failure_count() == 1

    def test_is_set_failure_returns_false_and_counts(self) -> None:
        """``RedisChannel.is_set`` returns False on Redis error
        (conservative — treat as "not set") and counts.
        """
        redis = MagicMock()
        redis.exists = MagicMock(side_effect=ConnectionError("redis down"))
        ch = RedisChannel("ch-iset", redis)
        result = ch.is_set()
        assert result is False
        assert get_publish_failure_count() == 1

    def test_set_count_failure_returns_zero_and_counts(self) -> None:
        """``RedisChannel.set_count`` returns 0 on Redis error
        (treat as "not set" — conservative) and counts.
        """
        redis = MagicMock()
        redis.exists = MagicMock(side_effect=ConnectionError("redis down"))
        ch = RedisChannel("ch-sc", redis)
        result = ch.set_count
        assert result == 0
        assert get_publish_failure_count() == 1

    def test_clear_failure_swallows_and_counts(self) -> None:
        """``RedisChannel.clear`` swallows the Redis error (no
        return value to fail) and counts.
        """
        redis = MagicMock()
        redis.delete = MagicMock(side_effect=ConnectionError("redis down"))
        ch = RedisChannel("ch-clr", redis)
        # Must not raise
        ch.clear()
        assert get_publish_failure_count() == 1

    def test_successful_redis_calls_do_not_count(self) -> None:
        """Sanity check: the happy path on a normalising Redis
        mock does not bump the counter.
        """
        redis = MagicMock()
        redis.exists = MagicMock(return_value=0)
        redis.delete = MagicMock(return_value=1)
        ch = RedisChannel("ch-ok", redis)
        assert ch.is_set() is False
        assert ch.set_count == 0
        ch.clear()
        assert get_publish_failure_count() == 0

    def test_swallow_points_are_isolated_per_channel(self, caplog: pytest.LogCaptureFixture) -> None:
        """A failure on channel A's ``is_set`` does not log
        at ``error`` when channel B's ``is_set`` fails for
        the first time.
        """
        caplog.set_level(logging.DEBUG, logger="backend.state.pubsub")
        redis = MagicMock()
        redis.exists = MagicMock(side_effect=ConnectionError("down"))
        ch_a = RedisChannel("ch-A-iso", redis)
        ch_b = RedisChannel("ch-B-iso", redis)
        # Two failures on ch_a
        ch_a.is_set()
        ch_a.is_set()
        caplog.clear()
        # First failure on ch_b
        ch_b.is_set()
        error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
        assert len(error_records) == 1
        assert "ch-B-iso" in error_records[0].getMessage()


# ---------------------------------------------------------------------------
# get_pubsub() Redis-init fallback counts its failure
# ---------------------------------------------------------------------------


class TestGetPubsubInitFailureCounts:
    """The Redis-init fallback in :func:`get_pubsub` counts its failure."""

    def setup_method(self) -> None:
        """Reset both the cache and the failure counter."""
        pubsub.reset_pubsub_cache()
        reset_publish_failure_count()

    def teardown_method(self) -> None:
        pubsub.reset_pubsub_cache()
        reset_publish_failure_count()

    def test_redis_init_failure_increments_counter(self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
        """When :func:`get_pubsub` falls back to in-memory because
        Redis is unreachable, the failure is counted via the
        synthetic ``"__init__"`` channel key.
        """
        from backend.core import config as config_mod

        # Point settings.redis_url at something real so the factory
        # tries to connect (and the try/except actually fires).
        fake_settings = config_mod.Settings(redis_url="redis://nope.invalid:65535")
        monkeypatch.setattr(config_mod, "settings", fake_settings)
        # We also need to make ``getattr(settings, "redis_url", ...)`` work
        # in the function's local import — it does ``from backend.core.config
        # import settings`` then ``settings.redis_url``, which uses our
        # monkey-patched settings.

        # Force ``RedisPubSub(settings.redis_url)`` to raise.  Patch
        # the class on the module so the import inside __init__ still
        # works (it does, because it only imports ``redis`` which is
        # not the problem here).
        from backend.state.pubsub import RedisPubSub

        def _boom(_url: str) -> None:
            raise ConnectionError("simulated Redis unreachable")

        monkeypatch.setattr(RedisPubSub, "__init__", _boom)

        caplog.set_level(logging.WARNING, logger="backend.state.pubsub")
        backend = pubsub.get_pubsub()
        # The factory fell back to in-memory
        assert isinstance(backend, InMemoryPubSub)
        # The counter was bumped
        assert get_publish_failure_count() == 1
        # And the existing warning was emitted
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any("Redis pub/sub unavailable" in r.getMessage() for r in warning_records)
