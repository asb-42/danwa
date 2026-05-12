"""Tests for A2A Client — discover, send_task, invoke_agent."""

from __future__ import annotations

import httpx
import pytest

from backend.a2a.client import A2AClient

# ------------------------------------------------------------------
# _extract_text_from_result
# ------------------------------------------------------------------


class TestExtractTextFromResult:
    def test_extracts_text_from_artifacts(self):
        result = {"artifacts": [{"parts": [{"type": "text", "text": "Hello from agent"}]}]}
        assert A2AClient._extract_text_from_result(result) == "Hello from agent"

    def test_returns_none_when_no_artifacts(self):
        assert A2AClient._extract_text_from_result({}) is None
        assert A2AClient._extract_text_from_result({"artifacts": []}) is None

    def test_returns_none_when_no_text_part(self):
        result = {"artifacts": [{"parts": [{"type": "image", "text": ""}]}]}
        assert A2AClient._extract_text_from_result(result) is None

    def test_returns_first_text_part(self):
        result = {
            "artifacts": [
                {
                    "parts": [
                        {"type": "text", "text": "First"},
                        {"type": "text", "text": "Second"},
                    ]
                }
            ]
        }
        assert A2AClient._extract_text_from_result(result) == "First"

    def test_skips_empty_text(self):
        result = {
            "artifacts": [
                {
                    "parts": [
                        {"type": "text", "text": ""},
                        {"type": "text", "text": "Real content"},
                    ]
                }
            ]
        }
        assert A2AClient._extract_text_from_result(result) == "Real content"


# ------------------------------------------------------------------
# invoke_agent prompt building
# ------------------------------------------------------------------


class TestInvokeAgentPrompt:
    """Test that invoke_agent builds the correct prompt structure.

    We mock the HTTP layer to verify the message sent to the external agent.
    """

    @pytest.mark.asyncio
    async def test_invoke_builds_structured_prompt(self, httpx_mock):
        """Verify the prompt includes context, role, round, and previous outputs.

        Note: invoke_agent does NOT call discover() — it goes straight to send_task().
        """
        httpx_mock.add_response(
            url="http://external-agent:8080",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-1",
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"type": "text", "text": "Agent response here"}]}],
                },
            },
        )

        client = A2AClient("http://external-agent:8080")
        response = await client.invoke_agent(
            context="Should we use microservices?",
            role="critic",
            round_num=2,
            previous_outputs=[
                {"role": "moderator", "content": "Let's discuss architecture."},
                {"role": "optimizer", "content": "Consider monolith first."},
            ],
        )

        assert response == "Agent response here"

        # Verify the request body contains the structured prompt
        request = httpx_mock.get_requests()[0]
        import json

        body = json.loads(request.content)
        message_text = body["params"]["message"]["parts"][0]["text"]

        assert "critic" in message_text
        assert "round 2" in message_text
        assert "microservices" in message_text
        assert "Moderator" in message_text
        assert "Optimizer" in message_text

    @pytest.mark.asyncio
    async def test_invoke_handles_async_polling(self, httpx_mock):
        """When task is submitted/working, client should poll for result.

        Note: invoke_agent does NOT call discover().
        """
        # tasks/send returns submitted
        httpx_mock.add_response(
            url="http://external-agent:8080",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-async",
                    "status": {"state": "submitted"},
                },
            },
        )
        # tasks/get returns completed
        httpx_mock.add_response(
            url="http://external-agent:8080",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-async",
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"type": "text", "text": "Polled result"}]}],
                },
            },
        )

        client = A2AClient("http://external-agent:8080")

        # Patch _poll_for_result to use fewer attempts
        original_poll = client._poll_for_result

        async def fast_poll(task_id, max_attempts=1):
            return await original_poll(task_id, max_attempts=1)

        client._poll_for_result = fast_poll

        response = await client.invoke_agent(
            context="Test topic",
            role="analyst",
            round_num=1,
            previous_outputs=[],
        )

        assert response == "Polled result"

    @pytest.mark.asyncio
    async def test_invoke_returns_fallback_on_empty_response(self, httpx_mock):
        """When no response is received, return a fallback message.

        Note: invoke_agent does NOT call discover().
        """
        httpx_mock.add_response(
            url="http://external-agent:8080",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-empty",
                    "status": {"state": "unknown_state"},
                },
            },
        )

        client = A2AClient("http://external-agent:8080")
        response = await client.invoke_agent(
            context="Test",
            role="reviewer",
            round_num=1,
            previous_outputs=[],
        )

        assert "No response" in response


