"""Tests for Phase 2 Group G.2 — Workflow Node Functions.

Covers input_node, initialize_wf_node, agent_node_factory, gate_node_factory,
interjection_node, and moderator_node_factory.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.workflow.node_functions import (
    agent_node_factory,
    complete_wf_node,
    gate_node_factory,
    initialize_wf_node,
    input_node,
    interjection_node,
    moderator_node_factory,
)
from backend.workflow.workflow_state import WorkflowState


def _make_state(**overrides) -> WorkflowState:
    """Build a minimal WorkflowState dict for testing."""
    base: dict = {
        "workflow_id": "wf-test",
        "session_id": "sess-test",
        "project_id": "default",
        "context": "Test case context",
        "language": "de",
        "node_sequence": ["wf-input", "wf-initialize", "node-s1"],
        "node_configs": {},
        "edge_map": {},
        "termination_conditions": [],
        "current_node_id": "wf-input",
        "current_round": 1,
        "max_rounds": 10,
        "threshold": 0.7,
        "node_outputs": [],
        "messages": [],
        "current_draft": "",
        "interjection_queue": [],
        "consumed_interjections": [],
        "final_consensus": 0.0,
        "output": "",
        "status": "running",
        "is_paused": False,
        "pause_event": None,
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# input_node
# ---------------------------------------------------------------------------


class TestInputNode:
    """Test input_node() sets context correctly."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_input_node_returns_context(self, mock_publish: AsyncMock) -> None:
        """input_node should return the context as current_draft."""
        state = _make_state(context="My debate topic")
        result = await input_node(state)

        assert "node_outputs" in result
        assert len(result["node_outputs"]) == 1
        assert result["node_outputs"][0]["content"] == "My debate topic"
        assert result["current_draft"] == "My debate topic"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_input_node_publishes_events(self, mock_publish: AsyncMock) -> None:
        """input_node should publish node.start and node.complete events."""
        state = _make_state()
        await input_node(state)

        assert mock_publish.call_count == 2
        events = [call.args[1] for call in mock_publish.call_args_list]
        assert "node.start" in events
        assert "node.complete" in events

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_input_node_zero_tokens(self, mock_publish: AsyncMock) -> None:
        """input_node should report zero tokens used."""
        state = _make_state()
        result = await input_node(state)
        assert result["node_outputs"][0]["tokens_used"] == 0


# ---------------------------------------------------------------------------
# initialize_wf_node
# ---------------------------------------------------------------------------


