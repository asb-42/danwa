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
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentRole(StrEnum):
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
    """Configuration for a single debate agent."""

    role: AgentRole
    llm_profile: str = "default"
    temperature: float = 0.7


class AgentOutput(BaseModel):
    """Output produced by one agent in one round."""

    role: AgentRole
    content: str
    tokens_used: int = 0


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CaseInput(BaseModel):
    """The case or topic to debate."""

    text: str = Field(..., min_length=1, max_length=10_000, description="Case description")
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
        ]
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
    llm_profile_id: str = Field(default="openrouter-claude", description="LLM profile to use")
    prompt_variant: str = Field(default="default", description="Prompt variant ID")
    agent_persona_ids: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Mapping of agent role to persona ID (e.g. {'strategist': 'strategist-default'})"
        ),
    )

    # --- Language (Sprint 4) ---
    language: str = Field(
        default="de",
        description="Language for debate prompts: 'de' (German) or 'en' (English)",
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
        description=(
            "Where to insert the A2A agent: 'after_all', 'after:critic', "
            "'before:moderator', etc."
        ),
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
    language: str = "de"
    llm_profile_id: str = ""
    llm_profile_model: str = ""
    anomalies: list[str] = Field(default_factory=list)
    # --- Project context ---
    project_id: str = ""
    project_name: str = ""
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
    date_from: str | None = Field(
        None, description="ISO-8601 lower bound (inclusive)"
    )
    date_to: str | None = Field(
        None, description="ISO-8601 upper bound (inclusive)"
    )
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
