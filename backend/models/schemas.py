"""Pydantic models for API request/response and internal state transfer."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DebateStatus(StrEnum):
    """DebateStatus class."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(StrEnum):
    """Deprecated: Hardcoded agent roles. Use RoleType.id instead.

    Kept for backward compatibility with existing API clients.
    New clients should pass role as a string referencing a RoleType.id.
    """

    STRATEGIST = "strategist"
    CRITIC = "critic"
    OPTIMIZER = "optimizer"
    MODERATOR = "moderator"


class SearchMode(StrEnum):
    """Web search mode for a debate."""

    OFF = "off"
    OPTIONAL = "optional"
    REQUIRED = "required"


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------


class AgentConfig(BaseModel):
    """Configuration for a single debate agent.

    The ``role`` field accepts any string (typically a RoleType.id).
    For backward compatibility, legacy AgentRole enum values are also accepted.
    """

    role: str  # RoleType.id (e.g. "strategist", "critic", "mediator", etc.)
    llm_profile: str = "default"
    temperature: float = 0.7


class AgentOutput(BaseModel):
    """Output produced by one agent in one round."""

    role: str  # RoleType.id
    content: str
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CaseInput(BaseModel):
    """The case or topic to debate."""

    text: str = Field(..., min_length=1, max_length=50_000, description="Case description")
    project_id: str | None = None


class DebateRequest(BaseModel):
    """POST /api/v1/debate request body."""

    case: CaseInput
    agent_profile: list[AgentConfig] = Field(
        default_factory=lambda: [
            AgentConfig(role=AgentRole.STRATEGIST),
            AgentConfig(role=AgentRole.CRITIC),
            AgentConfig(role=AgentRole.OPTIMIZER),
            AgentConfig(role=AgentRole.MODERATOR),
        ],
        description=(
            "List of agent configurations. Each role is a RoleType.id. "
            "Default: legacy 4-role setup (strategist, critic, optimizer, moderator). "
            "For custom roles, provide explicit list with bundle_id references."
        ),
    )
    bundle_ids: list[str] = Field(
        default_factory=list,
        description="AgentBundle IDs to use for debate agents. If provided, overrides agent_profile defaults.",
    )
    max_rounds: int = Field(default=3, ge=1, le=20)
    consensus_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    enable_fact_check: bool = False
    enable_memory: bool = False

    # --- Web search (Sprint 5) ---
    search_mode: SearchMode = Field(
        default=SearchMode.OFF,
        description="Web search mode: 'off', 'optional', or 'required'",
    )

    # --- Profile configuration (Sprint 3) ---
    llm_profile_id: str = Field(default="", description="LLM profile to use (empty = service default)")
    prompt_variant: str = Field(default="default", description="Prompt variant ID")
    agent_persona_ids: dict[str, str] = Field(
        default_factory=dict,
        description=("Mapping of agent role to persona ID (e.g. {'strategist': 'strategist-default'})"),
    )

    # --- Language (Sprint 4) ---
    language: str | None = Field(
        default=None,
        description=(
            "Language for debate prompts. Uses the user's configured UI language "
            "if not specified. Supported: de, en, fr, es, it, pt, ru, zh, ja, ko, sv, el, ar, he"
        ),
    )

    # --- RAG / DMS (Phase 2) ---
    document_ids: list[str] = Field(
        default_factory=list,
        description="List of DMS document IDs to include as RAG context for this debate",
    )
    rag_auto_retrieve: bool = Field(
        default=False,
        description="If true, automatically retrieve relevant document chunks based on the case text",
    )

    include_debate_results: bool = Field(
        default=False,
        description="If true, include results from previous completed debates as RAG context",
    )

    # --- Extension / Extra Rounds (Sprint 9) ---
    enable_extra_rounds: bool = Field(
        default=False,
        description="If true, the moderator can request additional rounds when consensus is not reached",
    )

    # --- A2A Integration ---
    a2a_agents: list[A2AAgentConfig] = Field(
        default_factory=list,
        description="External A2A agents to include as debate participants",
    )


class A2AAgentConfig(BaseModel):
    """Configuration for an external A2A agent participating in the debate."""

    url: str = Field(description="A2A agent URL")
    role: str = Field(
        default="a2a_agent",
        description="Role name for the A2A agent in the debate",
    )
    position: str = Field(
        default="after_all",
        description=("Where to insert the A2A agent: 'after_all', 'after:critic', 'before:moderator', etc."),
    )


