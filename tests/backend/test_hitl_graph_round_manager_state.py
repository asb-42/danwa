"""Smoke tests for the three HITL modules that had 0 % coverage.

Targets:
- backend/workflow/hitl/state.py         (38 stmts)
- backend/workflow/hitl/graph.py         (45 stmts)
- backend/workflow/hitl/round_manager.py (106 stmts)

The goal is not exhaustive behavioural coverage — that comes in a
follow-up. These tests pin the public surface (TypedDict shapes,
graph build, round-manager API) so future refactors break loudly.
"""

from __future__ import annotations

import operator
from typing import get_type_hints

import pytest

# ---------------------------------------------------------------------------
# backend/workflow/hitl/state.py
# ---------------------------------------------------------------------------


class TestHITLStateTypedDicts:
    """Pin the shape of the HITL TypedDicts so the LangGraph state
    schema doesn't drift unnoticed."""

    def test_interaction_keys(self):
        from backend.workflow.hitl.state import Interaction

        hints = get_type_hints(Interaction)
        expected = {
            "interaction_id",
            "type",
            "direction",
            "source",
            "target",
            "content",
            "round",
            "agent_index",
            "timestamp",
            "status",
            "metadata",
        }
        assert expected.issubset(hints.keys())

    def test_interrupt_context_keys(self):
        from backend.workflow.hitl.state import InterruptContext

        hints = get_type_hints(InterruptContext)
        expected = {
            "interrupt_id",
            "debate_id",
            "agent_role",
            "agent_index",
            "round",
            "question",
            "context",
            "created_at",
            "timeout_seconds",
            "status",
            "response",
            "responded_at",
        }
        assert expected.issubset(hints.keys())

    def test_hitl_state_interactions_uses_add_reducer(self):
        """``interactions`` is a list-accumulator; verify the Annotated
        metadata is intact so LangGraph doesn't drop entries on merge."""
        from backend.workflow.hitl.state import HITLState

        hints = get_type_hints(HITLState, include_extras=True)
        ann = hints["interactions"]
        # Annotated[list[Interaction], operator.add] -> metadata = (operator.add,)
        metadata = getattr(ann, "__metadata__", ())
        assert operator.add in metadata

    def test_hitl_state_contains_core_keys(self):
        from backend.workflow.hitl.state import HITLState

        hints = get_type_hints(HITLState)
        for key in (
            "interactions",
            "active_interrupt",
            "hitl_enabled",
            "hitl_mode",
            "auto_query_threshold",
            "max_interrupts_per_round",
            "interrupt_timeout_seconds",
            "pending_injects",
            "round_interrupt_count",
        ):
            assert key in hints, f"HITLState is missing required key {key!r}"


# ---------------------------------------------------------------------------
# backend/workflow/hitl/round_manager.py
# ---------------------------------------------------------------------------


@pytest.fixture
def manager():
    from backend.workflow.hitl.round_manager import (
        HITLRoundManager,
        remove_round_manager,
    )

    remove_round_manager("d-smoke")
    yield HITLRoundManager("d-smoke")
    remove_round_manager("d-smoke")


class TestHITLRoundManagerLifecycle:
    def test_start_round_creates_stats(self, manager):
        manager.start_round(1)
        stats = manager.get_round_stats(1)
        assert stats is not None
        assert stats.round == 1
        assert stats.injects_consumed == 0
        assert stats.queries_triggered == 0

    def test_start_round_is_idempotent(self, manager):
        manager.start_round(2)
        manager.record_inject(2, {"id": "x"})
        manager.start_round(2)  # must not reset
        stats = manager.get_round_stats(2)
        assert stats.injects_consumed == 1

    def test_get_round_stats_missing_returns_none(self, manager):
        assert manager.get_round_stats(99) is None


