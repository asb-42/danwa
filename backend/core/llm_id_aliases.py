"""LLM Profile ID alias resolver.

After the UUID migration, legacy semantic IDs (like ``openrouter-claude``)
no longer exist in the database.  This module provides a runtime resolver
that maps any legacy ID to its UUID equivalent, so that:

- Hardcoded defaults (``"openrouter-claude"``) resolve to a valid profile
- Old references stored in YAML / JSON / persisted frontend state still work
- The service LLM fallback is always available

Usage::

    from backend.core.llm_id_aliases import resolve_llm_id

    profile_id = resolve_llm_id("openrouter-claude")  # → UUID
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Static legacy aliases ────────────────────────────────────────────────
# These cover the hardcoded defaults found throughout the codebase.
# The mapping file (scripts/llm_id_mapping.json) is the authoritative source;
# this dict is a fast in-memory cache of the most common fallbacks.

_LEGACY_ALIASES: dict[str, str] = {}

_MAPPING_FILE = Path(__file__).resolve().parent.parent.parent / "scripts" / "llm_id_mapping.json"


def _load_mapping() -> dict[str, str]:
    """Load the old→new mapping from the migration script output."""
    if not _MAPPING_FILE.exists():
        return {}
    try:
        with open(_MAPPING_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load LLM ID mapping from %s: %s", _MAPPING_FILE, exc)
        return {}


def _ensure_loaded() -> None:
    """Lazily load the mapping on first use."""
    if not _LEGACY_ALIASES:
        _LEGACY_ALIASES.update(_load_mapping())
        # Also add common hardcoded aliases that don't exist in the DB
        # "openrouter-claude" was a legacy default that never had a DB entry.
        # Map it to the cloud-openrouter profile (claude-3-5-sonnet on OpenRouter).
        cloud_openrouter_uuid = _LEGACY_ALIASES.get("cloud-openrouter", "")
        if cloud_openrouter_uuid:
            _LEGACY_ALIASES.setdefault("openrouter-claude", cloud_openrouter_uuid)


def resolve_llm_id(profile_id: str | None) -> str:
    """Resolve an LLM profile ID, mapping legacy names to UUIDs.

    Returns the UUID if the ID is a legacy alias, or the original ID
    if it's already a UUID or unknown.  Returns ``""`` for None/empty input.
    """
    if not profile_id:
        return ""
    _ensure_loaded()
    return _LEGACY_ALIASES.get(profile_id, profile_id)


def get_default_llm_profile_id() -> str:
    """Return the UUID of the default service LLM profile.

    This replaces the hardcoded ``"openrouter-claude"`` default used
    throughout the codebase.
    """
    _ensure_loaded()
    # The service LLM (previously xiaomi-mimo-v2.5-pro) is the canonical default
    return _LEGACY_ALIASES.get("xiaomi-mimo-v2.5-pro", "")
