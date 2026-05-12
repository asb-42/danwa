"""Tests for Phase 8 Group B — A2AAdapter."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.a2a.adapter import A2AAdapter
from backend.a2a.exceptions import A2AConnectionError


class TestA2AAdapterInit:
    def test_valid_endpoint(self):
        adapter = A2AAdapter("http://agent.example.com")
        assert adapter._endpoint == "http://agent.example.com"

    def test_invalid_scheme(self):
        from backend.a2a.exceptions import A2AValidationError

        with pytest.raises(A2AValidationError):
            A2AAdapter("file:///etc/passwd")

    def test_private_ip_blocked(self):
        from backend.a2a.exceptions import A2AValidationError

        with pytest.raises(A2AValidationError):
            A2AAdapter("http://192.168.1.1")

    def test_private_ip_allowed(self):
        adapter = A2AAdapter("http://192.168.1.1", allow_private_ips=True)
        assert adapter._endpoint == "http://192.168.1.1"


class TestBuildTaskPayload:
    def test_basic_messages(self):
        messages = [
            {"role": "system", "content": "You are a strategist."},
            {"role": "user", "content": "Analyze this case."},
        ]
        result = A2AAdapter._build_task_payload(messages, {})
        assert "You are a strategist" in result
        assert "Analyze this case" in result

    def test_with_context(self):
        messages = [{"role": "user", "content": "Task"}]
        config = {"context": "Case text", "role": "critic", "round_num": 2}
        result = A2AAdapter._build_task_payload(messages, config)
        assert "Case text" in result
        assert "critic" in result
        assert "round 2" in result

    def test_with_previous_outputs(self):
        messages = []
        config = {
            "previous_outputs": [
                {"role": "strategist", "content": "Initial analysis"},
            ]
        }
        result = A2AAdapter._build_task_payload(messages, config)
        assert "strategist" in result
        assert "Initial analysis" in result


class TestExtractResponse:
    def test_from_artifacts(self):
        result = {"artifacts": [{"parts": [{"type": "text", "text": "Response text"}]}]}
        content, tokens = A2AAdapter._extract_response(result)
        assert content == "Response text"
        assert tokens > 0

    def test_from_result_string(self):
        result = {"result": "Direct response"}
        content, tokens = A2AAdapter._extract_response(result)
        assert content == "Direct response"

    def test_empty_result(self):
        result = {}
        content, tokens = A2AAdapter._extract_response(result)
        assert content == ""
        assert tokens == 0


class TestDiscover:
    @pytest.mark.asyncio
    async def test_discover_success(self):
        adapter = A2AAdapter("http://agent.example.com")
        mock_card = {
            "name": "Test Agent",
            "description": "A test agent",
            "version": "1.0",
            "capabilities": {"input_modes": ["text"]},
            "skills": [{"id": "skill1", "name": "Skill 1"}],
        }

        async def mock_discover():
            return mock_card

        with patch("backend.a2a.adapter.A2AClient") as mock_client:
            instance = mock_client.return_value
            instance.discover = mock_discover
            result = await adapter.discover()
        assert result["name"] == "Test Agent"
        assert result["version"] == "1.0"
        assert len(result["skills"]) == 1

    @pytest.mark.asyncio
    async def test_discover_connection_error(self):
        adapter = A2AAdapter("http://agent.example.com")
        with patch.object(adapter._client, "discover", new_callable=AsyncMock, side_effect=ConnectionError("fail")):
            with pytest.raises(A2AConnectionError):
                await adapter.discover()
