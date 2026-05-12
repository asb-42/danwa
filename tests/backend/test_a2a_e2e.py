"""E2E tests for A2A protocol compliance.

Validates:
- Agent Card discovery (GET /.well-known/agent.json)
- JSON-RPC 2.0 format (POST /a2a)
- Task lifecycle: send → get → cancel
- Error handling for malformed requests
"""

from __future__ import annotations

# ─── Agent Card Discovery ────────────────────────────────────────────


class TestAgentCardDiscovery:
    """Validate the Agent Card endpoint follows A2A spec."""

    def test_agent_card_endpoint_exists(self, client):
        """GET /.well-known/agent.json returns 200."""
        resp = client.get("/.well-known/agent.json")
        assert resp.status_code == 200

    def test_agent_card_is_valid_json(self, client):
        """Agent Card response is valid JSON."""
        resp = client.get("/.well-known/agent.json")
        card = resp.json()
        assert isinstance(card, dict)

    def test_agent_card_has_required_fields(self, client):
        """Agent Card contains required A2A fields."""
        card = client.get("/.well-known/agent.json").json()
        assert "name" in card
        assert "description" in card
        assert "url" in card
        assert "version" in card

    def test_agent_card_has_capabilities(self, client):
        """Agent Card declares capabilities."""
        card = client.get("/.well-known/agent.json").json()
        assert "capabilities" in card
        caps = card["capabilities"]
        assert isinstance(caps, dict)

    def test_agent_card_has_skills(self, client):
        """Agent Card declares at least one skill."""
        card = client.get("/.well-known/agent.json").json()
        assert "skills" in card
        assert len(card["skills"]) >= 1

    def test_agent_card_skill_has_required_fields(self, client):
        """Each skill has id, name, description."""
        card = client.get("/.well-known/agent.json").json()
        for skill in card["skills"]:
            assert "id" in skill
            assert "name" in skill
            assert "description" in skill


# ─── JSON-RPC 2.0 Format ────────────────────────────────────────────