class DebateResponse(BaseModel):
    """POST /api/v1/debate response."""

    debate_id: str
    status: DebateStatus = DebateStatus.PENDING
    title: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RoundData(BaseModel):
    """Data for a single debate round."""

    round: int
    consensus: float = 0.0
    agent_outputs: list[AgentOutput] = Field(default_factory=list)


class DebateStatusResponse(BaseModel):
    """GET /api/v1/debate/{id} response."""

    debate_id: str
    status: DebateStatus
    title: str = ""
    current_round: int = 0
    max_rounds: int = 3
    consensus_score: float | None = None
    rounds: list[RoundData] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    # --- Extended metadata ---
    case_text: str = ""
    language: str | None = None
    prompt_language: str | None = Field(
        default=None,
        description="Actual language of loaded prompts (may differ from requested language if fallback used)",
    )
    llm_profile_id: str = ""
    llm_profile_model: str = ""
    anomalies: list[str] = Field(default_factory=list)
    # --- Project context ---
    project_id: str = ""
    project_name: str = ""
    parent_debate_id: str | None = None
    forks_count: int = 0
    # --- MVP debate fields ---
    session_id: str | None = Field(
        default=None,
        description="Workflow session ID (wf-… format). Set for MVP debates.",
    )
    is_mvp: bool = False
    # --- RAG / DMS ---
    rag_enabled: bool = False
    rag_document_count: int = 0
    rag_context_preview: str = ""
    # --- HITL (Human-in-the-Loop) ---
    hitl_enabled: bool = False
    hitl_mode: str = "off"
    is_paused: bool = False
    has_active_interrupt: bool = False
    total_interactions: int = 0


class TagInfo(BaseModel):
    """Compact tag representation for embedding in list responses."""

    id: str
    name: str
    color: str = "#6366f1"


class DebateListItem(BaseModel):
    """GET /api/v1/debate list item — lightweight summary for history."""

    debate_id: str
    status: DebateStatus
    title: str = ""
    current_round: int = 0
    max_rounds: int = 3
    consensus_score: float | None = None
    case_preview: str = ""
    case_text: str = ""
    language: str = "de"
    created_at: datetime
    updated_at: datetime
    project_id: str = ""
    project_name: str = ""
    parent_debate_id: str | None = None
    forks_count: int = 0
    is_mvp: bool = False
    # --- Tenant/case context (new multi-tenant structure) ---
    tenant_id: str = ""
    tenant_name: str = ""
    case_id: str = ""
    case_title: str = ""
    tags: list[TagInfo] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """GET /health response."""

    status: str = "ok"
    version: str


class ErrorResponse(BaseModel):
    """Standard error envelope."""

    detail: str


# ---------------------------------------------------------------------------
# Audit event model (for persistence layer)
# ---------------------------------------------------------------------------


