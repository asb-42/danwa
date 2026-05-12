"""Integration tests for A2A workflow — debate with A2A participant."""

from __future__ import annotations

import pytest

from backend.a2a.node import run_a2a_agent_node
from backend.models.schemas import A2AAgentConfig as SchemaA2AAgentConfig
from backend.workflow.debate_graph import (
    build_graph_with_a2a,
    should_continue_agents_or_a2a,
)

# ------------------------------------------------------------------
# A2AAgentConfig schema
# ------------------------------------------------------------------


class TestA2AAgentConfigSchema:
    def test_default_values(self):
        cfg = SchemaA2AAgentConfig(url="http://agent:8080")
        assert cfg.url == "http://agent:8080"
        assert cfg.role == "a2a_agent"
        assert cfg.position == "after_all"

    def test_custom_values(self):
        cfg = SchemaA2AAgentConfig(
            url="http://critic-agent:9000",
            role="external_critic",
            position="after:critic",
        )
        assert cfg.role == "external_critic"
        assert cfg.position == "after:critic"

    def test_in_debate_request(self):
        from backend.models.schemas import CaseInput, DebateRequest

        req = DebateRequest(
            case=CaseInput(text="Test topic"),
            a2a_agents=[
                SchemaA2AAgentConfig(url="http://agent:8080", role="ext"),
            ],
        )
        assert len(req.a2a_agents) == 1
        assert req.a2a_agents[0].url == "http://agent:8080"


# ------------------------------------------------------------------
# build_graph_with_a2a
# ------------------------------------------------------------------


class TestBuildGraphWithA2a:
    def test_graph_builds_without_error(self):
        graph = build_graph_with_a2a()
        assert graph is not None

    def test_graph_has_a2a_node(self):
        graph = build_graph_with_a2a()
        # The compiled graph should have the run_a2a_agent node
        # Check by inspecting the graph's node names
        node_names = set(graph.get_graph().nodes.keys())
        assert "run_a2a_agent" in node_names


# ------------------------------------------------------------------
# should_continue_agents_or_a2a
# ------------------------------------------------------------------


class TestShouldContinueAgentsOrA2a:
    def test_returns_a2a_when_agents_exhausted_and_a2a_configured(self):
        state = {
            "agent_profile": [
                {"role": "moderator"},
                {"role": "critic"},
            ],
            "current_agent_index": 2,  # All agents done
            "a2a_config": {"enabled": True, "agent_url": "http://agent:8080"},
        }
        assert should_continue_agents_or_a2a(state) == "run_a2a"

    def test_returns_agent_when_agents_remaining(self):
        state = {
            "agent_profile": [
                {"role": "moderator"},
                {"role": "critic"},
            ],
            "current_agent_index": 1,  # Still have critic
            "a2a_config": {"enabled": True, "agent_url": "http://agent:8080"},
        }
        assert should_continue_agents_or_a2a(state) == "next_agent"

    def test_returns_check_consensus_when_no_more_agents_no_a2a(self):
        state = {
            "agent_profile": [
                {"role": "moderator"},
                {"role": "critic"},
            ],
            "current_agent_index": 2,
            "a2a_config": {},
        }
        assert should_continue_agents_or_a2a(state) == "check_consensus"

    def test_returns_run_a2a_when_index_exceeds_profile_but_a2a_configured(self):
        """When current_agent_index == len(profile), A2A should still run (first time)."""
        state = {
            "agent_profile": [{"role": "moderator"}],
            "current_agent_index": 1,  # == len(profile), A2A hasn't run yet
            "a2a_config": {"enabled": True, "agent_url": "http://agent:8080"},
        }
        assert should_continue_agents_or_a2a(state) == "run_a2a"

    def test_returns_check_consensus_when_a2a_has_no_agent_url(self):
        """When A2A is enabled but has no agent_url, skip to consensus."""
        state = {
            "agent_profile": [{"role": "moderator"}],
            "current_agent_index": 1,
            "a2a_config": {"enabled": True},
        }
        assert should_continue_agents_or_a2a(state) == "check_consensus"


# ------------------------------------------------------------------
# run_a2a_agent_node
# ------------------------------------------------------------------


