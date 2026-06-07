"""LangGraph state definition for the debate workflow."""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class AgentConfigState(TypedDict):
    """AgentConfigState class."""

    role: str
    llm_profile: str
    temperature: float


class AgentOutputState(TypedDict):
    """AgentOutputState class."""

    role: str
    content: str
    tokens_used: int


class RoundDataState(TypedDict):
    """RoundDataState class."""

    round: int
    consensus: float
    agent_outputs: list[AgentOutputState]


class InteractionState(TypedDict, total=False):
    """A single HITL interaction event between user and agent."""

    interaction_id: str
    type: str  # 'inject' | 'query' | 'response'
    direction: str  # 'user_to_agent' | 'agent_to_user'
    source: str  # 'user' | agent role
    target: str  # agent role | 'user'
    content: str
    round: int
    agent_index: int
    timestamp: str
    status: str  # 'pending' | 'delivered' | 'consumed' | 'expired'
    metadata: dict


class InterruptContextState(TypedDict, total=False):
    """Active interrupt — agent query waiting for user response."""

    interrupt_id: str
    debate_id: str
    agent_role: str
    agent_index: int
    round: int
    question: str
    context: str
    created_at: str
    timeout_seconds: int
    status: str  # 'waiting' | 'answered' | 'timeout' | 'cancelled'
    response: str | None
    responded_at: str | None


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

    # --- Web search ---
    search_mode: str  # 'off', 'optional', 'required'

    # --- Profile configuration (Sprint 3) ---
    llm_profile_id: str
    prompt_variant: str
    agent_persona_ids: dict[str, str]  # role → persona_id mapping
    bundle_ids: list[str]  # AgentBundle IDs (module-based, supersedes agent_persona_ids)

    # --- Language (Sprint 4) ---
    language: str  # 'de' or 'en'

    # --- Project isolation ---
    project_id: str  # UUID of the active project

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
    anomalies: Annotated[list[str], operator.add]

    # --- HITL (Human-in-the-Loop) ---
    interactions: Annotated[list[InteractionState], operator.add]
    active_interrupt: InterruptContextState | None
    hitl_enabled: bool
    hitl_mode: str  # 'full' | 'inject_only' | 'query_only' | 'off'
    auto_query_threshold: float  # Confidence below this triggers agent query
    max_interrupts_per_round: int
    interrupt_timeout_seconds: int
    pending_injects: list[dict]
    round_interrupt_count: int
    is_paused: bool

    # --- A2A (Agent-to-Agent) ---
    a2a_config: dict  # A2A agent configuration (url, role, enabled, etc.)

    # --- Extension / Extra Rounds ---
    enable_extra_rounds: bool = False  # User opted in for extra rounds
    extension_granted: bool | None = None  # None=not yet decided, True=granted, False=denied

    # --- Tone Profiles (Phase: ToneProfileNode) ---
    tone_profiles: dict[str, Any]  # node_id → ToneProfile dict
