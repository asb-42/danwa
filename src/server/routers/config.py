"""API router for configuration management (LLM profiles, agent profiles, prompt variants, settings)."""

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

router = APIRouter()
cm = ConfigManager()


# --- Pydantic models for request bodies ---

class LLMProfileBody(BaseModel):
    profile_name: str
    profile_data: Dict[str, Any]


class AgentProfileBody(BaseModel):
    profile_name: str
    profile_data: Dict[str, Any]


class PromptVariantBody(BaseModel):
    variant_name: str
    variant_data: Dict[str, Any]


class DefaultBody(BaseModel):
    name: str


class LanguageBody(BaseModel):
    language: str


# --- LLM Profiles ---

@router.get("/llm-profiles")
def list_llm_profiles():
    """List all LLM profiles."""
    return cm.get_llm_profiles()


@router.get("/llm-profiles/{name}")
def get_llm_profile(name: str):
    """Get a single LLM profile by name."""
    profile = cm.get_llm_profile(name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"LLM profile '{name}' not found")
    return {name: profile}


@router.post("/llm-profiles")
def create_llm_profile(body: LLMProfileBody):
    """Create or update an LLM profile."""
    cm.add_llm_profile(body.profile_name, body.profile_data)
    return {"status": "ok", "profile": body.profile_name}


@router.put("/llm-profiles/{name}")
def update_llm_profile(name: str, body: Dict[str, Any]):
    """Update an existing LLM profile."""
    existing = cm.get_llm_profile(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"LLM profile '{name}' not found")
    cm.update_llm_profile(name, body)
    return {"status": "ok", "profile": name}


@router.delete("/llm-profiles/{name}")
def delete_llm_profile(name: str):
    """Delete an LLM profile."""
    result = cm.delete_llm_profile(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"LLM profile '{name}' not found")
    return {"status": "ok", "deleted": name}


# --- Agent Profiles ---

@router.get("/agent-profiles")
def list_agent_profiles():
    """List all agent profiles."""
    return cm.get_agent_profiles()


@router.get("/agent-profiles/{name}")
def get_agent_profile(name: str):
    """Get a single agent profile by name."""
    profile = cm.get_agent_profile(name)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Agent profile '{name}' not found")
    return {name: profile}


@router.post("/agent-profiles")
def create_agent_profile(body: AgentProfileBody):
    """Create or update an agent profile."""
    cm.add_agent_profile(body.profile_name, body.profile_data)
    return {"status": "ok", "profile": body.profile_name}


@router.put("/agent-profiles/{name}")
def update_agent_profile(name: str, body: Dict[str, Any]):
    """Update an existing agent profile."""
    existing = cm.get_agent_profile(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Agent profile '{name}' not found")
    cm.add_agent_profile(name, body)
    return {"status": "ok", "profile": name}


@router.delete("/agent-profiles/{name}")
def delete_agent_profile(name: str):
    """Delete an agent profile."""
    result = cm.delete_agent_profile(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent profile '{name}' not found")
    return {"status": "ok", "deleted": name}


@router.put("/agent-profiles/default")
def set_default_agent_profile(body: DefaultBody):
    """Set the default agent profile."""
    result = cm.set_default_agent_profile(body.name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent profile '{body.name}' not found")
    return {"status": "ok", "default": body.name}


# --- Prompt Variants ---

@router.get("/prompt-variants")
def list_prompt_variants():
    """List all prompt variants."""
    return cm.get_prompt_variants()


@router.post("/prompt-variants")
def create_prompt_variant(body: PromptVariantBody):
    """Create or update a prompt variant."""
    cm.add_prompt_variant(body.variant_name, body.variant_data)
    return {"status": "ok", "variant": body.variant_name}


@router.delete("/prompt-variants/{name}")
def delete_prompt_variant(name: str):
    """Delete a prompt variant."""
    result = cm.delete_prompt_variant(name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Prompt variant '{name}' not found")
    return {"status": "ok", "deleted": name}


@router.put("/prompt-variants/default")
def set_default_variant(body: DefaultBody):
    """Set the default prompt variant."""
    cm.set_default_variant(body.name)
    return {"status": "ok", "default": body.name}


# --- Settings ---

@router.get("/settings")
def get_settings():
    """Get all settings."""
    return cm.get_settings()


@router.put("/settings")
def update_settings(body: Dict[str, Any]):
    """Update settings."""
    cm.update_settings(body)
    return {"status": "ok"}


# --- Language ---

@router.get("/language")
def get_language():
    """Get the current UI language."""
    return {"language": cm.get_ui_language(), "supported": cm.SUPPORTED_LANGUAGES}


@router.put("/language")
def set_language(body: LanguageBody):
    """Set the UI language."""
    result = cm.set_ui_language(body.language)
    if not result:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {body.language}")
    return {"status": "ok", "language": body.language}
