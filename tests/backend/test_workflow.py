"""Tests for the LangGraph workflow (unit tests, no HTTP)."""

from __future__ import annotations

import pytest

from backend.workflow.debate_graph import build_graph
from backend.workflow.legacy_nodes import (
    check_consensus_node,
    complete_node,
    initialize_node,
    run_agent_node,
    should_continue_agents,
    should_continue_rounds,
)


def _make_state(**overrides) -> dict:
    """Helper to build a minimal DebateState."""
    state = {
        "context": "Test case",
        "agent_profile": [
            {"role": "strategist", "llm_profile": "default", "temperature": 0.7},
            {"role": "critic", "llm_profile": "default", "temperature": 0.7},
        ],
        "max_rounds": 2,
        "threshold": 0.8,
        "enable_fact_check": False,
        "enable_memory": False,
        "rag_context": "",
        "session_id": "test-session",
        "current_round": 0,
        "current_agent_index": 0,
        "rounds": [],
        "agent_outputs": [],
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "validation_report": [],
        "used_variant": "default",
    }
    state.update(overrides)
    return state


class TestNodes:
    def test_initialize_node(self):
        state = _make_state()
        result = initialize_node(state)
        assert result["current_round"] == 1
        assert result["current_agent_index"] == 0
        assert result["final_consensus"] == 0.0

    @pytest.mark.asyncio
    async def test_run_agent_node(self):
        state = _make_state(current_round=1, current_agent_index=0)
        result = await run_agent_node(state)
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["role"] == "strategist"
        assert result["current_agent_index"] == 1

    @pytest.mark.asyncio
    async def test_check_consensus_node(self):
        state = _make_state(current_round=1, max_rounds=2, threshold=0.8)
        result = await check_consensus_node(state)
        assert len(result["rounds"]) == 1
        assert 0.0 <= result["final_consensus"] <= 1.0

    @pytest.mark.asyncio
    async def test_complete_node(self):
        state = _make_state(current_draft="Some draft")
        result = await complete_node(state)
        assert result["output"] == "Some draft"


class TestConditionalEdges:
    def test_should_continue_agents_more_to_go(self):
        state = _make_state(current_agent_index=0)
        assert should_continue_agents(state) == "next_agent"

    def test_should_continue_agents_all_done(self):
        state = _make_state(current_agent_index=2)  # 2 agents defined
        assert should_continue_agents(state) == "check_consensus"

    def test_should_continue_rounds_consensus_reached(self):
        state = _make_state(final_consensus=0.9, threshold=0.8, current_round=1, max_rounds=3)
        assert should_continue_rounds(state) == "complete"

    def test_should_continue_rounds_max_reached(self):
        # After check_consensus_node increments round, current_round > max_rounds
        state = _make_state(final_consensus=0.1, threshold=0.8, current_round=4, max_rounds=3)
        assert should_continue_rounds(state) == "complete"

    def test_should_continue_rounds_next(self):
        state = _make_state(final_consensus=0.1, threshold=0.8, current_round=1, max_rounds=3)
        assert should_continue_rounds(state) == "next_round"


class TestGraphIntegration:
    def test_build_graph_returns_compiled(self):
        graph = build_graph()
        assert graph is not None

    @pytest.mark.asyncio
    async def test_graph_runs_full_cycle(self):
        graph = build_graph()
        state = _make_state(max_rounds=1, threshold=0.5)
        result = await graph.ainvoke(state)
        assert result["output"] != ""
        # When LLM calls fail (no real profile), consensus is capped at 0
        # and anomalies are recorded — this is the correct behavior
        assert result["final_consensus"] == 0.0
        assert len(result.get("anomalies", [])) > 0

    @pytest.mark.asyncio
    async def test_graph_respects_max_rounds(self):
        graph = build_graph()
        state = _make_state(max_rounds=2, threshold=0.99)  # high threshold, should hit max
        result = await graph.ainvoke(state)
        # Should complete after max_rounds even without reaching threshold
        assert result["output"] != ""
