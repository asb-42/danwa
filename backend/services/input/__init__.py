"""Input Composer — plugin-based input capture pipeline.

This package provides the plugin architecture for capturing input
from various sources (text, STT, A2A, MCP) and transforming it into
standardized ``DebateInput`` artifacts for workflow execution.
"""

from backend.services.input.registry import InputPluginRegistry, register_input_plugin

__all__ = ["InputPluginRegistry", "register_input_plugin"]
