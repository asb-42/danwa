"""Tests for LLM Activity Tracker — unit tests for the singleton tracker."""

from __future__ import annotations

import pytest

from backend.services.llm_activity import LLMActivityTracker


@pytest.fixture()
def tracker() -> LLMActivityTracker:
    """Fresh tracker instance for each test (not the global singleton)."""
    return LLMActivityTracker()


# ---------------------------------------------------------------------------
# start_call / end_call basics
# ---------------------------------------------------------------------------


class TestStartCall:
    @pytest.mark.asyncio
    async def test_start_call_returns_id(self, tracker: LLMActivityTracker):
        call_id = await tracker.start_call(model="gpt-4", provider="openai")
        assert call_id.startswith("llm-")
        assert call_id == "llm-1"

    @pytest.mark.asyncio
    async def test_start_call_increments_counter(self, tracker: LLMActivityTracker):
        id1 = await tracker.start_call(model="gpt-4", provider="openai")
        id2 = await tracker.start_call(model="claude-3", provider="anthropic")
        assert id1 == "llm-1"
        assert id2 == "llm-2"

    @pytest.mark.asyncio
    async def test_start_call_tracks_active(self, tracker: LLMActivityTracker):
        await tracker.start_call(model="gpt-4", provider="openai")
        status = await tracker.get_status()
        assert status["active_count"] == 1
        assert status["active"][0]["model"] == "gpt-4"
        assert status["active"][0]["provider"] == "openai"

    @pytest.mark.asyncio
    async def test_start_call_multiple_active(self, tracker: LLMActivityTracker):
        await tracker.start_call(model="gpt-4", provider="openai")
        await tracker.start_call(model="claude-3", provider="anthropic")
        await tracker.start_call(model="llama-3", provider="local")
        status = await tracker.get_status()
        assert status["active_count"] == 3

    @pytest.mark.asyncio
    async def test_start_call_with_session_id(self, tracker: LLMActivityTracker):
        await tracker.start_call(model="gpt-4", provider="openai", session_id="sess-1")
        status = await tracker.get_status()
        assert "sess-1" in status["session_totals"]


class TestEndCall:
    @pytest.mark.asyncio
    async def test_end_call_removes_from_active(self, tracker: LLMActivityTracker):
        call_id = await tracker.start_call(model="gpt-4", provider="openai")
        await tracker.end_call(call_id, tokens_in=100, tokens_out=50, status="completed")
        status = await tracker.get_status()
        assert status["active_count"] == 0

    @pytest.mark.asyncio
    async def test_end_call_moves_to_recent(self, tracker: LLMActivityTracker):
        call_id = await tracker.start_call(model="gpt-4", provider="openai")
        await tracker.end_call(call_id, tokens_in=100, tokens_out=50, status="completed")
        status = await tracker.get_status()
        assert len(status["recent"]) == 1
        recent = status["recent"][0]
        assert recent["model"] == "gpt-4"
        assert recent["tokens_in"] == 100
        assert recent["tokens_out"] == 50
        assert recent["status"] == "completed"

    @pytest.mark.asyncio
    async def test_end_call_with_failure(self, tracker: LLMActivityTracker):
        call_id = await tracker.start_call(model="gpt-4", provider="openai")
        await tracker.end_call(call_id, status="failed", error="Connection refused")
        status = await tracker.get_status()
        assert len(status["recent"]) == 1
        assert status["recent"][0]["status"] == "failed"
        assert "Connection refused" in status["recent"][0]["error"]

    @pytest.mark.asyncio
    async def test_end_call_records_duration(self, tracker: LLMActivityTracker):
        call_id = await tracker.start_call(model="gpt-4", provider="openai")
        await tracker.end_call(call_id, tokens_in=10, tokens_out=5, status="completed")
        status = await tracker.get_status()
        assert status["recent"][0]["duration_ms"] >= 0

    @pytest.mark.asyncio
    async def test_end_call_unknown_id_is_noop(self, tracker: LLMActivityTracker):
        """Ending a call that doesn't exist should not raise."""
        await tracker.end_call("llm-999", tokens_in=0, tokens_out=0, status="completed")
        status = await tracker.get_status()
        assert status["active_count"] == 0
        assert len(status["recent"]) == 0

    @pytest.mark.asyncio
    async def test_end_call_updates_session_totals(self, tracker: LLMActivityTracker):
        call_id = await tracker.start_call(model="gpt-4", provider="openai", session_id="sess-1")
        await tracker.end_call(call_id, tokens_in=200, tokens_out=100, status="completed", session_id="sess-1")
        status = await tracker.get_status()
        assert status["session_totals"]["sess-1"] == 300  # 200 + 100

    @pytest.mark.asyncio
    async def test_end_call_accumulates_session_totals(self, tracker: LLMActivityTracker):
        cid1 = await tracker.start_call(model="gpt-4", provider="openai", session_id="sess-1")
        await tracker.end_call(cid1, tokens_in=100, tokens_out=50, status="completed", session_id="sess-1")
        cid2 = await tracker.start_call(model="gpt-4", provider="openai", session_id="sess-1")
        await tracker.end_call(cid2, tokens_in=200, tokens_out=100, status="completed", session_id="sess-1")
        status = await tracker.get_status()
        assert status["session_totals"]["sess-1"] == 450  # 150 + 300


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------