class TestRunA2aAgentNode:
    @pytest.mark.asyncio
    async def test_skips_when_no_config(self):
        """When no a2a_config in state and global config is disabled, skip."""
        state = {
            "a2a_config": {},
            "current_agent_index": 1,
            "session_id": "test-session",
            "current_round": 1,
            "agent_profile": [{"role": "moderator"}],
            "context": "Test",
            "current_draft": "",
            "agent_outputs": [],
        }
        result = await run_a2a_agent_node(state)
        assert result["current_agent_index"] == 2

    @pytest.mark.asyncio
    async def test_skips_when_no_agent_url(self):
        """When a2a_config has no agent_url and no external_agents, skip."""
        state = {
            "a2a_config": {"enabled": True},
            "current_agent_index": 1,
            "session_id": "test-session",
            "current_round": 1,
            "agent_profile": [{"role": "moderator"}],
            "context": "Test",
            "current_draft": "",
            "agent_outputs": [],
        }
        result = await run_a2a_agent_node(state)
        assert result["current_agent_index"] == 2

    @pytest.mark.asyncio
    async def test_uses_external_agents_from_config(self, httpx_mock):
        """When agent_url is empty but external_agents has entries, use the first one."""
        httpx_mock.add_response(
            url="http://ext-agent:8080",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "id": "t1",
                    "status": {"state": "completed"},
                    "artifacts": [{"parts": [{"type": "text", "text": "External analysis"}]}],
                },
            },
        )

        state = {
            "a2a_config": {
                "enabled": True,
                "external_agents": [{"url": "http://ext-agent:8080", "role": "analyst"}],
            },
            "current_agent_index": 1,
            "session_id": "test-session",
            "current_round": 1,
            "agent_profile": [{"role": "moderator"}],
            "context": "Should we use microservices?",
            "current_draft": "",
            "agent_outputs": [],
        }

        result = await run_a2a_agent_node(state)

        assert result["current_agent_index"] == 2
        assert len(result["agent_outputs"]) == 1
        # The node reads role from a2a_config.get("role", "a2a_agent"),
        # not from external_agents[0]["role"]
        assert result["agent_outputs"][0]["role"] == "a2a_agent"
        assert "External analysis" in result["agent_outputs"][0]["content"]

    @pytest.mark.asyncio
    async def test_handles_agent_error_gracefully(self, httpx_mock):
        """When the external agent fails, return error output instead of raising."""
        httpx_mock.add_response(
            url="http://failing-agent:8080",
            status_code=500,
        )

        state = {
            "a2a_config": {
                "enabled": True,
                "agent_url": "http://failing-agent:8080",
                "role": "broken_agent",
            },
            "current_agent_index": 1,
            "session_id": "test-session",
            "current_round": 1,
            "agent_profile": [{"role": "moderator"}],
            "context": "Test",
            "current_draft": "",
            "agent_outputs": [],
            "workflow_id": "wf-1",
            "workflow_version": 1,
        }

        result = await run_a2a_agent_node(state)

        # Should not raise, should return error output
        assert result["current_agent_index"] == 2
        assert len(result["agent_outputs"]) == 1
        assert "A2A agent failed" in result["agent_outputs"][0]["content"]


# ------------------------------------------------------------------
# A2A config in DebateRequest
# ------------------------------------------------------------------


class TestA2aConfigInDebateRequest:
    def test_debate_request_has_a2a_agents_field(self):
        from backend.models.schemas import CaseInput, DebateRequest

        req = DebateRequest(
            case=CaseInput(text="Test"),
            a2a_agents=[
                SchemaA2AAgentConfig(url="http://a:1", role="r1"),
                SchemaA2AAgentConfig(url="http://b:2", role="r2", position="before:moderator"),
            ],
        )
        assert len(req.a2a_agents) == 2
        assert req.a2a_agents[1].position == "before:moderator"

    def test_debate_request_a2a_agents_defaults_empty(self):
        from backend.models.schemas import CaseInput, DebateRequest

        req = DebateRequest(case=CaseInput(text="Test"))
        assert req.a2a_agents == []
