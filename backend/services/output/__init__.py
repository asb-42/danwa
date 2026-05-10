"""Output Composer — plugin-based rendering pipeline.

This package provides the plugin architecture for transforming
``DebateArtifact`` objects into target formats (PDF, DOCX, MP3, etc.).
"""

from backend.services.output.registry import PluginRegistry, register_plugin

__all__ = ["PluginRegistry", "register_plugin"]
