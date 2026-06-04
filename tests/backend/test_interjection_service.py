"""Tests for Phase 2 Group G.5 — InterjectionService.

Covers submit/consume roundtrips, get_pending, clear, and multi-session isolation.
"""

from __future__ import annotations

import pytest

from backend.workflow.interjection import Interjection, InterjectionService


@pytest.fixture()
def service() -> InterjectionService:
    """Fresh InterjectionService for each test."""
    return InterjectionService()


# ---------------------------------------------------------------------------
# submit / consume roundtrip
# ---------------------------------------------------------------------------


class TestSubmitConsume:
    """Test submit() and consume() roundtrip."""

    @pytest.mark.asyncio
    async def test_submit_returns_id(self, service: InterjectionService) -> None:
        """submit() should return an interjection_id string."""
        iid = await service.submit("sess-1", "Hello", source="user")
        assert isinstance(iid, str)
        assert iid.startswith("inj-")

    @pytest.mark.asyncio
    async def test_consume_returns_submitted(self, service: InterjectionService) -> None:
        """consume() should return all pending interjections for the session."""
        await service.submit("sess-1", "First", source="user")
        await service.submit("sess-1", "Second", source="api")

        results = await service.consume("sess-1")
        assert len(results) == 2
        contents = {r["content"] for r in results}
        assert contents == {"First", "Second"}
        assert all(r["source"] in ("user", "api") for r in results)

    @pytest.mark.asyncio
    async def test_consume_marks_as_consumed(self, service: InterjectionService) -> None:
        """After consume(), items should no longer be pending."""
        await service.submit("sess-1", "Test")
        await service.consume("sess-1")

        # Second consume should return empty
        results = await service.consume("sess-1")
        assert results == []

    @pytest.mark.asyncio
    async def test_consume_empty_session(self, service: InterjectionService) -> None:
        """consume() on a session with no interjections returns empty list."""
        results = await service.consume("nonexistent-session")
        assert results == []

    @pytest.mark.asyncio
    async def test_submit_with_metadata(self, service: InterjectionService) -> None:
        """Metadata should be preserved through submit/consume."""
        await service.submit("sess-1", "Data", metadata={"key": "value"})
        results = await service.consume("sess-1")
        assert len(results) == 1
        assert results[0]["metadata"] == {"key": "value"}

    @pytest.mark.asyncio
    async def test_submit_default_source(self, service: InterjectionService) -> None:
        """Default source should be 'user'."""
        await service.submit("sess-1", "Test")
        results = await service.consume("sess-1")
        assert results[0]["source"] == "user"


# ---------------------------------------------------------------------------
# get_pending
# ---------------------------------------------------------------------------