class TestHITLRoundManagerRecording:
    def test_record_inject_increments_and_appends(self, manager):
        manager.record_inject(1, {"id": "i1"})
        manager.record_inject(1, {"id": "i2"})
        stats = manager.get_round_stats(1)
        assert stats.injects_consumed == 2
        assert [i["id"] for i in stats.interactions] == ["i1", "i2"]

    def test_record_query_increments(self, manager):
        manager.record_query(1, {"id": "q1"})
        manager.record_query(1, {"id": "q2"})
        manager.record_query(1, {"id": "q3"})
        stats = manager.get_round_stats(1)
        assert stats.queries_triggered == 3

    def test_record_response_increments_answered(self, manager):
        manager.record_query(1, {"id": "q1"})
        manager.record_response(1, {"id": "r1"})
        stats = manager.get_round_stats(1)
        assert stats.queries_answered == 1
        assert stats.queries_triggered == 1  # unchanged

    def test_record_timeout_increments_only_timeout(self, manager):
        manager.record_timeout(1)
        manager.record_timeout(1)
        stats = manager.get_round_stats(1)
        assert stats.queries_timed_out == 2
        assert stats.queries_triggered == 0  # timeout is not a query

    def test_record_pause_accumulates(self, manager):
        manager.record_pause(1, 1.5)
        manager.record_pause(1, 0.5)
        stats = manager.get_round_stats(1)
        assert stats.total_pause_seconds == pytest.approx(2.0)


class TestHITLRoundManagerSummary:
    def test_summary_aggregates_rounds(self, manager):
        # Round 1: 1 inject, 2 queries (1 answered)
        manager.start_round(1)
        manager.record_inject(1, {"id": "i1"})
        manager.record_query(1, {"id": "q1"})
        manager.record_query(1, {"id": "q2"})
        manager.record_response(1, {"id": "r1"})

        # Round 2: 0 interactions, 1 timeout
        manager.start_round(2)
        manager.record_timeout(2)

        summary = manager.get_summary()
        assert summary.debate_id == "d-smoke"
        assert summary.total_injects == 1
        assert summary.total_queries == 2
        assert summary.total_responses == 1
        assert summary.total_timeouts == 1
        assert summary.total_interactions == 1 + 2 + 1
        assert len(summary.rounds) == 2

    def test_summary_aggregates_pause_seconds(self, manager):
        manager.start_round(1)
        manager.record_pause(1, 2.0)
        manager.start_round(2)
        manager.record_pause(2, 1.0)
        summary = manager.get_summary()
        assert summary.total_pause_seconds == pytest.approx(3.0)

    def test_query_answer_rate_zero_when_no_queries(self, manager):
        summary = manager.get_summary()
        assert summary.query_answer_rate == 0.0

    def test_query_answer_rate_calculated(self, manager):
        manager.start_round(1)
        manager.record_query(1, {})
        manager.record_query(1, {})
        manager.record_response(1, {})
        summary = manager.get_summary()
        assert summary.query_answer_rate == pytest.approx(0.5)

    def test_average_pause_zero_without_rounds(self, manager):
        summary = manager.get_summary()
        assert summary.average_pause_per_round == 0.0

    def test_average_pause_per_round(self, manager):
        manager.start_round(1)
        manager.record_pause(1, 2.0)
        manager.start_round(2)
        manager.record_pause(2, 4.0)
        summary = manager.get_summary()
        assert summary.average_pause_per_round == pytest.approx(3.0)


class TestHITLRoundManagerGuard:
    def test_should_allow_query_true_when_no_stats(self, manager):
        assert manager.should_allow_query(1, max_interrupts=2) is True

    def test_should_allow_query_false_when_at_limit(self, manager):
        manager.start_round(1)
        manager.record_query(1, {})
        manager.record_query(1, {})
        assert manager.should_allow_query(1, max_interrupts=2) is False

    def test_should_allow_query_true_below_limit(self, manager):
        manager.start_round(1)
        manager.record_query(1, {})
        assert manager.should_allow_query(1, max_interrupts=2) is True


