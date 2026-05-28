"""HITL-aware LangGraph debate workflow graph.

Extends the existing debate graph with HITL nodes:
- hitl_check: runs before each agent (pause + inject handling)
- hitl_agent_query: runs after each agent (query detection + interrupt)
- extension_request: asks moderator for extra rounds if consensus not reached

Flow::

    initialize → hitl_check → run_agent → hitl_agent_query ⟲ (next_agent / check_consensus)
                                         → check_consensus → extension_request → (next_round / complete)
                                         → complete → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.workflow.hitl.nodes import (
    extension_request_node,
    hitl_agent_query_node,
    hitl_check_node,
    reset_round_interrupt_count,
)
from backend.workflow.legacy_nodes import (
    check_consensus_node,
    complete_node,
    initialize_node,
    run_agent_node,
    should_continue_agents,
)
from backend.workflow.state import DebateState


def _should_request_extension(state: DebateState) -> str:
    """Check if extension request should be sent after consensus check.

    Returns:
        "next_round" — consensus reached or normal rounds remaining
        "extension_request" — needs extension decision
        "complete" — debate should end
    """
    # If normal rounds remain, just continue
    current = state.get("current_round", 0)
    max_r = state.get("max_rounds", 3)
    if current <= max_r:
        return "next_round"

    # Beyond normal rounds: check if extension is enabled
    if state.get("enable_extra_rounds", False):
        needs = state.get("needs_extension", False)
        if needs:
            return "extension_request"

    return "complete"


def _extension_decision_router(state: DebateState) -> str:
    """Route based on the extension decision.

    GRANTED → continue to next round
    DENIED/TIMEOUT → complete the debate
    PENDING (no decision yet) → complete as safety fallback
    """
    decision = state.get("extension_granted")
    if decision is True:
        return "next_round"
    # DENIED, TIMEOUT, None (pending/no decision) → complete
    return "complete"


async def _wrapped_check_consensus(state: DebateState) -> dict:
    """Wrapper around check_consensus_node that also resets HITL round counter."""
    # Run the original check_consensus
    result = await check_consensus_node(state)

    # If advancing to next round, reset interrupt counter
    if result.get("current_round", 0) > state.get("current_round", 0):
        hitl_reset = reset_round_interrupt_count(state)
        result.update(hitl_reset)

    return result


def build_hitl_graph() -> StateGraph:
    """Build and compile the HITL-aware debate workflow graph.

    The graph inserts HITL check nodes before and after each agent run:
    1. hitl_check — handles pause state and consumes pending injects
    2. run_agent — the existing agent execution (unchanged)
    3. hitl_agent_query — analyzes output and creates interrupts if needed
    4. extension_request — asks moderator for extra rounds if consensus not reached

    The check_consensus node is wrapped to also reset the round interrupt counter.
    """
    graph = StateGraph(DebateState)

    # --- Nodes ---
    graph.add_node("initialize", initialize_node)
    graph.add_node("hitl_check", hitl_check_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("hitl_agent_query", hitl_agent_query_node)
    graph.add_node("check_consensus", _wrapped_check_consensus)
    graph.add_node("extension_request", extension_request_node)
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

    # check_consensus → extension_request for extra rounds decision
    # If extension needed, go to extension_request; otherwise follow normal flow
    graph.add_conditional_edges(
        "check_consensus",
        _should_request_extension,
        {
            "next_round": "hitl_check",
            "extension_request": "extension_request",
            "complete": "complete",
        },
    )

    # extension_request → (next_round / complete) based on decision
    graph.add_conditional_edges(
        "extension_request",
        _extension_decision_router,
        {
            "next_round": "hitl_check",
            "complete": "complete",
        },
    )

    graph.add_edge("complete", END)

    return graph.compile()


# Module-level compiled HITL graph instance
hitl_debate_graph = build_hitl_graph()
