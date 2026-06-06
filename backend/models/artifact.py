"""DebateArtifact — immutable output of a completed workflow execution.

This is the sole interface between execution (LangGraph) and rendering
(Output Composer / plugins).  All inner transcript models are standalone
Pydantic classes, not generic dictionaries.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Inner Transcript Models
# ---------------------------------------------------------------------------


class Turn(BaseModel):
    """A single agent turn in the debate transcript."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    round: int
    node_id: str
    agent_name: str
    role_type: str
    role_definition_id: str = ""
    llm_profile_id: str = ""
    llm_profile_name: str = ""
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    latency_ms: int = 0
    token_usage: dict[str, int] = Field(default_factory=dict)
    # Expected keys: "prompt", "completion", "total"
    metadata: dict = Field(
        default_factory=dict,
        description="Arbitrary metadata for this turn (e.g. provenance chain for transactional drafting)",
    )


class Injection(BaseModel):
    """A user or system injection into the debate."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: Literal["user", "system"] = "user"
    target_node_id: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    injected_at_round: int = 0


class UserQuery(BaseModel):
    """A user query submitted during the debate."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    response_turn_id: str | None = None


class MinorityVote(BaseModel):
    """A dissenting opinion from an agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str
    dissent_content: str
    target_turn_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Top-Level Artifact
# ---------------------------------------------------------------------------


class DebateArtifact(BaseModel):
    """Immutable output of a completed workflow execution.

    This is the sole interface between execution (LangGraph) and
    rendering (Output Composer / plugins).  Plugins consume **only**
    this artifact — never the raw session state or snapshot data.
    """

    session_id: str
    workflow_id: str
    workflow_version: int = 1
    workflow_name: str = ""
    title: str = ""
    topic: str = ""
    tone_profile_snapshot: dict = Field(default_factory=dict)

    transcript: list[Turn] = Field(default_factory=list)
    interjections: list[Injection] = Field(default_factory=list)
    user_queries: list[UserQuery] = Field(default_factory=list)
    minority_votes: list[MinorityVote] = Field(default_factory=list)

    consensus_result: dict | None = None
    final_assessment: str | None = Field(
        default=None,
        description="Final assessment text from the moderator (e.g. '85% verwendbar')",
    )
    usability_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Overall usability score from pragmatist reality_score",
    )
    remaining_blockers: list[str] = Field(
        default_factory=list,
        description="Blocking concerns that still need resolution after the final round",
    )

    # --- Transactional Drafting scores ---
    constructivity_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Final constructivity score after all Builder loops (0.0–1.0)",
    )
    draft_versions: int = Field(
        default=0,
        ge=0,
        description="Number of Builder iteration loops executed",
    )
    critic_item_count: int = Field(
        default=0,
        ge=0,
        description="Total number of CriticItems produced across all rounds",
    )
    build_response_count: int = Field(
        default=0,
        ge=0,
        description="Total number of BuildResponses produced across all rounds",
    )
    pragmatist_reality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Final pragmatist reality_score (aggregate feasibility)",
    )

    metadata: dict = Field(default_factory=dict)
    # metadata keys: token_usage, latencies, timestamps (start/end),
    #                agents (list of {name, blueprint_id, role_type, llm_profile_id})

    def artifact_hash(self) -> str:
        """Return a deterministic SHA-256 hex digest of this artifact."""
        import hashlib

        payload = self.model_dump_json()
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