class AuditEvent(BaseModel):
    """Immutable audit trail entry."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    debate_id: str
    round: int
    agent: AgentRole
    action: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    input_hash: str = ""
    output_hash: str = ""
    llm_model: str = "dummy"
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# Out-of-Band (OOB) Input
# ---------------------------------------------------------------------------


class OOBTargetType(StrEnum):
    """Target type for OOB input routing."""

    SPECIFIC_AGENT = "specific_agent"
    NEXT_AGENT = "next_agent"
    ALL_FUTURE = "all_future"
    CURRENT_ACTIVE = "current_active"


class OOBTarget(BaseModel):
    """Routing target for an OOB input."""

    type: OOBTargetType
    agent_role: str | None = None
    round: int | None = None
    current_agent_role: str | None = None
    from_round: int | None = None


class OOBInputBody(BaseModel):
    """POST /api/v1/debate/{id}/oob request body."""

    content: str = Field(..., min_length=1, max_length=5000, description="Additional context")
    target: OOBTarget
    urgency: str = "append"  # 'append' | 'inject_now' | 'override_context'


class OOBInputResponse(BaseModel):
    """Response after submitting an OOB input."""

    oob_id: str
    status: str = "pending"
    target_resolved: str = ""


# ---------------------------------------------------------------------------
# Workflow Audit Log (Phase 7)
# ---------------------------------------------------------------------------


class AuditEventType(StrEnum):
    """Event types recorded in the workflow audit log."""

    WORKFLOW_STARTED = "workflow_started"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"
    WORKFLOW_PAUSED = "workflow_paused"
    WORKFLOW_RESUMED = "workflow_resumed"
    WORKFLOW_CANCELLED = "workflow_cancelled"
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    INTERJECTION_SUBMITTED = "interjection_submitted"
    INTERJECTION_CONSUMED = "interjection_consumed"
    SESSION_LOCKED = "session_locked"
    SESSION_ARCHIVED = "session_archived"
    # Transactional Drafting events
    BUILDER_ITERATION = "builder_iteration"
    PRAGMATIST_EVALUATION = "pragmatist_evaluation"


class AuditLogEntry(BaseModel):
    """A single entry in the workflow audit log.

    Maps to the ``audit_log`` table created in migration v6.
    """

    id: int | None = None
    session_id: str
    workflow_id: str
    workflow_version: int = 1
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str
    node_id: str | None = None
    actor: str = "system"
    input_hash: str = ""
    output_hash: str = ""
    llm_profile_id: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0


class AuditLogQuery(BaseModel):
    """Query parameters for filtering audit log entries."""

    session_id: str | None = None
    workflow_id: str | None = None
    event_type: str | None = None
    date_from: str | None = Field(None, description="ISO-8601 lower bound (inclusive)")
    date_to: str | None = Field(None, description="ISO-8601 upper bound (inclusive)")
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ReportJobStatus(BaseModel):
    """Status of an asynchronous report generation job.

    Maps to the ``report_jobs`` table created in migration v6.
    """

    job_id: str
    session_id: str
    format: str
    status: str = "pending"
    file_path: str | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Follow-up / Fork models (Plan 19)
# ---------------------------------------------------------------------------


class DebateContinueBody(BaseModel):
    """POST /api/v1/debate/{id}/continue request body."""

    new_title: str | None = None
    focus_topic: str | None = None


class ForkFromConsensusBody(BaseModel):
    """POST /api/v1/debate/{id}/fork-from-consensus request body."""

    new_title: str
    new_topic: str
    max_rounds: int = Field(default=3, ge=1, le=20)
    consensus_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    inherit_personas: bool = True
    inherit_llm_profile: bool = True


class ForkDebateBody(BaseModel):
    """POST /api/v1/debate/{id}/fork request body."""

    new_title: str
    fork_from_round: int | None = None
    fork_reason: str | None = None  # consensus_breakdown | new_perspective | branching
    modified_personas: dict[str, str] | None = None  # role -> persona_id
    modified_prompt_variant: str | None = None


class DebateForkInfo(BaseModel):
    """Fork metadata embedded in the debate JSON."""

    parent_debate_id: str
    fork_round: int | None = None
    fork_reason: str | None = None


# ---------------------------------------------------------------------------
# Case-Space Workspace (Phase 1 of plans/2026-06-14_case-space-workspace.md)
# ---------------------------------------------------------------------------


class WorkspaceRecentEvent(BaseModel):
    """A condensed activity event for the Workspace's Recent Activity card.

    Derived from the audit trail.  Only the fields relevant to a one-line
    workspace summary are exposed — full audit events remain available via
    the dedicated audit endpoint.
    """

    id: str
    event_type: str
    actor: str | None = None
    subject: str | None = None  # e.g. debate title, document name
    case_id: str | None = None
    created_at: datetime


class WorkspaceSuggestedNextStep(BaseModel):
    """A contextual hint surfaced on the Workspace's Suggested Next Steps card.

    Example kinds:
    - "unlinked_documents"  → user has docs in the DMS without a case
    - "untagged_debates"    → at least one debate has zero tags
    - "inactive_audit"      → no audit event for the case in N days
    """

    kind: str
    severity: str  # "info" | "warning"
    message: str
    action_label: str
    action_target: str  # route or feature id to navigate to


class WorkspaceSummary(BaseModel):
    """Aggregated, case-scoped summary payload served by GET /api/workspace/summary.

    The endpoint returns this in a single call to avoid N+1 round-trips from
    the frontend when the workspace view mounts.
    """

    case_id: str
    tenant_id: str
    title: str
    description: str | None = None
    status: str
    tags: list[str] = Field(default_factory=list)
    members: list[str] = Field(default_factory=list)

    debate_count: int = 0
    document_count: int = 0

    recent_events: list[WorkspaceRecentEvent] = Field(default_factory=list)
    suggested_next_steps: list[WorkspaceSuggestedNextStep] = Field(default_factory=list)

    generated_at: datetime


class CaseSearchHit(BaseModel):
    """Single result for GET /api/cases/search (typeahead for the Case selector)."""

    case_id: str
    tenant_id: str
    title: str
    status: str
    tags: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Case-Space Inbox (Phase 2 of plans/2026-06-14_case-space-workspace.md)
# ---------------------------------------------------------------------------


class InboxDebateItem(BaseModel):
    """A debate surfaced on the Inbox because of one of the kinds below.

    The "kind" determines which action buttons the UI renders:

    - ``recently_completed``  → "Open", "Archive", "View report"
    - ``untagged``            → "Add tags", "Open", "Open in Case"
    - ``stale_running``       → "Open", "Force reset", "Cancel"
    """

    id: str
    kind: str
    tenant_id: str
    case_id: str
    title: str
    status: str
    tags: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    age_hours: float | None = None
    message: str


class InboxSummary(BaseModel):
    """Aggregated, tenant-scoped Inbox payload.

    The endpoint returns this in a single call to avoid N+1 round-trips
    from the frontend when the Inbox view mounts.
    """

    tenant_id: str
    items: list[InboxDebateItem] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    is_all_clear: bool = True
    generated_at: datetime


class InboxBulkMoveBody(BaseModel):
    """Request body for POST /api/v1/inbox/bulk-move.

    Moves the listed debates to a new case.  All ids must belong to
    the same tenant; the target case must also belong to the same
    tenant (enforced server-side).
    """

    debate_ids: list[str] = Field(..., min_length=1, max_length=200)
    target_case_id: str = Field(..., min_length=1)


class InboxBulkTagBody(BaseModel):
    """Request body for POST /api/v1/inbox/bulk-tag.

    Adds the listed tags to each debate.  An empty ``tag_ids`` list is
    treated as a no-op (not a 400) so the UI's "remove all tags"
    button can submit cleanly without a special endpoint.
    """

    debate_ids: list[str] = Field(..., min_length=1, max_length=200)
    tag_ids: list[str] = Field(default_factory=list, max_length=50)


class InboxBulkArchiveBody(BaseModel):
    """Request body for POST /api/v1/inbox/bulk-archive.

    Marks the listed debates as archived.  Implementation may either
    delete the debates or set an ``archived_at`` flag depending on the
    store's policy; in Phase 2 we delete (the legacy archive view
    already mirrors this behaviour).
    """

    debate_ids: list[str] = Field(..., min_length=1, max_length=200)


class InboxBulkResult(BaseModel):
    """Response body for any /api/v1/inbox/bulk-* endpoint.

    ``succeeded`` and ``failed`` are mutually exclusive lists.  An item
    is in ``failed`` when the store rejected it (e.g. wrong tenant,
    not found) — the response is 200, not 4xx, so the UI can show a
    partial-success message.
    """

    succeeded: list[str] = Field(default_factory=list)
    failed: list[dict] = Field(default_factory=list)  # [{"id": str, "reason": str}]


# ---------------------------------------------------------------------------
# Case-Space Onboarding (Phase 3 of plans/2026-06-14_case-space-workspace.md)
# ---------------------------------------------------------------------------


class OnboardingState(BaseModel):
    """The three booleans the Welcome-Card consumes.

    - ``has_cases``    → at least one Case in the tenant
    - ``has_documents`` → (reserved) at least one document in the
                          tenant; in the current architecture
                          documents are scoped per project, so
                          this stays False (the welcome card uses
                          it to decide whether to show the upload
                          hint, but the upload flow itself works
                          regardless)
    - ``has_debates``   → at least one Debate in any case
    """

    tenant_id: str
    has_cases: bool
    has_documents: bool
    has_debates: bool


# ---------------------------------------------------------------------------
# Case-Space Knowledge Graph (Phase 4 of plans/2026-06-14_case-space-workspace.md)
# ---------------------------------------------------------------------------


class GraphNode(BaseModel):
    """A single node in the knowledge graph.

    The ``id`` is namespaced by type (``case:<id>``, ``debate:<id>``,
    ``document:<id>``, ``tag:<name>``) so two entities of different
    types but the same raw id never collide.
    """

    id: str
    type: str
    label: str
    meta: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """An edge between two nodes.  ``weight`` is unused in Phase 4
    but reserved for Phase 5+ derived edges (e.g. embedding
    similarity) where multiple edges of the same type can exist
    between the same pair of nodes.
    """

    src: str
    tgt: str
    type: str
    weight: float = 1.0


class GraphPayload(BaseModel):
    """The envelope returned by every /api/v1/graph/* endpoint.

    ``truncated`` + ``total_count`` + ``sampled_count`` are
    only meaningful for the global endpoint; the local endpoint
    always returns the full 1-hop subgraph.
    """

    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    truncated: bool = False
    total_count: int = 0
    sampled_count: int = 0


class EdgeDetail(BaseModel):
    """Response for GET /api/v1/graph/edges?src=…&tgt=…"""

    src: str
    tgt: str
    type: str
    weight: float = 1.0
    evidence: list[str] = Field(default_factory=list)
