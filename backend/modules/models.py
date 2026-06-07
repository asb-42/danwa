"""Pydantic models for the Danwa Module System v2.

v2 changes:
- 1 module = 1 profile (not a bundle)
- `profile_file` + `profile_format` replace `files[]` for single-profile modules
- Legacy `files[]` still supported during migration
- New typed models for RoleType, ToneProfile
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ModuleType(StrEnum):
    """ModuleType class."""

    ARGUMENTATION_PATTERN = "argumentation-pattern"
    AGENT_PERSONA = "agent-persona"
    LLM_PROFILE = "llm-profile"
    WORKFLOW_TEMPLATE = "workflow-template"
    TONE_PROFILE = "tone-profile"
    WORKFLOW_VARIANT = "workflow-variant"
    ROLE_TYPE = "role-type"
    PROMPT_VARIANT = "prompt-variant"
    PROMPT_MODIFIER = "prompt-modifier"
    KITSUNE_ASSISTANT = "kitsune-assistant"
    BUNDLE = "bundle"
    LANGUAGE_PACK = "language-pack"
    AGENT_CORE = "agent-core"


class ModuleCategory(StrEnum):
    """ModuleCategory class."""

    PROMPTS = "prompts"
    PROMPT_MODIFIERS = "prompt-modifiers"
    AGENTS = "agents"
    LLM_PROFILES = "llm-profiles"
    WORKFLOWS = "workflows"
    WORKFLOW_VARIANTS = "workflow-variants"
    TONE_PROFILES = "tone-profiles"
    ROLE_TYPES = "role-types"
    KITSUNE = "kitsune"
    BUNDLES = "bundles"
    TRANSLATIONS = "translations"


class ModuleFile(BaseModel):
    """A single file within a module (legacy bundle format)."""

    path: str
    format: str  # "markdown", "yaml", "json"
    checksum: str = ""
    role_type_id: str | None = None
    mode: str | None = None
    language: str | None = None
    subtype: str | None = None


class RoleTypeProfile(BaseModel):
    """Profile data for a role-type module."""

    id: str
    name: str
    description: str = ""
    icon: str = ""
    color: str = ""
    default_max_rounds: int = 5
    default_consensus_threshold: float = 0.9
    category: str = "functional"
    is_active: bool = True


class ToneProfileData(BaseModel):
    """Profile data for a tone-profile module."""

    id: str
    name: str
    description: str = ""
    style: str = "neutral"
    formality: float = 0.5
    verbosity: str = "medium"
    emotional_valence: float = 0.5
    rhetorical_mode: str = "balanced"
    custom_instructions: str | None = None


class LLMProfileData(BaseModel):
    """Profile data for an LLM-profile module (mirrors backend.core.profiles.LLMProfile)."""

    id: str
    name: str
    provider: str
    model: str
    api_base: str | None = None
    api_key_env: str = "OPENROUTER_API_KEY"
    account_id_env: str | None = None
    max_tokens: int = 4096
    context_window: int | None = None
    temperature: float = 0.7
    timeout: int = 600
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None
    protocol: str = "litellm"
    a2a_endpoint: str | None = None
    a2a_timeout: int = 120
    fallback_llm_profile_id: str | None = None
    service_eligible: bool = True
    min_recommended_context: int = 1024


class AgentPersonaData(BaseModel):
    """Profile data for an agent-persona module."""

    id: str
    name: str
    role: str
    system_prompt: str
    llm_profile_id: str
    max_rounds: int = 5
    consensus_threshold: float = 0.9
    argumentation_pattern: str | None = None
    mode: str | None = None
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class WorkflowTemplateData(BaseModel):
    """Profile data for a workflow-template module."""

    id: str
    name: str
    description: str = ""
    category: str = "system"
    tags: list[str] = Field(default_factory=list)
    template_data: dict[str, Any] = Field(default_factory=dict)


class LanguagePackData(BaseModel):
    """Profile data for a language-pack module."""

    locale: str  # Target locale code (e.g. "de", "es", "de-custom")
    source_locale: str = "en"  # Source locale for translations
    key_count: int = 0  # Number of translation keys
    coverage: float = 0.0  # Coverage ratio vs. source locale (0.0-1.0)
    ui_strings_file: str = "ui_strings.json"
    module_translations: list[str] = Field(default_factory=list)  # Paths to translated module files


class ManifestCompatibility(BaseModel):
    """Compatibility range for Danwa versions."""

    danwa_min_version: str | None = None
    danwa_max_version: str | None = None


class ManifestRepository(BaseModel):
    """Source repository reference for a module."""

    type: str = "github"
    url: str = ""
    ref: str | None = None


class ModuleDependencies(BaseModel):
    """Dependency declaration for a module.

    Supports two kinds of dependencies:
    - ``modules``: explicit module_id → semver constraint pairs
    - ``roles``: required agent-core roles (resolved dynamically at install time)
    """

    modules: dict[str, str] = Field(default_factory=dict)
    roles: list[str] = Field(default_factory=list)


class ModuleManifest(BaseModel):
    """Manifest for a Danwa module.

    v3: adds `compatibility` + `repository` fields
    v2 (single-profile): uses `profile_file` + `profile_format`
    v1 (legacy bundle): uses `files[]`
    """

    schema_version: str = "2.0.0"
    module_id: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    name: dict[str, str] = Field(default_factory=dict)
    description: dict[str, str] = Field(default_factory=dict)
    version: str = "1.0.0"
    type: ModuleType | None = None  # Derived from directory + module_id prefix if absent
    category: ModuleCategory | None = None  # Derived from directory if absent
    author: dict[str, str] = Field(default_factory=dict)
    license: str = "CC-BY-4.0"
    dependencies: ModuleDependencies = Field(default_factory=ModuleDependencies)
    tags: list[str] = Field(default_factory=list)
    language: str = "en"
    checksum: str = ""
    role: str | None = None  # Agent-core role name (e.g. "strategist", "critic")

    # v2: single profile file
    profile_file: str | None = None  # e.g. "profile.yaml"
    profile_format: Literal["yaml", "json", "markdown"] | None = None

    # v1: legacy bundle files (migration compat)
    files: list[ModuleFile] = Field(default_factory=list)

    # v3: repository origin
    compatibility: ManifestCompatibility = Field(default_factory=ManifestCompatibility)
    repository: ManifestRepository = Field(default_factory=ManifestRepository)

    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("module_id")
    @classmethod
    def validate_module_id(cls, v: str) -> str:
        """Validate module id."""
        v = v.replace("_", "-")
        if not v.startswith("danwa-") and "-" not in v:
            raise ValueError(f"module_id must contain at least one hyphen (non-danwa module), got '{v}'")
        return v

    @property
    def uuid(self) -> str | None:
        """Extract the UUID portion from a UUID-based module_id (e.g. 'ac-550e8400-...')."""
        parts = self.module_id.split("-", 1)
        if len(parts) == 2:
            try:
                import uuid as _uuid

                _uuid.UUID(parts[1])
                return parts[1]
            except ValueError:
                pass
        return None

    @field_validator("dependencies", mode="before")
    @classmethod
    def coerce_dependencies(cls, v: Any) -> Any:
        """Accept legacy flat dict ``{module_id: constraint}`` and wrap it."""
        if isinstance(v, dict) and "modules" not in v and "roles" not in v:
            return {"modules": v}
        return v


class InstallationReport(BaseModel):
    """Result of a module installation operation."""

    status: str
    module_id: str
    version: str
    files_installed: int = 0
    files_failed: int = 0
    db_entries_created: int = 0
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    checksum: str = ""
    installed_at: datetime | None = None


class UninstallationReport(BaseModel):
    """Result of a module uninstallation operation."""

    status: str
    module_id: str
    files_removed: int = 0
    db_entries_removed: int = 0
    warnings: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)


class ModuleInfo(BaseModel):
    """Summary information about an installed or available module."""

    module_id: str
    name: dict[str, str] = Field(default_factory=dict)
    description: dict[str, str] = Field(default_factory=dict)
    version: str
    type: ModuleType
    category: ModuleCategory
    author: dict[str, str] = Field(default_factory=dict)
    license: str = "CC-BY-4.0"
    tags: list[str] = Field(default_factory=list)
    language: str = "en"
    checksum: str = ""
    role: str | None = None
    dependencies: dict[str, Any] = Field(default_factory=dict)
    installed: bool = False
    enabled: bool = True
    installed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    file_count: int = 0

    # v2: profile preview data (parsed from profile file)
    profile_preview: dict[str, Any] | None = None


class ValidationIssue(BaseModel):
    """A single issue found during module validation."""

    severity: str
    field: str
    message: str
    file_path: str | None = None


class ValidationResult(BaseModel):
    """Complete validation result for a module."""

    module_id: str | None
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    file_count: int = 0
    checksum_valid: bool = True


class TranslationResult(BaseModel):
    """Result of a translation operation."""

    module_id: str
    target_language: str
    files_translated: int = 0
    files_skipped: int = 0
    files_errored: int = 0
    quality_scores: dict[str, float] = Field(default_factory=dict)
    back_translation_scores: dict[str, float] = Field(default_factory=dict)
    status: str
    estimated_cost_usd: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