class TestGetStatus:
    @pytest.mark.asyncio
    async def test_empty_tracker(self, tracker: LLMActivityTracker):
        status = await tracker.get_status()
        assert status["active_count"] == 0
        assert status["active"] == []
        assert status["recent"] == []
        assert status["total_tokens_all_sessions"] == 0
        assert status["session_totals"] == {}

    @pytest.mark.asyncio
    async def test_total_tokens_all_sessions(self, tracker: LLMActivityTracker):
        cid1 = await tracker.start_call(model="gpt-4", provider="openai", session_id="s1")
        await tracker.end_call(cid1, tokens_in=100, tokens_out=50, status="completed", session_id="s1")
        cid2 = await tracker.start_call(model="claude-3", provider="anthropic", session_id="s2")
        await tracker.end_call(cid2, tokens_in=200, tokens_out=100, status="completed", session_id="s2")
        status = await tracker.get_status()
        assert status["total_tokens_all_sessions"] == 450

    @pytest.mark.asyncio
    async def test_recent_limited_to_max(self, tracker: LLMActivityTracker):
        """Only the last _max_recent calls should be kept."""
        tracker._max_recent = 5
        for i in range(8):
            cid = await tracker.start_call(model=f"model-{i}", provider="test")
            await tracker.end_call(cid, tokens_in=i, tokens_out=0, status="completed")
        status = await tracker.get_status()
        assert len(status["recent"]) == 5
        # Should be the last 5 (models 3-7)
        assert status["recent"][0]["model"] == "model-3"
        assert status["recent"][4]["model"] == "model-7"

    @pytest.mark.asyncio
    async def test_recent_returns_last_10_in_status(self, tracker: LLMActivityTracker):
        """get_status() returns at most 10 recent calls regardless of _max_recent."""
        for i in range(15):
            cid = await tracker.start_call(model=f"model-{i}", provider="test")
            await tracker.end_call(cid, tokens_in=i, tokens_out=0, status="completed")
        status = await tracker.get_status()
        assert len(status["recent"]) == 10

    @pytest.mark.asyncio
    async def test_active_shows_elapsed_time(self, tracker: LLMActivityTracker):
        await tracker.start_call(model="gpt-4", provider="openai")
        status = await tracker.get_status()
        assert len(status["active"]) == 1
        assert "elapsed_s" in status["active"][0]
        assert status["active"][0]["elapsed_s"] >= 0


# ---------------------------------------------------------------------------
# clear_session
# ---------------------------------------------------------------------------


class TestClearSession:
    @pytest.mark.asyncio
    async def test_clear_session_removes_totals(self, tracker: LLMActivityTracker):
        cid = await tracker.start_call(model="gpt-4", provider="openai", session_id="s1")
        await tracker.end_call(cid, tokens_in=100, tokens_out=50, status="completed", session_id="s1")
        await tracker.clear_session("s1")
        status = await tracker.get_status()
        assert "s1" not in status["session_totals"]
        assert status["total_tokens_all_sessions"] == 0

    @pytest.mark.asyncio
    async def test_clear_nonexistent_session_noop(self, tracker: LLMActivityTracker):
        """Clearing a session that doesn't exist should not raise."""
        await tracker.clear_session("nonexistent")
        status = await tracker.get_status()
        assert status["session_totals"] == {}


# ---------------------------------------------------------------------------
# Edge cases / isolation
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_concurrent_calls_isolated(self, tracker: LLMActivityTracker):
        """Multiple active calls don't interfere with each other."""
        await tracker.start_call(model="gpt-4", provider="openai")
        id2 = await tracker.start_call(model="claude-3", provider="anthropic")
        await tracker.start_call(model="llama-3", provider="local")

        # End middle one
        await tracker.end_call(id2, tokens_in=50, tokens_out=25, status="completed")

        status = await tracker.get_status()
        assert status["active_count"] == 2
        active_models = {a["model"] for a in status["active"]}
        assert active_models == {"gpt-4", "llama-3"}
        assert len(status["recent"]) == 1
        assert status["recent"][0]["model"] == "claude-3"

    @pytest.mark.asyncio
    async def test_error_truncated_to_200_chars(self, tracker: LLMActivityTracker):
        long_error = "x" * 500
        cid = await tracker.start_call(model="gpt-4", provider="openai")
        await tracker.end_call(cid, status="failed", error=long_error)
        status = await tracker.get_status()
        assert len(status["recent"][0]["error"]) == 200

    @pytest.mark.asyncio
    async def test_multiple_sessions_independent(self, tracker: LLMActivityTracker):
        cid1 = await tracker.start_call(model="gpt-4", provider="openai", session_id="s1")
        await tracker.end_call(cid1, tokens_in=100, tokens_out=50, status="completed", session_id="s1")
        cid2 = await tracker.start_call(model="gpt-4", provider="openai", session_id="s2")
        await tracker.end_call(cid2, tokens_in=200, tokens_out=100, status="completed", session_id="s2")
        status = await tracker.get_status()
        assert status["session_totals"]["s1"] == 150
        assert status["session_totals"]["s2"] == 300
        assert status["total_tokens_all_sessions"] == 450
