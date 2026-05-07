"""LangGraph state machine for the debate workflow."""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph

from backend.workflow.nodes import (
    check_consensus_node,
    complete_node,
    initialize_node,
    run_agent_node,
    should_continue_agents,
    should_continue_rounds,
)
from backend.workflow.state import DebateState

logger = logging.getLogger(__name__)


def build_graph() -> StateGraph:
    """Build and compile the debate workflow graph.

    Flow::

        initialize → run_agent ⟲ (next_agent / check_consensus)
                              → check_consensus ⟲ (next_round / complete)
                              → complete → END
    """
    graph = StateGraph(DebateState)

    # --- Nodes ---
    graph.add_node("initialize", initialize_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("check_consensus", check_consensus_node)
    graph.add_node("complete", complete_node)

    # --- Edges ---
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "run_agent")

    graph.add_conditional_edges(
        "run_agent",
        should_continue_agents,
        {
            "next_agent": "run_agent",
            "check_consensus": "check_consensus",
        },
    )

    graph.add_conditional_edges(
        "check_consensus",
        should_continue_rounds,
        {
            "next_round": "run_agent",
            "complete": "complete",
        },
    )

    graph.add_edge("complete", END)

    return graph.compile()


def build_graph_with_a2a() -> StateGraph:
    """Build debate graph with an A2A agent node inserted after all built-in agents.

    Flow::

        initialize → run_agent ⟲ (next_agent / run_a2a / check_consensus)
                              → run_a2a_agent → check_consensus
                              → check_consensus ⟲ (next_round / complete)
                              → complete → END
    """
    from backend.a2a.node import run_a2a_agent_node

    graph = StateGraph(DebateState)

    # --- Nodes ---
    graph.add_node("initialize", initialize_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("run_a2a_agent", run_a2a_agent_node)
    graph.add_node("check_consensus", check_consensus_node)
    graph.add_node("complete", complete_node)

    # --- Edges ---
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "run_agent")

    # After all built-in agents: route to A2A agent or directly to consensus check
    graph.add_conditional_edges(
        "run_agent",
        should_continue_agents_or_a2a,
        {
            "next_agent": "run_agent",
            "run_a2a": "run_a2a_agent",
            "check_consensus": "check_consensus",
        },
    )

    # A2A agent always goes to consensus check
    graph.add_edge("run_a2a_agent", "check_consensus")

    graph.add_conditional_edges(
        "check_consensus",
        should_continue_rounds,
        {
            "next_round": "run_agent",
            "complete": "complete",
        },
    )

    graph.add_edge("complete", END)

    logger.info("Built A2A-aware debate graph")
    return graph.compile()


def should_continue_agents_or_a2a(state: DebateState) -> str:
    """Check if more agents need to run, or if A2A agent should run.

    Returns:
        ``"next_agent"`` if there are more built-in agents,
        ``"run_a2a"`` if all built-in agents are done and A2A is configured,
        ``"check_consensus"`` otherwise.
    """
    if state["current_agent_index"] < len(state["agent_profile"]):
        return "next_agent"

    # Check if A2A agent is configured for this debate
    a2a_config = state.get("a2a_config")
    if a2a_config and a2a_config.get("enabled") and a2a_config.get("agent_url"):
        return "run_a2a"

    return "check_consensus"


# Module-level compiled graph instances
debate_graph = build_graph()
a2a_debate_graph = build_graph_with_a2a()
