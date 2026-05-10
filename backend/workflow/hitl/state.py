"""HITL state definitions — Interaction, InterruptContext, and extended DebateState.

These TypedDicts extend the existing LangGraph state to support
bidirectional human-in-the-loop interactions during debate workflows.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

# ---------------------------------------------------------------------------
# Interaction types
# ---------------------------------------------------------------------------


class Interaction(TypedDict, total=False):
    """A single interaction event between user and agent (or vice versa).

    Covers all three interaction types:
    - inject:  user → agent (non-blocking context injection)
    - query:   agent → user (blocking clarification request)
    - response: user → agent (reply to an agent query)
    """

    interaction_id: str  # UUID
    type: str  # 'inject' | 'query' | 'response'
    direction: str  # 'user_to_agent' | 'agent_to_user'
    source: str  # 'user' | agent role (e.g. 'critic')
    target: str  # agent role | 'user'
    content: str  # The actual message/question/answer
    round: int  # Debate round when this interaction occurred
    agent_index: int  # Index of the agent in the profile list
    timestamp: str  # ISO 8601 timestamp
    status: str  # 'pending' | 'delivered' | 'consumed' | 'expired'
    metadata: dict  # Additional context (e.g. confidence_score, reason)


class InterruptContext(TypedDict, total=False):
    """Manages an active interrupt (agent query waiting for user response).

    When an agent needs clarification, this context tracks the pending
    question and waits for the user's response before the workflow resumes.
    """

    interrupt_id: str  # UUID
    debate_id: str
    agent_role: str  # Which agent asked the question
    agent_index: int
    round: int
    question: str  # The agent's question to the user
    context: str  # Surrounding context (e.g. current draft snippet)
    created_at: str  # ISO 8601
    timeout_seconds: int  # Max wait time (default: 300)
    status: str  # 'waiting' | 'answered' | 'timeout' | 'cancelled'
    response: str | None  # User's answer (once provided)
    responded_at: str | None  # ISO 8601


# ---------------------------------------------------------------------------
# Extended DebateState
# ---------------------------------------------------------------------------


class HITLState(TypedDict, total=False):
    """HITL-specific state fields that extend DebateState.

    These fields are merged into the main DebateState via LangGraph's
    state schema.  The Annotated[..., operator.add] fields are list
    accumulators — each node appends rather than replaces.
    """

    # --- Interaction log (accumulator) ---
    interactions: Annotated[list[Interaction], operator.add]

    # --- Active interrupt ---
    active_interrupt: InterruptContext | None  # None = no pending interrupt

    # --- HITL configuration ---
    hitl_enabled: bool  # Master switch for HITL features
    hitl_mode: str  # 'full' | 'inject_only' | 'query_only' | 'off'
    auto_query_threshold: float  # Confidence below this triggers agent query (0.0-1.0)
    max_interrupts_per_round: int  # Limit interrupts per round to prevent loops
    interrupt_timeout_seconds: int  # Default timeout for agent queries

    # --- Inject queue (user injections waiting to be consumed) ---
    pending_injects: list[dict]  # List of inject interactions not yet consumed

    # --- Round interrupt counter ---
    round_interrupt_count: int  # Number of interrupts in current round
