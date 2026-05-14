"""Pydantic models for the Danwa Module System."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class ModuleType(StrEnum):
    ARGUMENTATION_PATTERN = "argumentation-pattern"
    AGENT_PERSONA = "agent-persona"
    LLM_PROFILE = "llm-profile"
    WORKFLOW_TEMPLATE = "workflow-template"
    TONE_PROFILE = "tone-profile"
    WORKFLOW_VARIANT = "workflow-variant"
    BUNDLE = "bundle"


class ModuleCategory(StrEnum):
    PROMPTS = "prompts"
    AGENTS = "agents"
    LLM_PROFILES = "llm-profiles"
    WORKFLOWS = "workflows"
    WORKFLOW_VARIANTS = "workflow-variants"
    TONE_PROFILES = "tone-profiles"
    BUNDLES = "bundles"


class ModuleFile(BaseModel):
    """A single file within a module."""

    path: str
    format: str  # "markdown", "yaml", "json"
    checksum: str = ""
    role_type_id: str | None = None
    mode: str | None = None
    language: str | None = None
    subtype: str | None = None


class ModuleManifest(BaseModel):
    """Full manifest for a Danwa module."""

    schema_version: str = "1.0.0"
    module_id: str = Field(..., pattern=r"^[a-z][a-z0-9.-]*$")
    name: dict[str, str] = Field(default_factory=dict)
    description: dict[str, str] = Field(default_factory=dict)
    version: str = "0.0.0"
    type: ModuleType
    category: ModuleCategory
    author: dict[str, str] = Field(default_factory=dict)
    license: str = "CC-BY-4.0"
    dependencies: dict[str, str] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    language: str = "en"
    checksum: str = ""
    files: list[ModuleFile] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("module_id")
    @classmethod
    def validate_module_id(cls, v: str) -> str:
        if not v.startswith("danwa-") and v != "danwa-core":
            # Allow non-danwa-prefixed IDs for third-party modules
            pass
        parts = v.replace("_", "-").split("-")
        if len(parts) < 2 and not v.startswith("danwa-"):
            raise ValueError("module_id should follow pattern 'danwa-{{category}}-{{name}}'")
        return v.replace("_", "-")

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        import re

        if not re.match(r"^\d+\.\d+\.\d+$", v):
            raise ValueError(f"Version '{v}' does not follow semver (X.Y.Z)")
        return v

    @field_validator("files")
    @classmethod
    def validate_files_non_empty(cls, v: list[ModuleFile]) -> list[ModuleFile]:
        if not v:
            raise ValueError("Module must contain at least one file")
        return v


class InstallationReport(BaseModel):
    """Result of a module installation operation."""

    status: str  # "ok", "skipped", "error", "partial"
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

    status: str  # "ok", "error", "blocked"
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
    installed: bool = False
    enabled: bool = True
    installed_at: datetime | None = None
    updated_at: datetime | None = None
    dependencies: dict[str, str] = Field(default_factory=dict)
    file_count: int = 0


class ValidationIssue(BaseModel):
    """A single issue found during module validation."""

    severity: str  # "error", "warning", "info"
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
    status: str  # "ok", "partial", "error"
    estimated_cost_usd: float = 0.0
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