class TestHITLRoundManagerContext:
    def test_get_pending_context_empty_when_no_injects(self, manager, monkeypatch):
        from backend.workflow.hitl import round_manager as rm

        monkeypatch.setattr(rm, "get_pending_injects", lambda _debate_id: [])
        assert manager.get_pending_context("critic", round_num=1) == ""

    def test_get_pending_context_filters_by_target_agent(self, manager, monkeypatch):
        from backend.workflow.hitl import round_manager as rm

        monkeypatch.setattr(
            rm,
            "get_pending_injects",
            lambda _debate_id: [
                {"content": "for critic", "metadata": {"target_agent": "critic"}},
                {"content": "for pragmatist", "metadata": {"target_agent": "pragmatist"}},
                {"content": "broadcast", "metadata": {}},
            ],
        )
        ctx = manager.get_pending_context("critic", round_num=1)
        assert "for critic" in ctx
        assert "broadcast" in ctx
        assert "for pragmatist" not in ctx

    def test_get_pending_context_includes_priority_prefix(self, manager, monkeypatch):
        from backend.workflow.hitl import round_manager as rm

        monkeypatch.setattr(
            rm,
            "get_pending_injects",
            lambda _debate_id: [
                {"content": "urgent thing", "metadata": {"priority": "high"}},
            ],
        )
        ctx = manager.get_pending_context("critic", round_num=1)
        assert "[HIGH] urgent thing" in ctx

    def test_get_pending_context_wraps_with_markers(self, manager, monkeypatch):
        from backend.workflow.hitl import round_manager as rm

        monkeypatch.setattr(
            rm,
            "get_pending_injects",
            lambda _debate_id: [
                {"content": "hello", "metadata": {"target_agent": "critic"}},
            ],
        )
        ctx = manager.get_pending_context("critic", round_num=1)
        assert "--- USER CONTEXT ---" in ctx
        assert "--- END CONTEXT ---" in ctx


class TestHITLRoundManagerRegistry:
    def test_get_round_manager_returns_singleton(self):
        from backend.workflow.hitl.round_manager import (
            get_round_manager,
            remove_round_manager,
        )

        remove_round_manager("d-singleton")
        a = get_round_manager("d-singleton")
        b = get_round_manager("d-singleton")
        assert a is b
        remove_round_manager("d-singleton")

    def test_remove_round_manager_clears(self):
        from backend.workflow.hitl.round_manager import (
            get_round_manager,
            remove_round_manager,
        )

        remove_round_manager("d-rm")
        get_round_manager("d-rm").start_round(1)
        remove_round_manager("d-rm")
        # after removal, a fresh manager is created with empty state
        from backend.workflow.hitl.round_manager import get_round_manager as grm

        assert grm("d-rm").get_round_stats(1) is None
        remove_round_manager("d-rm")

    def test_remove_round_manager_missing_is_noop(self):
        from backend.workflow.hitl.round_manager import remove_round_manager

        # Must not raise
        remove_round_manager("d-does-not-exist")


# ---------------------------------------------------------------------------
# backend/workflow/hitl/graph.py
# ---------------------------------------------------------------------------


class TestHITLGraphBuild:
    def test_build_hitl_graph_returns_compiled_graph(self):
        from backend.workflow.hitl.graph import build_hitl_graph

        g = build_hitl_graph()
        # A compiled StateGraph exposes ``get_graph`` and ``invoke``/``ainvoke``
        assert hasattr(g, "invoke") or hasattr(g, "ainvoke")
        assert hasattr(g, "get_graph")

    def test_module_level_graph_exists(self):
        from backend.workflow.hitl import graph as hitl_graph_module

        # The module compiles a single shared instance for callers to reuse
        assert hasattr(hitl_graph_module, "hitl_debate_graph")
        assert callable(hitl_graph_module.build_hitl_graph)


