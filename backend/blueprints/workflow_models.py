"""Blueprint Canvas — Workflow definition models.

Defines ``WorkflowDefinition``, ``WorkflowNode``, ``WorkflowEdge``,
``TerminationCondition``, ``ConditionalEdge``, ``InterjectionPoint``,
and ``WorkflowTemplate`` for the workflow builder mode of the Blueprint Canvas.

These models reference AgentBlueprints from the catalog by ID — they do NOT
duplicate blueprint data.
"""

from __future__ import annotations

import json
import re
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
    "wf-fact-checker",
    "wf-optimizer",
    "wf-moderator",
    "wf-analyst",
    "wf-creative",
    "wf-socratic-questioner",
    "wf-expert-reviewer",
    "wf-steel-manner",
    "wf-devils-advocate",
    "wf-troll",
    "wf-mediator",
    "wf-ethicist",
    "wf-synthesizer",
    "wf-user-injection",
    "wf-gate",
    "wf-tone-profile",
    "wf-agent",  # Generic agent node referencing an AgentBundle
    "wf-phase",  # Phase container node for multi-phase debates
    "wf-builder",
    "wf-pragmatist",
    "wf-angels-advocate",
]

#: Node types that require an agent_blueprint_id or bundle_id reference.
AGENT_NODE_TYPES: list[str] = [
    "wf-strategist",
    "wf-critic",
    "wf-fact-checker",
    "wf-optimizer",
    "wf-moderator",
    "wf-analyst",
    "wf-creative",
    "wf-socratic-questioner",
    "wf-expert-reviewer",
    "wf-steel-manner",
    "wf-devils-advocate",
    "wf-troll",
    "wf-mediator",
    "wf-ethicist",
    "wf-synthesizer",
    "wf-agent",
    "wf-builder",
    "wf-pragmatist",
    "wf-angels-advocate",
]


class WorkflowNode(BaseModel):
    """A single node in a workflow graph.

    Each node has a type that determines its behavior during execution.
    Agent-type nodes (strategist, critic, optimizer, moderator) must
    reference an AgentBlueprint via ``agent_blueprint_id``.
    The generic ``wf-agent`` type references an ``AgentBundle`` via
    ``bundle_id`` instead.
    Tone-profile nodes reference a ToneProfile from the catalog or
    define an inline profile.
    """

    id: str = Field(..., min_length=1, max_length=100)
    type: Literal[
        "wf-input",
        "wf-initialize",
        "wf-strategist",
        "wf-critic",
        "wf-fact-checker",
        "wf-optimizer",
        "wf-moderator",
        "wf-analyst",
        "wf-creative",
        "wf-socratic-questioner",
        "wf-expert-reviewer",
        "wf-steel-manner",
        "wf-devils-advocate",
        "wf-troll",
        "wf-mediator",
        "wf-ethicist",
        "wf-synthesizer",
        "wf-user-injection",
        "wf-gate",
        "wf-tone-profile",
        "wf-agent",
        "wf-phase",
        "wf-builder",
        "wf-pragmatist",
        "wf-angels-advocate",
    ]
    label: str = ""
    agent_blueprint_id: str | None = None  # Required for legacy agent node types
    bundle_id: str | None = None  # Required for wf-agent type
    parent_id: str | None = None  # Parent phase node ID (for phase container membership)
    config: dict[str, Any] = Field(default_factory=dict)
    position: dict[str, float] = Field(default_factory=dict)  # {x, y} for canvas

    @model_validator(mode="after")
    def validate_agent_reference(self) -> WorkflowNode:
        """Agent-type nodes must have an agent_blueprint_id or bundle_id."""
        if self.type in AGENT_NODE_TYPES:
            if self.type == "wf-agent":
                if not self.bundle_id and not self.agent_blueprint_id:
                    raise ValueError(f"Node type '{self.type}' requires a 'bundle_id' or 'agent_blueprint_id'")
            else:
                if not self.agent_blueprint_id:
                    raise ValueError(f"Node type '{self.type}' requires an 'agent_blueprint_id'")
        return self

    @model_validator(mode="after")
    def validate_tone_profile_config(self) -> WorkflowNode:
        """Tone-profile nodes must have exactly one of tone_profile_id or inline_profile."""
        if self.type == "wf-tone-profile":
            has_catalog = bool(self.config.get("tone_profile_id"))
            has_inline = "inline_profile" in self.config and self.config["inline_profile"] is not None
            if not has_catalog and not has_inline:
                raise ValueError("Tone-profile node requires either 'tone_profile_id' or 'inline_profile' in config")
            if has_catalog and has_inline:
                raise ValueError("Tone-profile node must have exactly one of 'tone_profile_id' or 'inline_profile', not both")
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
    "injects_config",
    "builds_upon",
    "validates",
    "decision",
]

