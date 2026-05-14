"""A2A Agent Card — exposes Danwa's debate capabilities.

The Agent Card is served at ``/.well-known/agent.json`` and allows
external A2A clients to discover Danwa's capabilities, skills, and
supported input/output modes.
"""

from __future__ import annotations

from backend import __version__

AGENT_CARD: dict = {
    "name": "Danwa Debate Engine",
    "description": (
        "Multi-agent debate system that analyzes topics from multiple perspectives using AI agents (Strategist, Critic, Optimizer, Moderator)."
    ),
    "url": "",  # Set dynamically from server config
    "version": __version__,
    "capabilities": {
        "streaming": False,
        "pushNotifications": False,
    },
    "skills": [
        {
            "id": "debate",
            "name": "Multi-Agent Debate",
            "description": ("Run a structured multi-agent debate on any topic. Returns consensus analysis with multiple perspectives."),
            "tags": ["debate", "analysis", "multi-agent"],
            "examples": [
                "Analyze the pros and cons of remote work",
                "Debate the ethical implications of AI in healthcare",
            ],
        }
    ],
    "defaultInputModes": ["text"],
    "defaultOutputModes": ["text"],
}
