"""Blueprint Canvas — Pydantic-V2 domain models.

Defines typed, validated models for the Blueprint system:
- BlueprintLLMProfile: LLM endpoint configuration (blueprint variant)
- PromptTemplate: Named prompt template with inline content
- RoleDefinition: Agent role with behavior constraints
- AgentBlueprint: Composite model tying LLM + role + prompt together
- CanvasLayout: Simplified canvas arrangement for the visual editor
- ToneProfile: Debate tone/style configuration

These models are additive — they do NOT replace the existing
``backend.core.profiles`` models.  Legacy conversion is provided via
``from_legacy()`` / ``to_legacy()`` class methods.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from backend.core.profiles import AgentPersona, LLMProfile

# ---------------------------------------------------------------------------
# 2.2 BlueprintLLMProfile
# ---------------------------------------------------------------------------


class BlueprintLLMProfile(BaseModel):
    """LLM configuration for use in Agent Blueprints.

    Extends the concept of ``backend.core.profiles.LLMProfile`` with
    blueprint-specific metadata (description, tags, timestamps).
    """

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str
    profile_type: Literal["text", "tts", "stt"] = "text"
    provider: Literal[
        "openrouter",
        "openai",
        "anthropic",
        "local",
        "ollama",
        "opencode-zen",
        "opencode-go",
        "xiaomi",
        # STT providers (Input Composer Phase D)
        "whisper-local",
        "whisper-api",
        "azure-stt",
        "google-stt",
    ]
    model: str
    api_base: str | None = None
    api_key_env: str = "OPENROUTER_API_KEY"
    max_tokens: int = 4096
    context_window: int | None = None
    temperature: float = 0.7
    timeout: int = 600
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    # Blueprint-specific
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # --- A2A Protocol (Phase 8) ---
    protocol: Literal["litellm", "a2a", "stt"] = "litellm"
    a2a_endpoint: str | None = None
    a2a_timeout: int = 120
    fallback_llm_profile_id: str | None = None
    a2a_config: dict = Field(default_factory=dict)

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        if v < 1:
            raise ValueError("max_tokens must be at least 1")
        return v

    # -- Legacy conversion ---------------------------------------------------

    @classmethod
    def from_legacy(cls, legacy: LLMProfile) -> BlueprintLLMProfile:
        """Convert from ``backend.core.profiles.LLMProfile``."""
        now = datetime.now(UTC)
        # Infer profile_type from protocol/provider
        protocol = getattr(legacy, "protocol", "litellm")
        ptype = "text"
        if protocol == "stt" or legacy.provider.value in (
            "whisper-local", "whisper-api", "azure-stt", "google-stt",
        ):
            ptype = "stt"
        return cls(
            id=legacy.id,
            name=legacy.name,
            profile_type=ptype,
            provider=legacy.provider.value,  # type: ignore[arg-type]
            model=legacy.model,
            api_base=legacy.api_base,
            api_key_env=legacy.api_key_env,
            max_tokens=legacy.max_tokens,
            context_window=legacy.context_window,
            temperature=legacy.temperature,
            timeout=legacy.timeout,
            cost_per_1k_input=legacy.cost_per_1k_input,
            cost_per_1k_output=legacy.cost_per_1k_output,
            description="",
            tags=[],
            created_at=now,
            updated_at=now,
            protocol=protocol,
            a2a_endpoint=getattr(legacy, "a2a_endpoint", None),
            a2a_timeout=getattr(legacy, "a2a_timeout", 120),
            fallback_llm_profile_id=getattr(legacy, "fallback_llm_profile_id", None),
        )

    def to_legacy(self) -> LLMProfile:
        """Convert to ``backend.core.profiles.LLMProfile`` for backward compat."""
        return LLMProfile(
            id=self.id.replace("_", "-"),  # normalize underscores → hyphens
            name=self.name,
            profile_type=self.profile_type,
            provider=self.provider,  # type: ignore[arg-type]
            model=self.model,
            api_base=self.api_base,
            api_key_env=self.api_key_env,
            max_tokens=self.max_tokens,
            context_window=self.context_window,
            temperature=self.temperature,
            timeout=self.timeout,
            cost_per_1k_input=self.cost_per_1k_input,
            cost_per_1k_output=self.cost_per_1k_output,
            protocol=self.protocol,
            a2a_endpoint=self.a2a_endpoint,
            a2a_timeout=self.a2a_timeout,
            fallback_llm_profile_id=self.fallback_llm_profile_id,
        )


# ---------------------------------------------------------------------------
# 2.3 PromptTemplate
# ---------------------------------------------------------------------------


def _compute_content_hash(content: str) -> str:
    """SHA-256[:16] of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class PromptTemplate(BaseModel):
    """A named prompt template with content and metadata.

    Replaces the file-path-only approach of
    ``backend.core.profiles.PromptVariant``.  Content is stored inline
    in the database rather than referencing files.
    """

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str
    role: str = "strategist"  # References RoleType.id (dynamic)
    content: str  # The actual prompt text (stored inline)
    language: str = "de"
    variant: str = "default"  # e.g. "default", "kantian", "steiner"
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    source_path: str | None = None  # Original file path (for traceability)
    content_hash: str = ""  # SHA-256[:16] of content for change detection
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("content")
    @classmethod
    def validate_content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Prompt content must not be empty")
        return v

    def model_post_init(self, _context: object) -> None:
        """Auto-compute content_hash if not provided."""
        if not self.content_hash:
            object.__setattr__(self, "content_hash", _compute_content_hash(self.content))


