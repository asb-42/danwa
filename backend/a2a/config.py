"""A2A Configuration — manages A2A settings.

Loads configuration from ``config/a2a.json`` at the project root.
Falls back to sensible defaults if the file does not exist.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "a2a.json"

_DEFAULT_CONFIG: dict = {
    "enabled": False,
    "server": {
        "enabled": True,
        "path": "/a2a",
    },
    "external_agents": [],
}


def get_a2a_config() -> dict:
    """Load A2A configuration from ``config/a2a.json``.

    Returns the default config if the file is missing or unreadable.
    """
    if _CONFIG_PATH.exists():
        try:
            return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Failed to load A2A config from %s: %s", _CONFIG_PATH, exc)
    return dict(_DEFAULT_CONFIG)


def get_external_agents() -> list[dict]:
    """Return the list of configured external A2A agents."""
    config = get_a2a_config()
    return config.get("external_agents", [])


def get_agent_for_role(role: str) -> dict | None:
    """Find an external A2A agent configured for a specific role.

    Returns ``None`` if no agent matches the given role.
    """
    for agent in get_external_agents():
        if agent.get("role") == role:
            return agent
    return None
