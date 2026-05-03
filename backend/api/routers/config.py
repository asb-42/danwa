"""API router for application settings and language configuration.

Profile management (LLM profiles, agent personas, prompt variants) has
been moved to the ``profiles`` router.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

_SETTINGS_PATH = Path("config/settings.yaml")

SUPPORTED_LANGUAGES = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
}


# --- Helpers ---


def _load_settings() -> dict[str, Any]:
    """Load settings from YAML file."""
    if not _SETTINGS_PATH.exists():
        return {}
    with open(_SETTINGS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _save_settings(data: dict[str, Any]) -> None:
    """Save settings to YAML file."""
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    logger.info("Settings saved to %s", _SETTINGS_PATH)


# --- Request bodies ---


class SettingsBody(BaseModel):
    """Generic settings update body."""

    settings: dict[str, Any]


class LanguageBody(BaseModel):
    """Language update body."""

    language: str


# --- Settings ---


@router.get("/settings")
def get_settings() -> dict:
    """Get all application settings."""
    return _load_settings()


@router.put("/settings")
def update_settings(body: dict[str, Any]) -> dict:
    """Update application settings."""
    _save_settings(body)
    return {"status": "ok"}


# --- Language ---


@router.get("/language")
def get_language() -> dict:
    """Get the current UI language."""
    settings = _load_settings()
    language = settings.get("ui", {}).get("language", "en")
    return {"language": language, "supported": SUPPORTED_LANGUAGES}


@router.put("/language")
def set_language(body: LanguageBody) -> dict:
    """Set the UI language."""
    if body.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {body.language}")
    settings = _load_settings()
    if "ui" not in settings:
        settings["ui"] = {}
    settings["ui"]["language"] = body.language
    _save_settings(settings)
    return {"status": "ok", "language": body.language}
