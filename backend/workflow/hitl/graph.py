"""HITL-aware LangGraph debate workflow graph.

Extends the existing debate graph with HITL nodes:
- hitl_check: runs before each agent (pause + inject handling)
- hitl_agent_query: runs after each agent (query detection + interrupt)

Flow::

    initialize → hitl_check → run_agent → hitl_agent_query ⟲ (next_agent / check_consensus)
                                         → check_consensus ⟲ (next_round / complete)
                                         → complete → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.workflow.hitl.nodes import (
    hitl_agent_query_node,
    hitl_check_node,
    reset_round_interrupt_count,
)
from backend.workflow.nodes import (
    check_consensus_node,
    complete_node,
    initialize_node,
    run_agent_node,
    should_continue_agents,
    should_continue_rounds,
)
from backend.workflow.state import DebateState


def build_hitl_graph() -> StateGraph:
    """Build and compile the HITL-aware debate workflow graph.

    The graph inserts HITL check nodes before and after each agent run:
    1. hitl_check — handles pause state and consumes pending injects
    2. run_agent — the existing agent execution (unchanged)
    3. hitl_agent_query — analyzes output and creates interrupts if needed

    The check_consensus node is wrapped to also reset the round interrupt counter.
    """
    graph = StateGraph(DebateState)

    # --- Nodes ---
    graph.add_node("initialize", initialize_node)
    graph.add_node("hitl_check", hitl_check_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("hitl_agent_query", hitl_agent_query_node)
    graph.add_node("check_consensus", _wrapped_check_consensus)
    graph.add_node("complete", complete_node)

    # --- Edges ---
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "hitl_check")

    # hitl_check → run_agent (always)
    graph.add_edge("hitl_check", "run_agent")

    # run_agent → hitl_agent_query (always)
    graph.add_edge("run_agent", "hitl_agent_query")

    # hitl_agent_query → (next_agent / check_consensus)
    graph.add_conditional_edges(
        "hitl_agent_query",
        should_continue_agents,
        {
            "next_agent": "hitl_check",
            "check_consensus": "check_consensus",
        },
    )

    # check_consensus → (next_round / complete)
    graph.add_conditional_edges(
        "check_consensus",
        should_continue_rounds,
        {
            "next_round": "hitl_check",
            "complete": "complete",
        },
    )

    graph.add_edge("complete", END)

    return graph.compile()


async def _wrapped_check_consensus(state: DebateState) -> dict:
    """Wrapper around check_consensus_node that also resets HITL round counter."""
    # Run the original check_consensus
    result = await check_consensus_node(state)

    # If advancing to next round, reset interrupt counter
    if result.get("current_round", 0) > state.get("current_round", 0):
        hitl_reset = reset_round_interrupt_count(state)
        result.update(hitl_reset)

    return result


# Module-level compiled HITL graph instance
hitl_debate_graph = build_hitl_graph()