class TestInitializeNode:
    """Test initialize_wf_node() resets state."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_initialize_resets_round(self, mock_publish: AsyncMock) -> None:
        """initialize_wf_node should set current_round=1."""
        state = _make_state(current_round=5)
        result = await initialize_wf_node(state)
        assert result["current_round"] == 1

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_initialize_clears_draft(self, mock_publish: AsyncMock) -> None:
        """initialize_wf_node should clear current_draft."""
        state = _make_state(current_draft="old draft")
        result = await initialize_wf_node(state)
        assert result["current_draft"] == ""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_initialize_resets_consensus(self, mock_publish: AsyncMock) -> None:
        """initialize_wf_node should reset final_consensus to 0.0."""
        state = _make_state(final_consensus=0.9)
        result = await initialize_wf_node(state)
        assert result["final_consensus"] == 0.0


# ---------------------------------------------------------------------------
# agent_node_factory
# ---------------------------------------------------------------------------


class TestAgentNodeFactory:
    """Test agent_node_factory() with mock LLM."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_agent_produces_output(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """agent_node_factory should produce output from LLM call."""
        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(return_value=AsyncMock(content="Agent response", tokens_out=10, duration_ms=100))
        mock_llm_cls.return_value = mock_service

        config = {
            "blueprint_id": "bp-1",
            "blueprint_name": "Strategist",
            "llm_profile_id": "prof-1",
            "llm_model": "gpt-4",
            "role_definition_id": "role-1",
            "role": "strategist",
            "prompt_template_id": None,
        }
        node_fn = agent_node_factory("node-s1", "wf-strategist", config)
        state = _make_state()

        with patch("backend.workflow.node_functions._get_profile_service") as mock_ps:
            mock_ps.return_value = AsyncMock()
            result = await node_fn(state)

        assert "node_outputs" in result
        assert len(result["node_outputs"]) == 1
        assert result["node_outputs"][0]["content"] == "Agent response"
        assert result["node_outputs"][0]["role"] == "strategist"
        assert result["node_outputs"][0]["status"] == "completed"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_agent_handles_llm_failure(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """agent_node_factory should handle LLM failures gracefully."""
        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(side_effect=Exception("LLM unavailable"))
        mock_llm_cls.return_value = mock_service

        config = {
            "blueprint_id": "bp-1",
            "blueprint_name": "Strategist",
            "llm_profile_id": "prof-1",
            "llm_model": "gpt-4",
            "role_definition_id": "role-1",
            "role": "strategist",
            "prompt_template_id": None,
        }
        node_fn = agent_node_factory("node-s1", "wf-strategist", config)
        state = _make_state()

        with patch("backend.workflow.node_functions._get_profile_service") as mock_ps:
            mock_ps.return_value = AsyncMock()
            result = await node_fn(state)

        assert result["node_outputs"][0]["status"] == "failed"
        assert "LLM call failed" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_agent_appends_to_draft(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """agent_node_factory should append content to current_draft."""
        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(return_value=AsyncMock(content="New content", tokens_out=5, duration_ms=50))
        mock_llm_cls.return_value = mock_service

        config = {
            "blueprint_id": "bp-1",
            "blueprint_name": "Test",
            "llm_profile_id": "prof-1",
            "llm_model": "gpt-4",
            "role_definition_id": "role-1",
            "role": "strategist",
            "prompt_template_id": None,
        }
        node_fn = agent_node_factory("node-s1", "wf-strategist", config)
        state = _make_state(current_draft="Existing draft")

        with patch("backend.workflow.node_functions._get_profile_service") as mock_ps:
            mock_ps.return_value = AsyncMock()
            result = await node_fn(state)

        assert "Existing draft" in result["current_draft"]
        assert "New content" in result["current_draft"]


# ---------------------------------------------------------------------------
# gate_node_factory
# ---------------------------------------------------------------------------


class TestGateNodeFactory:
    """Test gate_node_factory() with true/false conditions."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    async def test_gate_evaluates_true_condition(self, mock_publish: AsyncMock) -> None:
        """gate_node_factory should evaluate a true condition."""
        node_fn = gate_node_factory("gate-1", "current_round >= 1")
        state = _make_state(current_round=3)
        result = await node_fn(state)

        assert "node_outputs" in result
        assert result["node_outputs"][0]["node_type"] == "wf-gate"
        assert "True" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    async def test_gate_evaluates_false_condition(self, mock_publish: AsyncMock) -> None:
        """gate_node_factory should evaluate a false condition."""
        node_fn = gate_node_factory("gate-1", "current_round >= 10")
        state = _make_state(current_round=1)
        result = await node_fn(state)

        assert "node_outputs" in result
        assert "False" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    async def test_gate_empty_condition(self, mock_publish: AsyncMock) -> None:
        """gate_node_factory with empty condition should not raise."""
        node_fn = gate_node_factory("gate-1", "")
        state = _make_state()
        result = await node_fn(state)

        assert "node_outputs" in result


# ---------------------------------------------------------------------------
# interjection_node
# ---------------------------------------------------------------------------


