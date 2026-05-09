"""LangGraph state definition for the workflow-based execution engine.

Parallel to ``DebateState`` but tailored for graph-based workflows with
structured node types, conditional edges, feedback loops, and interjections.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


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
