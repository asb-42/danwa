"""Blueprint Canvas — Workflow definition models.

Defines ``WorkflowDefinition``, ``WorkflowNode``, ``WorkflowEdge``,
``TerminationCondition``, ``ConditionalEdge``, and ``InterjectionPoint``
for the workflow builder mode of the Blueprint Canvas.

These models reference AgentBlueprints from the catalog by ID — they do NOT
duplicate blueprint data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Workflow Node Types
# ---------------------------------------------------------------------------

#: All supported workflow node types.
WORKFLOW_NODE_TYPES: list[str] = [
    "wf-input",
    "wf-initialize",
    "wf-strategist",
    "wf-critic",
    "wf-optimizer",
    "wf-moderator",
    "wf-user-injection",
    "wf-gate",
]

#: Node types that require an agent_blueprint_id reference.
AGENT_NODE_TYPES: list[str] = [
    "wf-strategist",
    "wf-critic",
    "wf-optimizer",
    "wf-moderator",
]


class WorkflowNode(BaseModel):
    """A single node in a workflow graph.

    Each node has a type that determines its behavior during execution.
    Agent-type nodes (strategist, critic, optimizer, moderator) must
    reference an AgentBlueprint via ``agent_blueprint_id``.
    """

    id: str = Field(..., min_length=1, max_length=100)
    type: Literal[
        "wf-input",
        "wf-initialize",
        "wf-strategist",
        "wf-critic",
        "wf-optimizer",
        "wf-moderator",
        "wf-user-injection",
        "wf-gate",
    ]
    label: str = ""
    agent_blueprint_id: str | None = None  # Required for agent node types
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=dict)  # {x, y} for canvas

    @model_validator(mode="after")
    def validate_agent_blueprint_id(self) -> "WorkflowNode":
        """Agent-type nodes must have an agent_blueprint_id."""
        if self.type in AGENT_NODE_TYPES and not self.agent_blueprint_id:
            raise ValueError(
                f"Node type '{self.type}' requires an agent_blueprint_id"
            )
        return self


# ---------------------------------------------------------------------------
# Workflow Edge Types
# ---------------------------------------------------------------------------

#: All supported workflow edge types.
WORKFLOW_EDGE_TYPES: list[str] = [
    "sequential",
    "conditional",
    "interjection",
    "feedback",
]


class WorkflowEdge(BaseModel):
    """An edge connecting two workflow nodes.

    Edge types:
    - ``sequential``: unconditional forward connection
    - ``conditional``: branching based on a condition expression
    - ``interjection``: connects to an interjection point
    - ``feedback``: loop-back edge (e.g. moderator → strategist for another round)
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str  # source node ID
    target: str  # target node ID
    type: Literal["sequential", "conditional", "interjection", "feedback"] = "sequential"
    condition: str | None = None  # Required for conditional edges
    label: str = ""

    @model_validator(mode="after")
    def validate_condition(self) -> "WorkflowEdge":
        """Conditional edges must have a condition expression."""
        if self.type == "conditional" and not self.condition:
            raise ValueError("Conditional edges require a condition expression")
        return self


# ---------------------------------------------------------------------------
# Termination Conditions
# ---------------------------------------------------------------------------


class TerminationCondition(BaseModel):
    """A condition that determines when a workflow should stop.

    Examples:
    - ``max_rounds``: stop after N rounds
    - ``consensus_reached``: stop when consensus threshold is met
    - ``time_limit``: stop after N seconds
    """

    type: Literal["max_rounds", "consensus_reached", "time_limit", "custom"] = "max_rounds"
    value: int | float = 5  # e.g. 5 rounds, 0.9 threshold, 300 seconds
    description: str = ""


# ---------------------------------------------------------------------------
# Existing models (unchanged)
# ---------------------------------------------------------------------------


class ConditionalEdge(BaseModel):
    """An edge with a condition expression for branching logic."""

    source_node_id: str
    target_node_id: str
    condition: str  # e.g. "consensus_reached", "round >= 3", "user_approved"
    description: str = ""


class InterjectionPoint(BaseModel):
    """A node that accepts external input during workflow execution."""

    node_id: str
    input_type: Literal["user_query", "oob_input", "external_event"] = "user_query"
    description: str = ""
    blocking: bool = True  # If True, workflow pauses until input received


# ---------------------------------------------------------------------------
# Workflow Definition (extended)
# ---------------------------------------------------------------------------


class WorkflowDefinition(BaseModel):
    """Defines a complete debate workflow.

    References AgentBlueprints from the catalog by ID.
    Does NOT duplicate blueprint data.

    The ``nodes`` and ``edges`` fields provide the structured graph
    representation.  ``execution_order``, ``conditional_edges``, and
    ``interjection_points`` are retained for backward compatibility with
    the list-based representation.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""

    # Layout reference
    canvas_layout_id: str | None = None  # References CanvasLayout.id

    # --- Structured graph representation (Phase 1) ---
    nodes: list[WorkflowNode] = Field(default_factory=list)
    edges: list[WorkflowEdge] = Field(default_factory=list)
    entry_point: str | None = None  # Node ID of the entry point
    termination_conditions: list[TerminationCondition] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)
    is_locked: bool = False

    # --- Legacy list-based representation (kept for backward compat) ---
    execution_order: list[str] = Field(default_factory=list)
    conditional_edges: list[ConditionalEdge] = Field(default_factory=list)
    interjection_points: list[InterjectionPoint] = Field(default_factory=list)
    node_blueprint_map: dict[str, str] = Field(default_factory=dict)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("execution_order")
    @classmethod
    def validate_execution_order(cls, v: list[str]) -> list[str]:
        """Ensure execution_order contains no duplicate node IDs."""
        if len(v) != len(set(v)):
            raise ValueError("execution_order contains duplicate node IDs")
        return v

    @field_validator("entry_point")
    @classmethod
    def validate_entry_point(cls, v: str | None, info: Any) -> str | None:
        """If set, entry_point must reference a valid node ID in nodes."""
        if v is not None:
            nodes = info.data.get("nodes", [])
            node_ids = {n.id for n in nodes} if nodes else set()
            if node_ids and v not in node_ids:
                raise ValueError(
                    f"entry_point '{v}' does not reference any node in the workflow"
                )
        return v
