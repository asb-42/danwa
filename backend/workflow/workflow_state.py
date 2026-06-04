"""LangGraph state definition for the workflow-based execution engine.

Parallel to ``DebateState`` but tailored for graph-based workflows with
structured node types, conditional edges, feedback loops, and interjections.

Also carries transactional-drafting-specific keys (zero_draft, critic_items,
build_responses, pragmatist_output, etc.) — these are only used when the
workflow template is :attr:`WorkflowTemplate.TRANSACTIONAL_DRAFTING`.
"""

from __future__ import annotations

import operator
from enum import StrEnum
from typing import Annotated, Any, TypedDict


class WorkflowTemplate(StrEnum):
    """Identifiers for the built-in workflow templates.

    Used as values for ``WorkflowState.workflow_template`` and as
    template IDs throughout the backend.  :class:`StrEnum` keeps the
    values identical to the historical string literals so that state
    dicts serialised before the enum existed round-trip cleanly.
    """

    DEBATE = "debate"
    ACADEMIC_DEBATE = "academic_debate"
    TRANSACTIONAL_DRAFTING = "transactional_drafting"


class WorkflowNodeOutput(TypedDict):
    """Output produced by a single workflow node execution."""

    node_id: str
    node_type: str
    role: str
    content: str
    tokens_used: int
    duration_ms: int
    status: str  # 'pending' | 'running' | 'completed' | 'failed' | 'skipped'


class WorkflowState(TypedDict, total=False):
    """Shared state passed through every LangGraph workflow node.

    Fields using ``Annotated[..., operator.add]`` are list accumulators —
    each node *appends* to them rather than replacing.
    """

    # --- Input (set at creation) ---
    workflow_id: str
    session_id: str
    project_id: str
    context: str  # User case text / input
    language: str
    search_mode: str  # 'off', 'optional', 'required'
    rag_context: str  # Document analysis + RAG document excerpts

    # --- Workflow structure (resolved at compile time) ---
    node_sequence: list[str]  # Ordered node IDs from topological sort
    node_configs: dict[str, dict]  # node_id → resolved config (blueprint, llm, role)
    edge_map: dict[str, list[dict]]  # node_id → list of outgoing edge dicts
    termination_conditions: list[dict]

    # --- Runtime ---
    current_node_id: str
    current_round: int
    max_rounds: int
    threshold: float

    # --- Accumulators ---
    node_outputs: Annotated[list[WorkflowNodeOutput], operator.add]
    messages: Annotated[list[dict], operator.add]  # Full message log
    current_draft: str

    # --- Interjection ---
    interjection_queue: list[dict]  # Pending interjections
    consumed_interjections: Annotated[list[str], operator.add]

    # --- Output ---
    final_consensus: float
    output: str
    status: str  # 'running' | 'paused' | 'completed' | 'failed'

    # --- Tone Profiles ---
    tone_profiles: dict[str, Any]  # node_id → ToneProfile dict

    # --- Control ---
    is_paused: bool
    pause_event: Any  # asyncio.Event for pause/resume

    # --- Transactional Drafting ---
    zero_draft: str | None  # Originaler Entwurf vom Strategist
    critic_items: Annotated[list[dict], operator.add]  # list[CriticItem]
    build_responses: Annotated[list[dict], operator.add]  # list[BuildResponse]
    pragmatist_output: dict | None  # PragmatistOutput serialised
    draft_version: int  # Inkrementiert bei jedem Return-to-Builder
    constructivity_score: float
    consensus_result: dict | None  # {"verdict": "approved"|"revision_required", ...}
    latest_draft: str | None  # Most recent Builder output (global_revision or raw); distinct from
    # zero_draft (Strategist's original) and from current_draft (the running debate log).

    # --- Workflow template identifier ---
    workflow_template: str  # WorkflowTemplate enum value
