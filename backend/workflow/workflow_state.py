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


def _merge_drafts(a: str, b: str) -> str:
    """Merge concurrent ``current_draft`` writes from fan-out agents.

    Each fan-out agent reads the same base and appends its section.
    Both ``a`` and ``b`` share a common prefix (the base that existed
    before the fan-out step).  We find that prefix and concatenate
    only the unique suffixes so no agent output is lost.

    Example with base = "context" and two agents appending:
        a = "context\\n\\n[ANALYST Round 1]\\nAnalysis..."
        b = "context\\n\\n[CREATIVE Round 1]\\nIdeas..."
        → "context\\n\\n[ANALYST Round 1]\\nAnalysis...\\n\\n[CREATIVE Round 1]\\nIdeas..."
    """
    if not a:
        return b
    if not b:
        return a
    # Find the longest common prefix
    min_len = min(len(a), len(b))
    lo, hi = 0, min_len
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    # lo = length of longest common prefix
    # If one string is a prefix of the other, return the longer one
    if lo >= len(a):
        return b
    if lo >= len(b):
        return a
    # Concatenate: common prefix + suffix_a + suffix_b
    # Snap to the last newline boundary within the common prefix to
    # avoid splitting mid-word when the prefix ends mid-section-header.
    return a + b[lo:]


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
    current_draft: Annotated[str, _merge_drafts]

    # --- Interjection ---
    # NOTE (2.2): last-write-wins semantics — no operator.add reducer.
    # This is intentional: the interjection_node clears the queue with
    # ``interjection_queue: []`` and external submissions go through
    # ``interjection_service``, not state mutation.  Safe for linear
    # graphs; if fan-out templates ever append to this field, switch
    # to ``Annotated[list[dict], operator.add]``.
    interjection_queue: list[dict]
    consumed_interjections: Annotated[list[str], operator.add]

    # --- Output ---
    final_consensus: float
    output: str
    status: str  # 'running' | 'paused' | 'completed' | 'failed'

    # --- Tone Profiles ---
    tone_profiles: dict[str, Any]  # node_id → ToneProfile dict

    # --- Control ---
    # Metadata flag for API/status queries.  Does NOT gate graph
    # execution — the actual pause mechanism is consume_blocking()
    # inside the interjection_node (3.1 clarification).
    is_paused: bool
    pause_event: Any  # asyncio.Event for pause/resume

    # --- Extension support ---
    enable_extra_rounds: bool  # Allow up to max_rounds + 2 when True
    extension_granted: bool | None  # None=pending, True/False=user decision

    # --- Moderator assessment (2.1 — previously undeclared) ---
    final_assessment: str  # Moderator's extracted text summary
    usability_score: float  # Pragmatist's reality_score or consensus fallback
    remaining_blockers: list[str]  # Blocking concerns from pragmatist evaluation

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

    # --- Workflow versioning ---
    workflow_version: int  # Schema version for audit/snapshot compatibility
