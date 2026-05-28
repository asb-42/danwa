"""LangGraph state machine for the debate workflow.

.. deprecated::
    This module uses hardcoded agent roles (strategist, critic, optimizer, moderator)
    and a fixed 4-role execution loop. New code should use the ``WorkflowCompiler``
    with ``wf-agent`` nodes referencing ``AgentBundle`` instances for dynamic,
    configurable agent roles.

    See ``backend.workflow.workflow_compiler.WorkflowCompiler`` for the replacement.
"""

from __future__ import annotations

import logging
import warnings

from langgraph.graph import END, StateGraph

from backend.workflow.legacy_nodes import (
    check_consensus_node,
    complete_node,
    initialize_node,
    run_agent_node,
    should_continue_agents,
    should_continue_rounds,
)
from backend.workflow.state import DebateState

logger = logging.getLogger(__name__)

warnings.warn(
    "backend.workflow.debate_graph is deprecated. Use WorkflowCompiler with wf-agent nodes instead.",
    DeprecationWarning,
    stacklevel=2,
)


# ---------------------------------------------------------------------------
# Conditional edge helpers — extension-aware routing
# ---------------------------------------------------------------------------


def _should_request_extension(state: DebateState) -> str:
    """Check if extension request should be sent after consensus check.

    Mirrors the logic in ``backend.workflow.hitl.graph._should_request_extension``
    but lives here so the A2A graph does not depend on the HITL sub-package.
    """
    current = state.get("current_round", 0)
    max_r = state.get("max_rounds", 3)
    if current <= max_r:
        return "next_round"

    if state.get("enable_extra_rounds", False):
        needs = state.get("needs_extension", False)
        if needs:
            return "extension_request"

    return "complete"


def _extension_decision_router(state: DebateState) -> str:
    """Route based on moderator's extension decision."""
    decision = state.get("extension_granted")
    if decision is True:
        return "next_round"
    return "complete"


# ---------------------------------------------------------------------------
# Standard debate graph (no HITL, no A2A)
# ---------------------------------------------------------------------------


def build_graph() -> StateGraph:
    """Build and compile the standard debate workflow graph.

    Flow::

        initialize → run_agent ⟲ (next_agent / check_consensus)
                          → check_consensus ⟲ (next_round / complete)
                          → complete → END
    """
    graph = StateGraph(DebateState)

    graph.add_node("initialize", initialize_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("check_consensus", check_consensus_node)
    graph.add_node("complete", complete_node)

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


# ---------------------------------------------------------------------------
# A2A-aware debate graph with extension support
# ---------------------------------------------------------------------------


def build_graph_with_a2a() -> StateGraph:
    """Build the A2A-aware debate graph with built-in extension support.

    The graph inserts an A2A agent node after all built-in agents, and
    routes through an extension_request node when consensus is not reached
    and the user has opted in to extra rounds.

    Flow::

        initialize → run_agent ⟲ (next_agent / run_a2a / check_consensus)
                          → run_a2a_agent → check_consensus
                          → check_consensus ⟲ (next_round / extension_request / complete)
                          → extension_request → (next_round / complete)
                          → complete → END
    """
    # Lazy imports to avoid circular dependency
    from backend.a2a.node import run_a2a_agent_node
    from backend.workflow.hitl.nodes import extension_request_node

    graph = StateGraph(DebateState)

    # --- Nodes ---
    graph.add_node("initialize", initialize_node)
    graph.add_node("run_agent", run_agent_node)
    graph.add_node("run_a2a_agent", run_a2a_agent_node)
    graph.add_node("check_consensus", _wrapped_check_consensus)
    graph.add_node("extension_request", extension_request_node)
    graph.add_node("complete", complete_node)

    # --- Edges ---
    graph.set_entry_point("initialize")
    graph.add_edge("initialize", "run_agent")

    # After built-in agents: route to next agent, A2A agent, or consensus check
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

    # After consensus: continue rounds, request extension, or finish
    graph.add_conditional_edges(
        "check_consensus",
        _should_request_extension,
        {
            "next_round": "run_agent",
            "extension_request": "extension_request",
            "complete": "complete",
        },
    )

    # Extension decision: grant → next round, deny/timeout → complete
    graph.add_conditional_edges(
        "extension_request",
        _extension_decision_router,
        {
            "next_round": "run_agent",
            "complete": "complete",
        },
    )

    graph.add_edge("complete", END)

    logger.info("Built A2A-aware debate graph with extension support")
    return graph.compile()


async def _wrapped_check_consensus(state: DebateState) -> dict:
    """Wrapper around check_consensus_node that also resets the interrupt counter."""
    from backend.workflow.hitl.nodes import reset_round_interrupt_count

    result = await check_consensus_node(state)

    if result.get("current_round", 0) > state.get("current_round", 0):
        reset = reset_round_interrupt_count(state)
        result.update(reset)

    return result


def should_continue_agents_or_a2a(state: DebateState) -> str:
    """Check if more agents need to run, or if A2A agent should run.

    Returns:
        ``"next_agent"`` if there are more built-in agents,
        ``"run_a2a"`` if all built-in agents are done and A2A is configured,
        ``"check_consensus"`` otherwise.
    """
    if state["current_agent_index"] < len(state["agent_profile"]):
        return "next_agent"

    a2a_config = state.get("a2a_config")
    if a2a_config and a2a_config.get("enabled") and a2a_config.get("agent_url"):
        return "run_a2a"

    return "check_consensus"


# Module-level compiled graph instances
debate_graph = build_graph()
# NOTE: a2a_debate_graph is built lazily to avoid circular imports at module load.
# Call get_a2a_debate_graph() to obtain the compiled instance.


def get_a2a_debate_graph() -> StateGraph:
    """Return the A2A-aware debate graph, building it on first call."""
    # Rebuild each time to pick up latest node implementations
    return build_graph_with_a2a()
