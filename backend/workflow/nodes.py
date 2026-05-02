"""Dummy node functions for LangGraph debate workflow.

In Sprint 1 these are no-op stubs that update state without real LLM calls.
They will be replaced with real implementations in Sprint 3.
"""

from __future__ import annotations

from backend.workflow.state import (
    AgentOutputState,
    DebateState,
    RoundDataState,
)


def initialize_node(state: DebateState) -> dict:
    """Set up initial runtime state."""
    return {
        "current_round": 1,
        "current_agent_index": 0,
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "validation_report": [],
        "used_variant": "default",
    }


def run_agent_node(state: DebateState) -> dict:
    """Run the current agent (dummy — produces placeholder output)."""
    agents = state["agent_profile"]
    idx = state["current_agent_index"]
    agent = agents[idx]

    # Dummy output — real LLM call in Sprint 3
    dummy_content = (
        f"[{agent['role']}] Round {state['current_round']}: "
        f"Analysis of '{state['context'][:50]}...'"
    )
    tokens = len(dummy_content.split())  # rough estimate

    output: AgentOutputState = {
        "role": agent["role"],
        "content": dummy_content,
        "tokens_used": tokens,
    }

    # Advance agent index
    next_index = idx + 1

    return {
        "agent_outputs": [output],
        "current_agent_index": next_index,
        "current_draft": state.get("current_draft", "") + "\n" + dummy_content,
    }


def check_consensus_node(state: DebateState) -> dict:
    """Evaluate consensus (dummy — linear progression toward threshold)."""
    current_round = state["current_round"]
    max_rounds = state["max_rounds"]
    threshold = state["threshold"]

    # Dummy consensus: approaches threshold linearly
    consensus = min(threshold, current_round / max_rounds * threshold * 1.2)

    round_data: RoundDataState = {
        "round": current_round,
        "consensus": round(consensus, 3),
        "agent_outputs": [],  # already in state.agent_outputs
    }

    # Reset agent index and advance round for next iteration
    return {
        "rounds": [round_data],
        "final_consensus": round(consensus, 3),
        "current_agent_index": 0,
        "current_round": current_round + 1,
    }


def complete_node(state: DebateState) -> dict:
    """Finalize the debate."""
    return {
        "output": state.get("current_draft", "No output generated."),
    }


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------

def should_continue_agents(state: DebateState) -> str:
    """Check if more agents need to run in this round."""
    if state["current_agent_index"] < len(state["agent_profile"]):
        return "next_agent"
    return "check_consensus"


def should_continue_rounds(state: DebateState) -> str:
    """Check if consensus reached or max rounds exceeded.

    Note: current_round is incremented by check_consensus_node before
    this function is called, so we use ``>`` (strict) to allow exactly
    max_rounds iterations.
    """
    if state["final_consensus"] >= state["threshold"]:
        return "complete"
    if state["current_round"] > state["max_rounds"]:
        return "complete"
    return "next_round"
