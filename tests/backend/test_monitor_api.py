"""Tests for the Monitor API — /api/v1/monitor/activity endpoint."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.services.llm_activity import LLMActivityTracker


@pytest.fixture()
def fresh_tracker() -> LLMActivityTracker:
    """Fresh tracker for API tests."""
    return LLMActivityTracker()


class TestMonitorActivityEndpoint:
    """Tests for GET /api/v1/monitor/activity."""

    def test_activity_empty(self, client, fresh_tracker):
        """Fresh tracker returns zero activity."""
        with patch("backend.api.routers.monitor.llm_activity", fresh_tracker):
            response = client.get("/api/v1/monitor/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["active_count"] == 0
        assert data["active"] == []
        assert data["recent"] == []
        assert data["total_tokens_all_sessions"] == 0
        assert data["session_totals"] == {}

    def test_activity_reflects_active_calls(self, client, fresh_tracker):
        """Endpoint returns active calls that haven't ended yet."""
        import asyncio

        # Simulate active call
        asyncio.run(fresh_tracker.start_call(model="gpt-4", provider="openai"))

        with patch("backend.api.routers.monitor.llm_activity", fresh_tracker):
            response = client.get("/api/v1/monitor/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["active_count"] == 1
        assert data["active"][0]["model"] == "gpt-4"
        assert data["active"][0]["provider"] == "openai"
        assert "elapsed_s" in data["active"][0]

    def test_activity_reflects_completed_calls(self, client, fresh_tracker):
        """Endpoint returns recently completed calls."""
        import asyncio

        async def _setup():
            cid = await fresh_tracker.start_call(model="claude-3", provider="anthropic")
            await fresh_tracker.end_call(cid, tokens_in=150, tokens_out=75, status="completed", session_id="s1")

        asyncio.run(_setup())

        with patch("backend.api.routers.monitor.llm_activity", fresh_tracker):
            response = client.get("/api/v1/monitor/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["recent"]) == 1
        assert data["recent"][0]["model"] == "claude-3"
        assert data["recent"][0]["tokens_in"] == 150
        assert data["recent"][0]["tokens_out"] == 75
        assert data["recent"][0]["status"] == "completed"
        assert data["total_tokens_all_sessions"] == 225
        assert data["session_totals"]["s1"] == 225

    def test_activity_reflects_failed_calls(self, client, fresh_tracker):
        """Endpoint returns failed calls with error info."""
        import asyncio

        async def _setup():
            cid = await fresh_tracker.start_call(model="gpt-4", provider="openai")
            await fresh_tracker.end_call(cid, status="failed", error="Connection refused")

        asyncio.run(_setup())

        with patch("backend.api.routers.monitor.llm_activity", fresh_tracker):
            response = client.get("/api/v1/monitor/activity")
        assert response.status_code == 200
        data = response.json()
        assert len(data["recent"]) == 1
        assert data["recent"][0]["status"] == "failed"
        assert "Connection refused" in data["recent"][0]["error"]

    def test_activity_mixed_active_and_completed(self, client, fresh_tracker):
        """Endpoint reports both active and completed calls."""
        import asyncio

        async def _setup():
            # Completed call
            cid1 = await fresh_tracker.start_call(model="gpt-4", provider="openai")
            await fresh_tracker.end_call(cid1, tokens_in=100, tokens_out=50, status="completed")
            # Still active call
            await fresh_tracker.start_call(model="claude-3", provider="anthropic")

        asyncio.run(_setup())

        with patch("backend.api.routers.monitor.llm_activity", fresh_tracker):
            response = client.get("/api/v1/monitor/activity")
        assert response.status_code == 200
        data = response.json()
        assert data["active_count"] == 1
        assert data["active"][0]["model"] == "claude-3"
        assert len(data["recent"]) == 1
        assert data["recent"][0]["model"] == "gpt-4"

    def test_activity_endpoint_is_get_only(self, client):
        """POST /api/v1/monitor/activity should return 405."""
        response = client.post("/api/v1/monitor/activity")
        assert response.status_code == 405

    def test_activity_response_shape(self, client):
        """Response has the expected top-level keys."""
        response = client.get("/api/v1/monitor/activity")
        assert response.status_code == 200
        data = response.json()
        expected_keys = {"active_count", "active", "recent", "total_tokens_all_sessions", "session_totals"}
        assert set(data.keys()) == expected_keys