class TestInterjectionNode:
    """Test interjection_node() with empty and non-empty queues."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_empty_queue_pauses(self, mock_publish: AsyncMock) -> None:
        """interjection_node with empty queue should set is_paused=True."""
        state = _make_state(interjection_queue=[])
        result = await interjection_node(state)

        assert result["is_paused"] is True
        assert result["node_outputs"][0]["status"] == "pending"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_queued_items_consumed(self, mock_publish: AsyncMock) -> None:
        """interjection_node with queued items should consume them."""
        state = _make_state(
            interjection_queue=[
                {"id": "inj-1", "content": "First input"},
                {"id": "inj-2", "content": "Second input"},
            ]
        )
        result = await interjection_node(state)

        assert "is_paused" not in result
        assert result["interjection_queue"] == []  # Cleared
        assert "inj-1" in result["consumed_interjections"]
        assert "inj-2" in result["consumed_interjections"]
        assert "First input" in result["node_outputs"][0]["content"]
        assert "Second input" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_consumed_appended_to_draft(self, mock_publish: AsyncMock) -> None:
        """interjection_node should append consumed content to current_draft."""
        state = _make_state(
            current_draft="Existing",
            interjection_queue=[{"id": "inj-1", "content": "User note"}],
        )
        result = await interjection_node(state)

        assert "Existing" in result["current_draft"]
        assert "User note" in result["current_draft"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_legacy_zero_pause_timeout_falls_through(self, mock_publish: AsyncMock) -> None:
        """Without ``pause_timeout`` (default 0), an empty queue still
        sets ``is_paused=True`` immediately — the legacy behaviour all
        pre-existing tests rely on.
        """
        state = _make_state(interjection_queue=[])
        result = await interjection_node(state)

        assert result["is_paused"] is True
        assert result["node_outputs"][0]["status"] == "pending"


class TestInterjectionNodeBlocking:
    """Test the H6 fix: interjection_node actually waits for human input
    when ``pause_timeout > 0`` and the queue is empty.
    """

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_drains_service_queue_when_state_empty(self, mock_publish: AsyncMock) -> None:
        """Items submitted via ``interjection_service.submit()`` (the API
        path) must be consumed even if the in-state queue is empty.
        """
        import asyncio

        from backend.workflow.interjection import interjection_service

        session_id = "sess-blocking-1"
        await interjection_service.clear(session_id)

        async def submitter() -> None:
            await asyncio.sleep(0.01)
            await interjection_service.submit(session_id, "API note", source="api")

        task = asyncio.create_task(submitter())
        state = _make_state(session_id=session_id, interjection_queue=[], pause_timeout=2.0)
        result = await interjection_node(state)
        await task
        await interjection_service.clear(session_id)

        assert "is_paused" not in result
        assert result["interjection_queue"] == []
        assert len(result["consumed_interjections"]) == 1
        assert "API note" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_blocks_until_submit_then_returns(self, mock_publish: AsyncMock) -> None:
        """With ``pause_timeout > 0`` and an empty queue, the node must
        wait for ``interjection_service.submit()`` rather than set
        ``is_paused=True`` immediately.
        """
        import asyncio

        from backend.workflow.interjection import interjection_service

        session_id = "sess-blocking-2"
        await interjection_service.clear(session_id)

        async def submitter() -> None:
            await asyncio.sleep(0.05)
            await interjection_service.submit(session_id, "Delayed", source="user")

        task = asyncio.create_task(submitter())
        state = _make_state(session_id=session_id, interjection_queue=[], pause_timeout=5.0)
        result = await interjection_node(state)
        await task
        await interjection_service.clear(session_id)

        assert "is_paused" not in result
        assert len(result["consumed_interjections"]) == 1
        assert "Delayed" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_times_out_and_pauses(self, mock_publish: AsyncMock) -> None:
        """If nothing arrives within ``pause_timeout``, the node must
        fall back to setting ``is_paused=True`` (preserving the
        original pause semantics — but now *after* a real wait rather
        than instantly).
        """
        from backend.workflow.interjection import interjection_service

        session_id = "sess-blocking-3"
        await interjection_service.clear(session_id)

        state = _make_state(session_id=session_id, interjection_queue=[], pause_timeout=0.2)
        result = await interjection_node(state)
        await interjection_service.clear(session_id)

        assert result["is_paused"] is True
        assert result["node_outputs"][0]["status"] == "pending"


# ---------------------------------------------------------------------------
# moderator_node_factory
# ---------------------------------------------------------------------------


class TestModeratorNodeFactory:
    """Test moderator_node_factory() consensus evaluation."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_moderator_produces_consensus(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """moderator_node_factory should compute and return a consensus score."""
        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(return_value=AsyncMock(content="Moderator synthesis", tokens_out=15, duration_ms=80))
        mock_llm_cls.return_value = mock_service

        config = {
            "blueprint_id": "bp-mod",
            "blueprint_name": "Moderator",
            "llm_profile_id": "prof-1",
            "llm_model": "gpt-4",
            "role_definition_id": "role-mod",
            "role": "moderator",
            "prompt_template_id": None,
        }
        node_fn = moderator_node_factory("node-mod", config, threshold=0.7)
        state = _make_state(
            node_outputs=[
                {"node_id": "a", "content": "x"},
                {"node_id": "b", "content": "y"},
            ]
        )

        with patch("backend.workflow.node_functions._get_profile_service") as mock_ps:
            mock_ps.return_value = AsyncMock()
            result = await node_fn(state)

        assert "final_consensus" in result
        assert 0.0 <= result["final_consensus"] <= 1.0

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_moderator_publishes_consensus_event(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """moderator_node_factory should publish a consensus.reached event."""
        mock_service = AsyncMock()
        mock_service.generate = AsyncMock(return_value=AsyncMock(content="Synthesis", tokens_out=10, duration_ms=50))
        mock_llm_cls.return_value = mock_service

        config = {
            "blueprint_id": "bp-mod",
            "blueprint_name": "Moderator",
            "llm_profile_id": "prof-1",
            "llm_model": "gpt-4",
            "role_definition_id": "role-mod",
            "role": "moderator",
            "prompt_template_id": None,
        }
        node_fn = moderator_node_factory("node-mod", config)
        state = _make_state()

        with patch("backend.workflow.node_functions._get_profile_service") as mock_ps:
            mock_ps.return_value = AsyncMock()
            await node_fn(state)

        events = [call.args[1] for call in mock_publish.call_args_list]
        assert "consensus.reached" in events


# ---------------------------------------------------------------------------
# complete_wf_node
# ---------------------------------------------------------------------------


class TestCompleteNode:
    """Test complete_wf_node() assembles final output."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_complete_sets_output(self, mock_publish: AsyncMock) -> None:
        """complete_wf_node should set the output field."""
        state = _make_state(current_draft="Final draft content")
        result = await complete_wf_node(state)

        assert result["output"] == "Final draft content"
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    async def test_complete_publishes_workflow_complete(self, mock_publish: AsyncMock) -> None:
        """complete_wf_node should publish workflow.complete event."""
        state = _make_state()
        await complete_wf_node(state)

        events = [call.args[1] for call in mock_publish.call_args_list]
        assert "workflow.complete" in events
