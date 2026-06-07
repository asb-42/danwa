"""Pydantic schemas for profile management.

Defines typed, validated models for LLM profiles, agent personas,
prompt variants, and active debate configurations.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LLMProvider(StrEnum):
    """Supported LLM providers."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    OLLAMA = "ollama"
    OPENCODE_ZEN = "opencode-zen"
    OPENCODE_GO = "opencode-go"
    XIAOMI = "xiaomi"
    DEEPSEEK = "deepseek"
    CLOUDFLARE = "cloudflare"


class LLMProfile(BaseModel):
    """Configuration for a specific LLM endpoint."""

    id: str = Field(default="", pattern=r"^([a-z0-9][a-z0-9.-]*)?$")
    name: str
    profile_type: Literal["text", "tts", "stt"] = "text"
    provider: LLMProvider
    model: str  # e.g. "anthropic/claude-3.5-sonnet"
    api_base: str | None = None  # For OpenRouter / local
    api_key_env: str = "OPENROUTER_API_KEY"  # Environment variable name
    api_key: str | None = None  # BYOK: Direct API key (takes precedence over env var)
    account_id_env: str | None = None  # Environment variable name for account ID (e.g. Cloudflare)
    max_tokens: int = 4096
    context_window: int | None = None  # Max total tokens (input + output) the model supports
    temperature: float = 0.7
    timeout: int = 600

    # Cost tracking (USD per 1k tokens)
    cost_per_1k_input: float | None = None
    cost_per_1k_output: float | None = None

    # --- A2A Protocol (Phase 8) ---
    protocol: Literal["litellm", "a2a"] = "litellm"
    a2a_endpoint: str | None = None  # URL for A2A agent (e.g. "http://agent.example.com")
    a2a_timeout: int = 120  # Timeout for A2A calls in seconds
    fallback_llm_profile_id: str | None = None  # Fallback profile for A2A failures

    # --- Service LLM (Sprint 16) ---
    service_eligible: bool = True  # Whether this profile can be used for system/background tasks
    min_recommended_context: int = 1024  # Min context window recommended for service use

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


class ActiveConfiguration(BaseModel):
    """Running configuration for a specific debate."""

    debate_id: str
    llm_profile_id: str
    agent_personas: dict[str, str]  # role → persona_id
    prompt_variant_id: str
    created_at: str

    # Runtime info
    estimated_cost: float | None = None
    actual_cost: float | None = None
