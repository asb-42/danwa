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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.core.profiles import LLMProfile

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
        "deepseek",
        "local",
        "ollama",
        "opencode-zen",
        "opencode-go",
        "xiaomi",
        "cloudflare",
        # STT providers (Input Composer Phase D)
        "whisper-local",
        "whisper-api",
        "azure-stt",
        "google-stt",
    ]
    model: str
    api_base: str | None = None
    api_key_env: str = "OPENROUTER_API_KEY"
    api_key: str | None = None  # BYOK: Direct API key (takes precedence over env var)
    account_id_env: str | None = None
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

    # --- Service LLM (Sprint 16) ---
    service_eligible: bool = True  # Whether this profile can be used for system/background tasks

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature."""
        if not 0 <= v <= 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max tokens."""
        if v < 1:
            raise ValueError("max_tokens must be at least 1")
        return v

    # -- Legacy conversion ---------------------------------------------------

    @classmethod
    def from_legacy(cls, legacy: LLMProfile) -> BlueprintLLMProfile:
        """Convert from ``backend.core.profiles.LLMProfile``."""
        now = datetime.now(UTC)
        protocol = getattr(legacy, "protocol", "litellm")
        # Use explicit profile_type if set, otherwise infer from protocol/provider/model
        ptype = getattr(legacy, "profile_type", None) or "text"
        if ptype == "text":
            if protocol == "stt" or legacy.provider.value in (
                "whisper-local",
                "whisper-api",
                "azure-stt",
                "google-stt",
            ):
                ptype = "stt"
            elif "tts" in legacy.model.lower() or "tts" in legacy.name.lower():
                ptype = "tts"
        return cls(
            id=legacy.id,
            name=legacy.name,
            profile_type=ptype,
            provider=legacy.provider.value,  # type: ignore[arg-type]
            model=legacy.model,
            api_base=legacy.api_base,
            api_key_env=legacy.api_key_env,
            account_id_env=getattr(legacy, "account_id_env", None),
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
            service_eligible=getattr(legacy, "service_eligible", True),
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
            account_id_env=self.account_id_env,
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
            service_eligible=self.service_eligible,
        )


# ---------------------------------------------------------------------------
# 2.3 PromptTemplate
# ---------------------------------------------------------------------------


def _compute_content_hash(content: str) -> str:
    """SHA-256[:16] of content for change detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class PromptTemplate(BaseModel):
    """A named prompt template with content and metadata.

    Content is stored inline
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
        """Validate content not empty."""
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
    # Argumentation pattern (philosophische/sachliche Ausrichtung)
    argumentation_pattern: str | None = None
    # Formatorischer Modus (Art der Gesprächsführung)
    mode: str | None = None
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
        """Validate threshold."""
        if not 0 <= v <= 1:
            raise ValueError("consensus_threshold must be between 0 and 1")
        return v

    # -- Legacy conversion ---------------------------------------------------


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
    # Klassifikation: Funktionale vs. formatorische Rolle
    category: Literal["functional", "formative"] = "functional"
    # Metadata
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("default_consensus_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        """Validate threshold."""
        if not 0 <= v <= 1:
            raise ValueError("default_consensus_threshold must be between 0 and 1")
        return v

    @field_validator("default_max_rounds")
    @classmethod
    def validate_max_rounds(cls, v: int) -> int:
        """Validate max rounds."""
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
    role_definition_id: str  # References RoleDefinition.id (module-based)
    tone_profile_id: str | None = None  # Optional: ToneProfile for communication style
    tts_voice_id: str | None = None  # TTS voice assignment (MiMo or edge-tts voice)
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
    type: str  # e.g. "agent-blueprint", "llm-profile", "wf-strategist"
    x: float = 0
    y: float = 0
    blueprint_id: str | None = None  # References AgentBlueprint.id
    label: str = ""
    agent_blueprint_id: str | None = None  # For workflow nodes referencing AgentBlueprint
    parent_id: str | None = None  # Parent phase node ID (for phase container membership)
    config: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)  # Raw node data for round-tripping


class CanvasLayoutEdge(BaseModel):
    """An edge in the simplified canvas layout format."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    source: str  # Node ID
    target: str  # Node ID
    type: str = "sequential"  # e.g. "uses_llm", "implements_role", "sequential"
    source_handle: str | None = None
    target_handle: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)  # Raw edge data for round-tripping


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


# ---------------------------------------------------------------------------
# PromptModifier
# ---------------------------------------------------------------------------


class PromptModifier(BaseModel):
    """A prompt modifier — output formatting & finetuning snippet.

    Loaded from ``modules/prompt-modifiers/`` modules and seeded into
    the database.  The ``content`` field contains the raw modifier text
    that gets appended to the system prompt during assembly.
    """

    id: str = Field(..., min_length=1, max_length=200)
    name: str = Field(..., min_length=1, max_length=200)
    content: str = ""  # The modifier text (Markdown)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    is_system: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# BundleComposition — module-ID references for Composer-based Bundles
# ---------------------------------------------------------------------------


class BundleComposition(BaseModel):
    """Modul-Referenzen für die Composer-Assembly — KEINE Inline-Daten.

    References module IDs from the ``modules/`` directory tree, NOT
    database primary keys.  At resolve time the actual content is loaded
    from the module filesystem (or a future ``danwa-modules`` resolver).

    FUTURE: Dependency resolver from ``danwa-modules`` repo on GitHub
    will automatically fetch missing dependencies.
    """

    agent_core_id: str = ""
    argumentation_pattern_id: str = ""
    prompt_modifier_id: str = ""


# ---------------------------------------------------------------------------
# AgentBundle — higher-level composition for Workflow-Nodes
# ---------------------------------------------------------------------------


class AgentBundle(BaseModel):
    """A reusable composition of LLM + Role-Type + Persona + Prompt + Tone Profile.

    Represents a complete debate agent configuration that can be placed
    as a node on the Canvas and referenced in Workflows.  Unlike
    ``AgentBlueprint`` (which ties LLM + RoleDefinition + PromptTemplate
    together), a Bundle is more flexible: it references a RoleType directly
    and optionally includes a ToneProfile.
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    # Core composition
    llm_profile_id: str  # References BlueprintLLMProfile.id
    role_type_id: str  # References RoleType.id (module-based)
    tone_profile_id: str | None = None  # Optional: ToneProfile for communication style
    # Composition (Composer-based assembly)
    composition: BundleComposition | None = None
    # LLM generation parameters (override LLM profile defaults at inference time)
    model_params: dict = Field(
        default_factory=dict,
        description="LLM inference overrides (temperature, top_p, top_k, frequency_penalty, presence_penalty, etc.)",
    )
    # Metadata
    tags: list[str] = Field(default_factory=list)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# ResolvedBundle — fully resolved Bundle with all referenced entities inline
# ---------------------------------------------------------------------------


class ResolvedBundle(BaseModel):
    """An AgentBundle with all referenced entities resolved and inline.

    Produced by the BundleResolver for use in Workflow execution.
    Contains the fully assembled system prompt.
    """

    bundle_id: str
    bundle_name: str
    llm_profile: BlueprintLLMProfile
    role_type: RoleType
    tone_profile: ToneProfile | None = None
    system_prompt: str = ""
    model_params: dict = Field(
        default_factory=dict,
        description="LLM inference overrides (temperature, top_p, etc.)",
    )