class TestGetPending:
    """Test get_pending() returns queued items without consuming."""

    @pytest.mark.asyncio
    async def test_get_pending_returns_items(self, service: InterjectionService) -> None:
        """get_pending() should list pending items."""
        await service.submit("sess-1", "A")
        await service.submit("sess-1", "B")

        pending = await service.get_pending("sess-1")
        assert len(pending) == 2

    @pytest.mark.asyncio
    async def test_get_pending_does_not_consume(self, service: InterjectionService) -> None:
        """get_pending() should not consume items."""
        await service.submit("sess-1", "A")
        await service.get_pending("sess-1")

        # Items should still be pending
        pending = await service.get_pending("sess-1")
        assert len(pending) == 1

    @pytest.mark.asyncio
    async def test_get_pending_empty_session(self, service: InterjectionService) -> None:
        """get_pending() on empty session returns empty list."""
        pending = await service.get_pending("nonexistent")
        assert pending == []

    @pytest.mark.asyncio
    async def test_get_pending_excludes_consumed(self, service: InterjectionService) -> None:
        """get_pending() should not include already-consumed items."""
        await service.submit("sess-1", "A")
        await service.submit("sess-1", "B")
        await service.consume("sess-1")

        await service.submit("sess-1", "C")
        pending = await service.get_pending("sess-1")
        assert len(pending) == 1
        assert pending[0]["content"] == "C"


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    """Test clear() removes all items for a session."""

    @pytest.mark.asyncio
    async def test_clear_removes_all(self, service: InterjectionService) -> None:
        """clear() should remove all interjections for a session."""
        await service.submit("sess-1", "A")
        await service.submit("sess-1", "B")
        await service.clear("sess-1")

        pending = await service.get_pending("sess-1")
        assert pending == []

    @pytest.mark.asyncio
    async def test_clear_nonexistent_session(self, service: InterjectionService) -> None:
        """clear() on a nonexistent session should not raise."""
        await service.clear("nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_clear_then_submit(self, service: InterjectionService) -> None:
        """After clear(), new submissions should work normally."""
        await service.submit("sess-1", "Old")
        await service.clear("sess-1")
        await service.submit("sess-1", "New")

        results = await service.consume("sess-1")
        assert len(results) == 1
        assert results[0]["content"] == "New"


# ---------------------------------------------------------------------------
# Multi-session isolation
# ---------------------------------------------------------------------------


class TestMultiSession:
    """Test that sessions are properly isolated."""

    @pytest.mark.asyncio
    async def test_sessions_are_isolated(self, service: InterjectionService) -> None:
        """Interjections in one session should not appear in another."""
        await service.submit("sess-1", "For session 1")
        await service.submit("sess-2", "For session 2")

        results_1 = await service.consume("sess-1")
        results_2 = await service.consume("sess-2")

        assert len(results_1) == 1
        assert results_1[0]["content"] == "For session 1"
        assert len(results_2) == 1
        assert results_2[0]["content"] == "For session 2"

    @pytest.mark.asyncio
    async def test_clear_one_session_preserves_other(self, service: InterjectionService) -> None:
        """Clearing one session should not affect another."""
        await service.submit("sess-1", "A")
        await service.submit("sess-2", "B")
        await service.clear("sess-1")

        pending_1 = await service.get_pending("sess-1")
        pending_2 = await service.get_pending("sess-2")

        assert pending_1 == []
        assert len(pending_2) == 1


# ---------------------------------------------------------------------------
# Interjection dataclass
# ---------------------------------------------------------------------------


class TestInterjectionDataclass:
    """Test the Interjection dataclass."""

    def test_default_values(self) -> None:
        """Interjection should have sensible defaults."""
        ij = Interjection(
            interjection_id="inj-1",
            session_id="sess-1",
            content="test",
            source="user",
        )
        assert ij.metadata == {}
        assert ij.status == "pending"

    def test_custom_values(self) -> None:
        """Interjection should accept custom values."""
        ij = Interjection(
            interjection_id="inj-2",
            session_id="sess-1",
            content="test",
            source="api",
            metadata={"key": "val"},
            status="consumed",
        )
        assert ij.metadata == {"key": "val"}
        assert ij.status == "consumed"


# ---------------------------------------------------------------------------
# consume_blocking — wake-up semantics for the interjection node
# ---------------------------------------------------------------------------


class TestConsumeBlocking:
    """Test consume_blocking() — the H6 fix that lets a workflow actually
    wait for human input instead of racing the resume handler.
    """

    @pytest.mark.asyncio
    async def test_returns_immediately_when_items_present(self, service: InterjectionService) -> None:
        """If items are already queued, consume_blocking() must return
        synchronously (no async wait) and drain them.
        """
        await service.submit("sess-1", "Hello", source="user")

        results = await service.consume_blocking("sess-1", timeout=10.0)

        assert len(results) == 1
        assert results[0]["content"] == "Hello"
        # Queue is now empty.
        pending = await service.get_pending("sess-1")
        assert pending == []

    @pytest.mark.asyncio
    async def test_waits_and_wakes_on_submit(self, service: InterjectionService) -> None:
        """If the queue is empty, consume_blocking() must block until a
        concurrent submit() arrives, then return that item.
        """
        import asyncio

        async def submitter() -> None:
            await asyncio.sleep(0.05)
            await service.submit("sess-1", "Late arrival", source="api")

        task = asyncio.create_task(submitter())
        results = await service.consume_blocking("sess-1", timeout=5.0)
        await task

        assert len(results) == 1
        assert results[0]["content"] == "Late arrival"
        assert results[0]["source"] == "api"

    @pytest.mark.asyncio
    async def test_returns_empty_on_timeout(self, service: InterjectionService) -> None:
        """If no submit() arrives within the timeout, consume_blocking()
        must return an empty list (so the node can fall back to
        ``is_paused=True``).
        """
        results = await service.consume_blocking("sess-1", timeout=0.1)

        assert results == []

    @pytest.mark.asyncio
    async def test_timeout_zero_skips_wait(self, service: InterjectionService) -> None:
        """``timeout=0`` is a useful escape hatch in tests — must return
        immediately without waiting for any wake event.
        """
        results = await service.consume_blocking("sess-1", timeout=0.0)
        assert results == []

    @pytest.mark.asyncio
    async def test_second_blocking_after_drain(self, service: InterjectionService) -> None:
        """After a successful consume_blocking(), a follow-up call must
        block again (i.e. the wake event is correctly cleared).
        """
        import asyncio

        await service.submit("sess-1", "First")
        first = await service.consume_blocking("sess-1", timeout=0.1)
        assert len(first) == 1

        async def submitter() -> None:
            await asyncio.sleep(0.05)
            await service.submit("sess-1", "Second")

        task = asyncio.create_task(submitter())
        second = await service.consume_blocking("sess-1", timeout=5.0)
        await task

        assert len(second) == 1
        assert second[0]["content"] == "Second"

    @pytest.mark.asyncio
    async def test_blocks_with_multiple_consumers(self, service: InterjectionService) -> None:
        """Two concurrent consumers must not deadlock: one wakes on the
        first submit(), the other wakes on the next.
        """
        import asyncio

        async def submitter() -> None:
            await asyncio.sleep(0.05)
            await service.submit("sess-1", "first")
            await asyncio.sleep(0.05)
            await service.submit("sess-1", "second")

        task = asyncio.create_task(submitter())
        first = await service.consume_blocking("sess-1", timeout=5.0)
        second = await service.consume_blocking("sess-1", timeout=5.0)
        await task

        contents = {first[0]["content"], second[0]["content"]}
        assert contents == {"first", "second"}

    @pytest.mark.asyncio
    async def test_clear_resets_wake_event(self, service: InterjectionService) -> None:
        """After clear(), consume_blocking() must block again rather
        than returning whatever was previously in the queue.
        """
        import asyncio

        await service.submit("sess-1", "Doomed")
        await service.clear("sess-1")

        async def submitter() -> None:
            await asyncio.sleep(0.05)
            await service.submit("sess-1", "Survivor")

        task = asyncio.create_task(submitter())
        results = await service.consume_blocking("sess-1", timeout=5.0)
        await task

        assert len(results) == 1
        assert results[0]["content"] == "Survivor"
