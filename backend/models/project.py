"""Project models — central organization unit for Danwa.

Every debate, document, and configuration belongs to exactly one project.
Projects provide logical isolation without requiring multi-tenant infrastructure.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from backend.core.profiles import LLMProfile, PromptVariant


class ProjectConfig(BaseModel):
    """Project-specific settings with optional overrides.

    ``None`` values fall back to global defaults.  Profile overrides use a
    merge strategy: project profiles supplement global ones, and when an ID
    exists in both, the project version wins.
    """

    # --- Debate defaults (None → use global Settings) ---
    language: str | None = None
    default_max_rounds: int | None = None
    default_consensus_threshold: float | None = None
    search_mode: str | None = None  # off / optional / required

    # --- Web search ---
    searxng_url: str | None = None

    # --- Profile overrides (ID → profile, merged with global) ---
    llm_profiles: dict[str, LLMProfile] = Field(default_factory=dict)
    prompt_variants: dict[str, PromptVariant] = Field(default_factory=dict)


class Project(BaseModel):
    """A Danwa project — the top-level organization entity."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    is_system: bool = False  # True for _default (not deletable)
    tenant_id: str = "_default"  # FK → Tenant
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config: ProjectConfig = Field(default_factory=ProjectConfig)


# --- API request/response helpers ---


class ProjectCreateRequest(BaseModel):
    """POST /api/v1/projects request body."""

    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tenant_id: str = "_default"


class ProjectUpdateRequest(BaseModel):
    """PUT /api/v1/projects/{id} request body."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class ProjectConfigUpdateRequest(BaseModel):
    """PUT /api/v1/projects/{id}/config request body."""

    config: ProjectConfig


class ProjectResponse(BaseModel):
    """GET /api/v1/projects/{id} response."""

    id: str
    name: str
    description: str
    is_system: bool
    tenant_id: str
    created_at: datetime
    updated_at: datetime
    config: ProjectConfig


class ProjectListItem(BaseModel):
    """GET /api/v1/projects list item — lightweight summary."""

    id: str
    name: str
    description: str
    is_system: bool
    tenant_id: str
    created_at: datetime
    updated_at: datetime
