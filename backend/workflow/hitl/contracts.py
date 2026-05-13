"""HITL Pydantic contracts — request/response models for HITL API endpoints.

These models define the API surface for bidirectional interactions:
- InjectRequest / InjectResponse: user → agent context injection
- RespondRequest / RespondResponse: user → agent query response
- PauseRequest / PauseResponse: pause/resume debate
- HITLStatusResponse: current HITL state for a debate
- InteractionResponse: single interaction record
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InteractionType(StrEnum):
    """Type of HITL interaction."""

    INJECT = "inject"
    QUERY = "query"
    RESPONSE = "response"


class InteractionDirection(StrEnum):
    """Direction of HITL interaction."""

    USER_TO_AGENT = "user_to_agent"
    AGENT_TO_USER = "agent_to_user"


class InteractionStatus(StrEnum):
    """Lifecycle status of an interaction."""

    PENDING = "pending"
    DELIVERED = "delivered"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class HITLMode(StrEnum):
    """HITL operation mode."""

    FULL = "full"  # Both inject and query
    INJECT_ONLY = "inject_only"  # Only user → agent
    QUERY_ONLY = "query_only"  # Only agent → user
    OFF = "off"  # HITL disabled


class InterruptStatus(StrEnum):
    """Status of an active interrupt."""

    WAITING = "waiting"
    ANSWERED = "answered"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ExtensionDecision(StrEnum):
    """Decision on whether to grant extra debate rounds."""

    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    TIMEOUT = "timeout"


class PauseAction(StrEnum):
    """Pause/resume action."""

    PAUSE = "pause"
    RESUME = "resume"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class InjectRequest(BaseModel):
    """POST /debate/{id}/inject — user injects context into running debate."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Context or information to inject into the debate",
    )
    target_agent: str | None = Field(
        default=None,
        description=("Target agent role (e.g. 'critic'). If None, injected to all future agents in the current and subsequent rounds."),
    )
    target_round: int | None = Field(
        default=None,
        description="Target round number. If None, applies to current and future rounds.",
    )
    priority: str = Field(
        default="normal",
        description="Injection priority: 'low', 'normal', 'high', 'urgent'",
    )


class RespondRequest(BaseModel):
    """POST /debate/{id}/respond — user responds to an agent query."""

    interrupt_id: str = Field(
        ...,
        description="ID of the interrupt (agent query) being answered",
    )
    response: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="User's response to the agent's question",
    )


class PauseRequest(BaseModel):
    """POST /debate/{id}/pause — pause or resume a running debate."""

    action: PauseAction = Field(
        ...,
        description="'pause' to pause the debate, 'resume' to continue",
    )
    reason: str = Field(
        default="",
        max_length=500,
        description="Optional reason for pausing",
    )


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class InteractionResponse(BaseModel):
    """A single interaction record returned by the API."""

    interaction_id: str
    type: InteractionType
    direction: InteractionDirection
    source: str
    target: str
    content: str
    round: int
    agent_index: int
    timestamp: str
    status: InteractionStatus
    metadata: dict = Field(default_factory=dict)


class InjectResponse(BaseModel):
    """Response after submitting an inject."""

    interaction_id: str
    status: str = "pending"
    target_resolved: str = ""
    message: str = "Context injection queued"


class RespondResponse(BaseModel):
    """Response after answering an agent query."""

    interaction_id: str
    interrupt_id: str
    status: str = "delivered"
    message: str = "Response delivered to agent"


class PauseResponse(BaseModel):
    """Response after pause/resume action."""

    debate_id: str
    paused: bool
    action: PauseAction
    message: str = ""


class InterruptInfo(BaseModel):
    """Information about an active interrupt (agent waiting for user)."""

    interrupt_id: str
    agent_role: str
    question: str
    context: str = ""
    round: int
    created_at: str
    timeout_seconds: int
    status: InterruptStatus
    elapsed_seconds: float = 0.0


class HITLStatusResponse(BaseModel):
    """GET /debate/{id}/hitl/status — current HITL state."""

    debate_id: str
    hitl_enabled: bool
    hitl_mode: HITLMode
    is_paused: bool = False
    active_interrupt: InterruptInfo | None = None
    total_interactions: int = 0
    interactions_by_type: dict[str, int] = Field(default_factory=dict)
    round_interrupt_count: int = 0
    max_interrupts_per_round: int = 3


class ExtensionRequest(BaseModel):
    """POST /debate/{id}/extension-request — moderator requests extra rounds."""

    current_consensus: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Current consensus score",
    )
    current_round: int = Field(..., ge=1, description="Current round number")
    max_rounds: int = Field(..., ge=1, description="Configured max rounds")
    threshold: float = Field(..., ge=0.0, le=1.0, description="Consensus threshold")


class ExtensionDecisionModel(BaseModel):
    """POST /debate/{id}/extension-decision — user/player decides on extension."""

    decision: ExtensionDecision = Field(
        ...,
        description="GRANTED to allow extra rounds, DENIED to end debate",
    )


class ExtensionResponse(BaseModel):
    """Response after submitting an extension decision."""

    decision: ExtensionDecision
    debate_id: str
    new_max_rounds: int
    message: str = ""


class InteractionListResponse(BaseModel):
    """GET /debate/{id}/interactions — paginated interaction history."""

    interactions: list[InteractionResponse] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 50