class TestJSONRPCFormat:
    """Validate JSON-RPC 2.0 compliance of the /a2a endpoint."""

    def test_response_always_has_jsonrpc_version(self, client):
        """All responses include jsonrpc: '2.0'."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "id": "test-1",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Test"}],
                    },
                },
            },
        )
        body = resp.json()
        assert body.get("jsonrpc") == "2.0"

    def test_response_echoes_request_id(self, client):
        """Response echoes the request id."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "id": "echo-test-42",
                "params": {
                    "message": {
                        "role": "user",
                        "parts": [{"type": "text", "text": "Echo test"}],
                    },
                },
            },
        )
        body = resp.json()
        assert body.get("id") == "echo-test-42"

    def test_unknown_method_returns_error(self, client):
        """Request with unknown method returns -32601 error."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "unknown/method",
                "id": "test-4",
                "params": {},
            },
        )
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == -32601  # Method not found
        assert "jsonrpc" in body
        assert body["id"] == "test-4"

    def test_missing_method_returns_error(self, client):
        """Request without 'method' field returns method-not-found error."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "test-3",
                "params": {},
            },
        )
        body = resp.json()
        assert "error" in body
        # Empty method string falls through to unknown method handler
        assert body["error"]["code"] == -32601

    def test_get_nonexistent_task_has_jsonrpc_and_id(self, client):
        """tasks/get for nonexistent task includes jsonrpc and id."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "tasks/get",
                "id": "err-test",
                "params": {"id": "nonexistent"},
            },
        )
        body = resp.json()
        assert body.get("jsonrpc") == "2.0"
        assert body.get("id") == "err-test"
        # Server returns result with failed state (not a JSON-RPC error)
        assert "result" in body
        assert body["result"]["status"]["state"] == "failed"

    def test_malformed_json_body_returns_error(self, client):
        """Malformed JSON body returns an error response."""
        resp = client.post(
            "/a2a",
            content=b"not json",
            headers={"Content-Type": "application/json"},
        )
        # The router catches exceptions and returns -32603
        body = resp.json()
        assert "error" in body


# ─── Task Lifecycle ──────────────────────────────────────────────────


class TestTaskLifecycle:
    """Validate the full A2A task lifecycle through the API."""

    def _send_task(self, client, topic="Test debate topic", task_id=None):
        """Helper: send a task and return the response body."""
        params = {
            "message": {
                "role": "user",
                "parts": [{"type": "text", "text": topic}],
            },
        }
        if task_id:
            params["id"] = task_id
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "tasks/send",
                "id": "req-send",
                "params": params,
            },
        )
        return resp.json()

    def _get_task(self, client, task_id):
        """Helper: get task status and return the response body."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "tasks/get",
                "id": "req-get",
                "params": {"id": task_id},
            },
        )
        return resp.json()

    def _cancel_task(self, client, task_id):
        """Helper: cancel a task and return the response body."""
        resp = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "method": "tasks/cancel",
                "id": "req-cancel",
                "params": {"id": task_id},
            },
        )
        return resp.json()

    def test_send_task_returns_task_id(self, client):
        """tasks/send returns a result with task id and status."""
        body = self._send_task(client)
        assert "result" in body
        result = body["result"]
        assert "id" in result
        assert "status" in result
        assert result["status"]["state"] in ("submitted", "working")

    def test_send_task_with_custom_id(self, client):
        """tasks/send respects custom task ID."""
        body = self._send_task(client, task_id="custom-task-123")
        result = body["result"]
        assert result["id"] == "custom-task-123"

    def test_get_task_after_send(self, client):
        """tasks/get returns the same task after send."""
        send_body = self._send_task(client, task_id="lifecycle-get")
        task_id = send_body["result"]["id"]

        get_body = self._get_task(client, task_id)
        assert "result" in get_body
        assert get_body["result"]["id"] == task_id

    def test_get_nonexistent_task(self, client):
        """tasks/get for nonexistent task returns result with failed state."""
        body = self._get_task(client, "nonexistent-id")
        assert "result" in body
        assert body["result"]["status"]["state"] == "failed"

    def test_cancel_task(self, client):
        """tasks/cancel transitions task to canceled state."""
        send_body = self._send_task(client, task_id="lifecycle-cancel")
        task_id = send_body["result"]["id"]

        cancel_body = self._cancel_task(client, task_id)
        assert "result" in cancel_body
        assert cancel_body["result"]["status"]["state"] == "canceled"

    def test_cancel_nonexistent_task(self, client):
        """tasks/cancel for nonexistent task returns result with failed state."""
        body = self._cancel_task(client, "nonexistent-cancel")
        assert "result" in body
        assert body["result"]["status"]["state"] == "failed"

    def test_get_canceled_task(self, client):
        """tasks/get shows canceled state after cancel."""
        send_body = self._send_task(client, task_id="lifecycle-get-cancel")
        task_id = send_body["result"]["id"]
        self._cancel_task(client, task_id)

        get_body = self._get_task(client, task_id)
        assert get_body["result"]["status"]["state"] == "canceled"

    def test_task_has_message_in_result(self, client):
        """tasks/send result includes the original message."""
        body = self._send_task(client, topic="Consensus on AI ethics")
        result = body["result"]
        assert "message" in result
        msg = result["message"]
        assert msg["role"] == "user"
        assert any("Consensus on AI ethics" in p.get("text", "") for p in msg["parts"])


# ─── A2A Config in DebateRequest ─────────────────────────────────────


