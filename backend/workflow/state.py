"""LangGraph state definition for the debate workflow."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict


class AgentConfigState(TypedDict):
    role: str
    llm_profile: str
    temperature: float


class AgentOutputState(TypedDict):
    role: str
    content: str
    tokens_used: int


class RoundDataState(TypedDict):
    round: int
    consensus: float
    agent_outputs: list[AgentOutputState]


class DebateState(TypedDict, total=False):
    """Shared state passed through every LangGraph node.

    Fields using ``Annotated[..., operator.add]`` are list accumulators —
    each node *appends* to them rather than replacing.
    """

    # --- Input (set at creation) ---
    context: str
    agent_profile: list[AgentConfigState]
    max_rounds: int
    threshold: float
    enable_fact_check: bool
    enable_memory: bool
    rag_context: str

    # --- Profile configuration (Sprint 3) ---
    llm_profile_id: str
    prompt_variant: str
    agent_persona_ids: dict[str, str]  # role → persona_id mapping

    # --- Runtime ---
    session_id: str
    current_round: int
    current_agent_index: int

    # --- Accumulators ---
    rounds: Annotated[list[RoundDataState], operator.add]
    agent_outputs: Annotated[list[AgentOutputState], operator.add]
    current_draft: str

    # --- Output ---
    final_consensus: float
    output: str
    validation_report: list[dict]
    used_variant: str
