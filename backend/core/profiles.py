"""Pydantic schemas for profile management.

Defines typed, validated models for LLM profiles, agent personas,
prompt variants, and active debate configurations.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENROUTER = "openrouter"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    OLLAMA = "ollama"
    OPENCODE_ZEN = "opencode-zen"
    OPENCODE_GO = "opencode-go"
    XIAOMI = "xiaomi"


class LLMProfile(BaseModel):
    """Configuration for a specific LLM endpoint."""

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str
    provider: LLMProvider
    model: str  # e.g. "anthropic/claude-3.5-sonnet"
    api_base: Optional[str] = None  # For OpenRouter / local
    api_key_env: str = "OPENROUTER_API_KEY"  # Environment variable name
    max_tokens: int = 4096
    context_window: Optional[int] = None  # Max total tokens (input + output) the model supports
    temperature: float = 0.7
    timeout: int = 600

    # Cost tracking (USD per 1k tokens)
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None

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


class AgentPersona(BaseModel):
    """Configuration for a debate agent persona."""

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str
    role: Literal["strategist", "critic", "optimizer", "moderator"]
    system_prompt: str
    llm_profile_id: str  # Reference to LLMProfile.id

    # Behaviour constraints
    max_rounds: int = 5
    consensus_threshold: float = 0.9

    # Metadata
    description: Optional[str] = None
    tags: List[str] = []

    @field_validator("consensus_threshold")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("consensus_threshold must be between 0 and 1")
        return v


class PromptVariant(BaseModel):
    """A named set of prompt templates for debate agents."""

    id: str = Field(..., pattern=r"^[a-z0-9][a-z0-9.-]*$")
    name: str
    base_path: str  # e.g. "profiles/prompts/default/"

    # Override for specific agents: agent_role → file path
    overrides: Dict[str, str] = {}

    # Metadata
    description: Optional[str] = None
    parent_variant: Optional[str] = None  # Inheritance


class ActiveConfiguration(BaseModel):
    """Running configuration for a specific debate."""

    debate_id: str
    llm_profile_id: str
    agent_personas: Dict[str, str]  # role → persona_id
    prompt_variant_id: str
    created_at: str

    # Runtime info
    estimated_cost: Optional[float] = None
    actual_cost: Optional[float] = None