class TestHITLRouters:
    def test_should_request_extension_within_max_rounds(self):
        from backend.workflow.hitl.graph import _should_request_extension

        assert _should_request_extension({"current_round": 1, "max_rounds": 3}) == "next_round"
        assert _should_request_extension({"current_round": 3, "max_rounds": 3}) == "next_round"

    def test_should_request_extension_beyond_max_rounds_without_extra(self):
        from backend.workflow.hitl.graph import _should_request_extension

        result = _should_request_extension({"current_round": 4, "max_rounds": 3, "enable_extra_rounds": False})
        assert result == "complete"

    def test_should_request_extension_needs_extension(self):
        from backend.workflow.hitl.graph import _should_request_extension

        result = _should_request_extension(
            {
                "current_round": 4,
                "max_rounds": 3,
                "enable_extra_rounds": True,
                "needs_extension": True,
            }
        )
        assert result == "extension_request"

    def test_should_request_extension_extra_enabled_but_not_needed(self):
        from backend.workflow.hitl.graph import _should_request_extension

        result = _should_request_extension(
            {
                "current_round": 4,
                "max_rounds": 3,
                "enable_extra_rounds": True,
                "needs_extension": False,
            }
        )
        assert result == "complete"

    def test_extension_decision_router_granted(self):
        from backend.workflow.hitl.graph import _extension_decision_router

        assert _extension_decision_router({"extension_granted": True}) == "next_round"

    @pytest.mark.parametrize("decision", [False, None, "denied", "timeout", "pending", 0, ""])
    def test_extension_decision_router_denies(self, decision):
        from backend.workflow.hitl.graph import _extension_decision_router

        assert _extension_decision_router({"extension_granted": decision}) == "complete"

    @pytest.mark.asyncio
    async def test_wrapped_check_consensus_resets_counter_on_advance(self, monkeypatch):
        from backend.workflow.hitl import graph as hitl_graph_module

        # Build the graph so any module-level singletons are created
        hitl_graph_module.build_hitl_graph()

        state = {
            "current_round": 1,
            "max_rounds": 3,
            "round_interrupt_count": 5,
        }

        # The real reset_round_interrupt_count is a sync function that
        # returns a dict, NOT an async coroutine.
        async def fake_check(_state):
            return {"current_round": 2, "consensus_reached": False}

        def fake_reset(_state):
            return {"round_interrupt_count": 0}

        # The graph module imported the symbols at module-load time
        # (``from backend.workflow.legacy_nodes import ...``), so we must
        # patch them in the graph module's namespace, not in the original
        # source module.
        monkeypatch.setattr(hitl_graph_module, "check_consensus_node", fake_check)
        monkeypatch.setattr(hitl_graph_module, "reset_round_interrupt_count", fake_reset)

        result = await hitl_graph_module._wrapped_check_consensus(state)

        assert result["current_round"] == 2
        assert result["round_interrupt_count"] == 0

    @pytest.mark.asyncio
    async def test_wrapped_check_consensus_keeps_counter_when_staying(self, monkeypatch):
        from backend.workflow.hitl import graph as hitl_graph_module

        state = {
            "current_round": 2,
            "max_rounds": 3,
            "round_interrupt_count": 5,
        }

        async def fake_check(_state):
            # consensus reached -> round not advanced
            return {"current_round": 2, "consensus_reached": True}

        called = {"reset": 0}

        def fake_reset(_state):
            called["reset"] += 1
            return {"round_interrupt_count": 0}

        monkeypatch.setattr(hitl_graph_module, "check_consensus_node", fake_check)
        monkeypatch.setattr(hitl_graph_module, "reset_round_interrupt_count", fake_reset)
        result = await hitl_graph_module._wrapped_check_consensus(state)

        # No advance -> the wrapper must NOT call reset_round_interrupt_count
        assert result["current_round"] == 2
        assert called["reset"] == 0
        # The wrapper returns only the inner node's diff; existing
        # state fields (like the counter) are carried by the LangGraph
        # state, not by the partial result.
        assert "round_interrupt_count" not in result