#: Agent node types that can receive injects_config edges.
INJECTABLE_AGENT_NODE_TYPES: list[str] = [
    "wf-strategist",
    "wf-critic",
    "wf-fact-checker",
    "wf-optimizer",
    "wf-moderator",
    "wf-analyst",
    "wf-creative",
    "wf-socratic-questioner",
    "wf-expert-reviewer",
    "wf-steel-manner",
    "wf-devils-advocate",
    "wf-troll",
    "wf-mediator",
    "wf-ethicist",
    "wf-synthesizer",
    "wf-agent",
    "wf-builder",
    "wf-pragmatist",
    "wf-angels-advocate",
    # Note: wf-input, wf-gate, wf-phase, wf-user-injection, wf-tone-profile cannot receive injects_config
]


class WorkflowEdge(BaseModel):
    """An edge connecting two workflow nodes.

    Edge types:
    - ``sequential``: unconditional forward connection
    - ``conditional``: branching based on a condition expression
    - ``interjection``: connects to an interjection point
    - ``feedback``: loop-back edge (e.g. moderator → strategist for another round)
    - ``injects_config``: config injection from tone_profile node to agent node
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str  # source node ID
    target: str  # target node ID
    type: Literal["sequential", "conditional", "interjection", "feedback", "injects_config", "builds_upon", "validates", "decision"] = "sequential"
    condition: str | None = None  # Required for conditional edges
    label: str = ""

    @model_validator(mode="after")
    def validate_condition(self) -> WorkflowEdge:
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


class PhaseConfig(BaseModel):
    """Configuration for a single debate phase.

    Maps a ``wf-phase`` node ID to its runtime configuration:
    phase name, description, assigned roles, max rounds, and header color.
    """

    phase_node_id: str  # References WorkflowNode.id (a wf-phase node)
    name: str = "Phase"
    description: str = ""
    roles: list[str] = Field(default_factory=list)  # Agent core role IDs
    max_rounds: int = Field(default=3, ge=1, le=50)
    color: str = "#6366f1"


class WorkflowDefinition(BaseModel):
    """Defines a complete debate workflow.

    References AgentBlueprints from the catalog by ID.
    Does NOT duplicate blueprint data.

    The ``nodes`` and ``edges`` fields provide the structured graph
    representation.  ``phase_configs`` maps phase node IDs to their
    runtime configuration (name, roles, max rounds).

    ``execution_order``, ``conditional_edges``, and
    ``interjection_points`` are retained for backward compatibility with
    the list-based representation.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""

    # Layout reference
    canvas_layout_id: str | None = None  # References CanvasLayout.id

    # --- Phase configuration ---
    phase_configs: dict[str, PhaseConfig] = Field(
        default_factory=dict,
        description=(
            "Phase configurations keyed by phase node ID. Each entry defines the name, assigned roles, max rounds, and color for a debate phase."
        ),
    )

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

    # Template reference (set when instantiated from a WorkflowTemplate)
    template_id: str | None = None

    # --- Input Composer (Phase H.5) ---
    input_config: dict | None = Field(
        default=None,
        description=("Input Composer configuration for this workflow. Keys: default_input_plugin, stt_profile_id, a2a_inbound_enabled"),
    )

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
                raise ValueError(f"entry_point '{v}' does not reference any node in the workflow")
        return v