# ---------------------------------------------------------------------------
# 2.4 RoleDefinition
# ---------------------------------------------------------------------------


class RoleDefinition(BaseModel):
    """Defines an agent role with behavior constraints and prompt reference.

    Extends ``backend.core.profiles.AgentPersona`` with richer metadata
    and a decoupled prompt reference (by ID, not inline text).

    The ``role_type_id`` field references a ``RoleType.id``, allowing
    dynamic role types beyond the hardcoded strategist/critic/optimizer/moderator.
    """

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str
    role_type_id: str = "strategist"  # References RoleType.id (dynamic, not hardcoded enum)
    description: str = ""
    # Prompt reference (by ID, not inline text)
    prompt_template_id: str | None = None  # References PromptTemplate.id
    # Behavior constraints
    max_rounds: int = 5
    consensus_threshold: float = 0.9
    # Metadata
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("consensus_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("consensus_threshold must be between 0 and 1")
        return v

    # -- Legacy conversion ---------------------------------------------------

    @classmethod
    def from_legacy(
        cls,
        legacy: AgentPersona,
        prompt_template_id: str | None = None,
    ) -> RoleDefinition:
        """Convert from ``backend.core.profiles.AgentPersona``.

        The ``system_prompt`` field is dropped — prompt content is now
        referenced via ``prompt_template_id``.
        """
        now = datetime.now(UTC)
        return cls(
            id=legacy.id,
            name=legacy.name,
            role_type_id=legacy.role,
            description=legacy.description or "",
            prompt_template_id=prompt_template_id,
            max_rounds=legacy.max_rounds,
            consensus_threshold=legacy.consensus_threshold,
            tags=list(legacy.tags) if legacy.tags else [],
            created_at=now,
            updated_at=now,
        )

    def to_legacy(
        self,
        system_prompt: str = "",
        llm_profile_id: str = "",
    ) -> AgentPersona:
        """Convert to ``backend.core.profiles.AgentPersona`` for backward compat.

        Args:
            system_prompt: The prompt content (resolved from PromptTemplate).
            llm_profile_id: The LLM profile ID to use.
        """
        return AgentPersona(
            id=self.id.replace("_", "-"),
            name=self.name,
            role=self.role_type_id,  # type: ignore[arg-type]
            system_prompt=system_prompt or f"# {self.name}\n(No prompt configured)",
            llm_profile_id=llm_profile_id or "openrouter-claude",
            max_rounds=self.max_rounds,
            consensus_threshold=self.consensus_threshold,
            description=self.description,
            tags=list(self.tags) if self.tags else [],
        )


# ---------------------------------------------------------------------------
# 2.5 RoleType
# ---------------------------------------------------------------------------


class RoleType(BaseModel):
    """A configurable role type/category (e.g. strategist, critic, optimizer, moderator).

    Role types are first-class canvas entities that can be created, edited,
    and connected to Role Definitions and Agent Blueprints. They define the
    behavioral category and visual identity of a role.
    """

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str
    description: str = ""
    icon: str = "👤"  # Emoji icon for canvas display
    color: str = "#8b5cf6"  # Hex color for node border/background
    # Behavioral defaults applied to RoleDefinitions using this type
    default_max_rounds: int = 5
    default_consensus_threshold: float = 0.9
    # Metadata
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("default_consensus_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("default_consensus_threshold must be between 0 and 1")
        return v

    @field_validator("default_max_rounds")
    @classmethod
    def validate_max_rounds(cls, v: int) -> int:
        if v < 1:
            raise ValueError("default_max_rounds must be >= 1")
        return v


# ---------------------------------------------------------------------------
# 2.6 AgentBlueprint
# ---------------------------------------------------------------------------


class AgentBlueprint(BaseModel):
    """A reusable agent configuration combining LLM, role, and prompt.

    The composite model — ties together an LLM profile, a role definition,
    and optionally a prompt template into a reusable debate agent
    configuration.
    """

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9._-]*$")
    name: str
    description: str = ""
    # References
    llm_profile_id: str  # References BlueprintLLMProfile.id
    role_definition_id: str  # References RoleDefinition.id
    prompt_template_id: str | None = None  # Optional override
    # Metadata
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# 2.6 Canvas Layout models
# ---------------------------------------------------------------------------


class CanvasLayoutNode(BaseModel):
    """A node in the simplified canvas layout format."""

    id: str
    type: str  # e.g. "agent-blueprint", "llm-profile"
    x: float
    y: float
    blueprint_id: str | None = None  # References AgentBlueprint.id


class CanvasLayoutEdge(BaseModel):
    """An edge in the simplified canvas layout format."""

    id: str
    source: str  # Node ID
    target: str  # Node ID
    type: str  # e.g. "uses_llm", "implements_role"


class CanvasLayoutViewport(BaseModel):
    """Viewport state for the canvas."""

    x: float = 0
    y: float = 0
    zoom: float = 1


class CanvasLayoutData(BaseModel):
    """Simplified canvas layout data — NOT raw React Flow JSON.

    Translation to full Svelte Flow format happens in the frontend on load.
    """

    nodes: list[CanvasLayoutNode] = Field(default_factory=list)
    edges: list[CanvasLayoutEdge] = Field(default_factory=list)
    viewport: CanvasLayoutViewport = Field(default_factory=CanvasLayoutViewport)


class CanvasLayout(BaseModel):
    """A saved canvas arrangement of agent blueprints."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str
    description: str = ""
    project_id: str | None = None
    layout_data: CanvasLayoutData = Field(default_factory=CanvasLayoutData)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# ToneProfile
# ---------------------------------------------------------------------------


class ToneProfile(BaseModel):
    """Debate tone/style configuration for agent nodes.

    Defines how an agent should communicate: formal vs. casual,
    heated vs. neutral, verbose vs. concise, etc.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""

    style: Literal["heated", "academic", "conversational", "socratic", "neutral"] = "neutral"
    formality: float = Field(default=0.5, ge=0.0, le=1.0)
    verbosity: Literal["concise", "normal", "verbose"] = "normal"
    emotional_valence: float = Field(default=0.5, ge=0.0, le=1.0)
    rhetorical_mode: Literal["none", "questioning", "assertive", "dialectic"] = "none"
    custom_instructions: str | None = None

    is_system: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