# ------------------------------------------------------------------
# discover
# ------------------------------------------------------------------


class TestDiscover:
    @pytest.mark.asyncio
    async def test_discover_fetches_agent_card(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com/.well-known/agent.json",
            json={
                "name": "Example Agent",
                "description": "An example A2A agent",
                "url": "http://agent.example.com/a2a",
                "skills": [{"name": "analyze", "description": "Analysis skill"}],
            },
        )

        client = A2AClient("http://agent.example.com")
        card = await client.discover()

        assert card["name"] == "Example Agent"
        assert card["description"] == "An example A2A agent"
        assert client._agent_card == card

    @pytest.mark.asyncio
    async def test_discover_raises_on_http_error(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com/.well-known/agent.json",
            status_code=404,
        )

        client = A2AClient("http://agent.example.com")
        with pytest.raises(httpx.HTTPStatusError):
            await client.discover()


# ------------------------------------------------------------------
# send_task / get_task
# ------------------------------------------------------------------


class TestSendGetTask:
    @pytest.mark.asyncio
    async def test_send_task_returns_result(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-123",
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"type": "text", "text": "Done"}]}],
                },
            },
        )

        client = A2AClient("http://agent.example.com")
        result = await client.send_task("Hello agent", task_id="task-123")

        assert result["id"] == "task-123"
        assert result["status"]["state"] == "completed"

    @pytest.mark.asyncio
    async def test_send_task_sends_jsonrpc_payload(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"id": "t1", "status": {"state": "submitted"}},
            },
        )

        client = A2AClient("http://agent.example.com")
        await client.send_task("Test message", task_id="t1")

        import json

        request = httpx_mock.get_requests()[0]
        body = json.loads(request.content)

        assert body["jsonrpc"] == "2.0"
        assert body["method"] == "tasks/send"
        assert body["params"]["id"] == "t1"
        assert body["params"]["message"]["parts"][0]["text"] == "Test message"

    @pytest.mark.asyncio
    async def test_get_task_polls_status(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-456",
                    "status": {"state": "working"},
                },
            },
        )

        client = A2AClient("http://agent.example.com")
        result = await client.get_task("task-456")

        assert result["id"] == "task-456"
        assert result["status"]["state"] == "working"


# ------------------------------------------------------------------
# _poll_for_result
# ------------------------------------------------------------------


class TestPollForResult:
    @pytest.mark.asyncio
    async def test_poll_returns_completed_text(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-poll",
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"type": "text", "text": "Poll result"}]}],
                },
            },
        )

        client = A2AClient("http://agent.example.com")
        result = await client._poll_for_result("task-poll", max_attempts=1)
        assert result == "Poll result"

    @pytest.mark.asyncio
    async def test_poll_returns_error_on_failed(self, httpx_mock):
        httpx_mock.add_response(
            url="http://agent.example.com",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "task-fail",
                    "status": {"state": "failed", "message": "LLM error"},
                },
            },
        )

        client = A2AClient("http://agent.example.com")
        result = await client._poll_for_result("task-fail", max_attempts=1)
        assert "failed" in result
        assert "LLM error" in result

    @pytest.mark.asyncio
    async def test_poll_returns_timeout_message(self, httpx_mock):
        """When max_attempts exhausted, return timeout message."""
        # Return "working" status exactly max_attempts times
        for _ in range(3):
            httpx_mock.add_response(
                url="http://agent.example.com",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": {
                        "id": "task-slow",
                        "status": {"state": "working"},
                    },
                },
            )

        client = A2AClient("http://agent.example.com")
        result = await client._poll_for_result("task-slow", max_attempts=3)
        assert "Timeout" in result