# ---------------------------------------------------------------------------
# Workflow Templates
# ---------------------------------------------------------------------------


class PlaceholderType:
    """Allowed placeholder value types."""

    STRING = "string"
    BLUEPRINT_REF = "blueprint_ref"
    INTEGER = "integer"
    FLOAT = "float"


PLACEHOLDER_TYPES: list[str] = [
    PlaceholderType.STRING,
    PlaceholderType.BLUEPRINT_REF,
    PlaceholderType.INTEGER,
    PlaceholderType.FLOAT,
]


class TemplatePlaceholder(BaseModel):
    """Defines a single placeholder within a WorkflowTemplate.

    Placeholders are replaced with concrete values during instantiation.
    """

    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_]+$")
    type: Literal["string", "blueprint_ref", "integer", "float"] = "string"
    default: str | int | float | None = None
    default_role: str | None = None
    description: str = ""


class TemplateCategory:
    """Workflow template categories."""

    SYSTEM = "system"
    CUSTOM = "custom"


TEMPLATE_CATEGORIES: list[str] = [TemplateCategory.SYSTEM, TemplateCategory.CUSTOM]

#: Regex matching {{placeholder_key}} in template data strings.
_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


class WorkflowTemplate(BaseModel):
    """A reusable workflow template with placeholder substitution.

    Templates contain a ``template_data`` dictionary that mirrors the
    structure of a ``WorkflowDefinition`` (nodes, edges, entry_point,
    termination_conditions) but may contain ``{{key}}`` placeholders in
    string fields.

    During instantiation, all placeholders are replaced with concrete
    values provided by the user, and the result is validated as a
    ``WorkflowDefinition``.
    """

    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    category: Literal["system", "custom"] = TemplateCategory.CUSTOM
    tags: list[str] = Field(default_factory=list)

    # The workflow structure with {{placeholder}} strings
    template_data: dict[str, Any] = Field(default_factory=dict)

    # Placeholder definitions
    placeholders: list[TemplatePlaceholder] = Field(default_factory=list)

    # System templates cannot be edited or deleted via API
    is_system: bool = False

    # If created from an existing workflow, reference its ID
    source_workflow_id: str | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("template_data")
    @classmethod
    def validate_template_data_has_keys(cls, v: dict[str, Any]) -> dict[str, Any]:
        """template_data must contain at least 'nodes' and 'edges'."""
        if v and "nodes" not in v:
            raise ValueError("template_data must contain a 'nodes' key")
        return v

    def extract_placeholder_keys(self) -> set[str]:
        """Extract all {{key}} placeholder keys found in template_data."""
        raw = _PLACEHOLDER_RE.findall(json.dumps(self.template_data, default=str))
        return set(raw)

    def instantiate(self, values: dict[str, Any]) -> dict[str, Any]:
        """Replace all {{key}} placeholders in template_data with values.

        Returns a new dict with all placeholders resolved.
        Raises ValueError if required placeholders are missing.
        """
        # Check for missing required placeholders
        # A placeholder is optional if it has a default, default_role, or a provided value
        {p.key for p in self.placeholders}
        self.extract_placeholder_keys()
        required_keys = {p.key for p in self.placeholders if p.default is None and p.default_role is None}
        missing = required_keys - set(values.keys())
        if missing:
            raise ValueError(f"Missing placeholder values: {sorted(missing)}")

        # Merge defaults with provided values (default_role resolved by caller)
        merged: dict[str, Any] = {}
        for p in self.placeholders:
            if p.key in values:
                merged[p.key] = values[p.key]
            elif p.default is not None:
                merged[p.key] = p.default
            # default_role placeholders: caller must have resolved and added to values

        # Deep-replace placeholders in the serialized template data
        raw = json.dumps(self.template_data, default=str)
        for key, val in merged.items():
            raw = raw.replace("{{" + key + "}}", str(val))
        return json.loads(raw)
