"""Tests for Phase 2 Group G.5 — InterjectionService.

Covers submit/consume roundtrips, get_pending, clear, and multi-session isolation.
"""

from __future__ import annotations

import asyncio

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
    async def test_clear_one_session_preserves_other(
        self, service: InterjectionService
    ) -> None:
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
