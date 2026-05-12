"""PluginManifest — model for external plugin discovery.

External plugins are loaded from the ``external_plugins/`` directory
and must provide a ``manifest.json`` conforming to this schema.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PluginManifest(BaseModel):
    """Manifest descriptor for an external plugin.

    Each external plugin directory must contain a ``manifest.json``
    file that deserializes to this model.
    """

    manifest_version: str = Field(
        default="1.0",
        description="Manifest schema version",
    )
    plugin_key: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Unique key identifying this plugin (e.g. 'video_renderer')",
    )
    plugin_type: Literal["input", "output", "both"] = Field(
        default="output",
        description="Whether this is an input plugin, output plugin, or both",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Human-readable plugin name",
    )
    description: str = Field(
        default="",
        description="Short description of the plugin",
    )
    author: str = Field(
        default="",
        description="Plugin author or organization",
    )
    version: str = Field(
        default="1.0.0",
        description="Semantic version of the plugin",
    )
    entrypoint: str = Field(
        ...,
        description=("Python module path (e.g. 'external_plugins.my_plugin.plugin') or Docker image reference"),
    )
    config_schema: dict = Field(
        default_factory=dict,
        description="JSON Schema for the plugin's configuration",
    )
    permissions: list[str] = Field(
        default_factory=list,
        description="Required permissions (e.g. ['network', 'filesystem'])",
    )
