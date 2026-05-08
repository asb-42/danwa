"""Blueprint Canvas — Workflow definition models.

Defines ``WorkflowDefinition``, ``ConditionalEdge``, and ``InterjectionPoint``
for the workflow builder mode of the Blueprint Canvas.

These models reference AgentBlueprints from the catalog by ID — they do NOT
duplicate blueprint data.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


class WorkflowDefinition(BaseModel):
    """Defines a complete debate workflow.

    References AgentBlueprints from the catalog by ID.
    Does NOT duplicate blueprint data.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""

    # Layout reference
    canvas_layout_id: str | None = None  # References CanvasLayout.id

    # Execution order: ordered list of node IDs
    execution_order: list[str] = Field(default_factory=list)

    # Conditional edges (branching logic)
    conditional_edges: list[ConditionalEdge] = Field(default_factory=list)

    # Interjection points (external input nodes)
    interjection_points: list[InterjectionPoint] = Field(default_factory=list)

    # Referenced blueprints (node_id → blueprint_id mapping)
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