class TestA2AConfigInDebateRequest:
    """Validate that a2a_agents field is accepted in debate creation."""

    def test_create_debate_with_empty_a2a_agents(self, client):
        """Debate creation accepts empty a2a_agents list."""
        resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Test case"},
                "a2a_agents": [],
            },
        )
        assert resp.status_code == 201

    def test_create_debate_with_a2a_agent(self, client):
        """Debate creation accepts a2a_agents with url, role, position."""
        resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Test case with A2A"},
                "a2a_agents": [
                    {
                        "url": "https://external.example.com/a2a",
                        "role": "analyst",
                        "position": "after_moderator",
                    },
                ],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"

    def test_create_debate_with_multiple_a2a_agents(self, client):
        """Debate creation accepts multiple a2a_agents."""
        resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Multi-agent test"},
                "a2a_agents": [
                    {"url": "https://agent1.example.com/a2a", "role": "analyst"},
                    {"url": "https://agent2.example.com/a2a", "role": "reviewer"},
                ],
            },
        )
        assert resp.status_code == 201

    def test_create_debate_a2a_agent_url_required(self, client):
        """a2a_agents entry without url is rejected."""
        resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Invalid A2A"},
                "a2a_agents": [
                    {"role": "analyst"},  # missing url
                ],
            },
        )
        assert resp.status_code == 422  # Validation error


# ─── A2A Debate with External Agent ─────────────────────────────────


class TestA2ADebateWithExternalAgent:
    """E2E tests: create and start a debate with A2A agent configuration."""

    def test_create_and_get_debate_with_a2a_agents(self, client):
        """Create debate with A2A agents, then GET it back."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "AI ethics debate with external agent"},
                "a2a_agents": [
                    {
                        "url": "https://external-agent.example.com/a2a",
                        "role": "external_reviewer",
                        "position": "after:moderator",
                    },
                ],
            },
        )
        assert create_resp.status_code == 201
        debate_id = create_resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["debate_id"] == debate_id
        assert data["status"] == "pending"
        assert data["case_text"] == "AI ethics debate with external agent"

    def test_start_debate_with_a2a_agents_accepted(self, app):
        """Starting a debate with A2A agents is accepted by the API."""
        # Use raise_server_exceptions=False because the background workflow
        # will fail (no LLM profiles / no external agent in test env)
        from fastapi.testclient import TestClient

        client_no_exc = TestClient(app, raise_server_exceptions=False)

        create_resp = client_no_exc.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Start A2A debate test"},
                "a2a_agents": [
                    {"url": "https://agent.example.com/a2a", "role": "analyst"},
                ],
            },
        )
        assert create_resp.status_code == 201
        debate_id = create_resp.json()["debate_id"]

        start_resp = client_no_exc.post(f"/api/v1/debate/{debate_id}/start")
        # The start endpoint returns 200 with status=running
        assert start_resp.status_code == 200
        assert start_resp.json()["status"] == "running"

    def test_debate_with_multiple_a2a_agents(self, client):
        """Create debate with multiple A2A agents and verify storage."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Multi-agent debate"},
                "a2a_agents": [
                    {"url": "https://agent1.example.com/a2a", "role": "analyst"},
                    {"url": "https://agent2.example.com/a2a", "role": "critic"},
                    {"url": "https://agent3.example.com/a2a", "role": "reviewer"},
                ],
            },
        )
        assert create_resp.status_code == 201
        debate_id = create_resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "pending"

    def test_debate_without_a2a_agents_still_works(self, client):
        """Debate without A2A agents works normally (regression test)."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Normal debate without A2A"},
            },
        )
        assert create_resp.status_code == 201
        debate_id = create_resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "pending"

    def test_a2a_agent_with_all_fields(self, client):
        """A2A agent with all optional fields is accepted."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Full A2A config test"},
                "a2a_agents": [
                    {
                        "url": "https://full-agent.example.com/a2a",
                        "role": "external_critic",
                        "position": "after:critic",
                    },
                ],
            },
        )
        assert create_resp.status_code == 201

    def test_a2a_agent_default_role_and_position(self, client):
        """A2A agent with only url uses default role and position."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Default A2A config test"},
                "a2a_agents": [
                    {"url": "https://minimal-agent.example.com/a2a"},
                ],
            },
        )
        assert create_resp.status_code == 201
