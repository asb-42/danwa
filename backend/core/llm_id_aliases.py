"""LLM Profile ID alias resolver.

After the UUID migration, legacy semantic IDs (like ``xiaomi-mimo-v2.5-pro``)
no longer exist in the database.  This module provides a runtime resolver
that maps any legacy ID to its UUID equivalent, so that:

- Old references stored in YAML / JSON / persisted frontend state still work
- The service LLM fallback is always available

Usage::

    from backend.core.llm_id_aliases import resolve_llm_id

    profile_id = resolve_llm_id("xiaomi-mimo-v2.5-pro")  # → UUID
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

# Canonical active default — what the user sees in the UI as "Standard-Modell"
_ACTIVE_DEFAULT_ALIAS = "xiaomi-mimo-v2.5-pro"


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
    """Return the UUID of the active default service LLM profile.

    This is the canonical fallback when a debate is started without
    an explicit LLM choice.  Never returns a hardcoded provider name —
    always the active default (currently ``xiaomi-mimo-v2.5-pro``).
    """
    _ensure_loaded()
    return _LEGACY_ALIASES.get(_ACTIVE_DEFAULT_ALIAS, "")
