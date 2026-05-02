"""LangGraph state machine for the debate workflow."""

from __future__ import annotations

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


# Module-level compiled graph instance
debate_graph = build_graph()
