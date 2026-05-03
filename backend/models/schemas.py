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


class DebateResponse(BaseModel):
    """POST /api/v1/debate response."""

    debate_id: str
    status: DebateStatus = DebateStatus.PENDING
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
    anomalies: list[str] = Field(default_factory=list)


class DebateListItem(BaseModel):
    """GET /api/v1/debate list item — lightweight summary for history."""

    debate_id: str
    status: DebateStatus
    current_round: int = 0
    max_rounds: int = 3
    consensus_score: float | None = None
    case_preview: str = ""
    case_text: str = ""
    language: str = "de"
    created_at: datetime
    updated_at: datetime


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
