"""Example Video Renderer — stub external output plugin.

This is a template demonstrating the external plugin format.
It does NOT produce any output. Replace with real implementation.

Usage:
    Loaded only when DANWA_ALLOW_EXTERNAL_PLUGINS=true.
    The manifest.json in this directory declares the plugin metadata.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, Field

# NOTE: In a real external plugin, these imports would resolve via
# the installed danwa package or by adding the project to PYTHONPATH.
# from backend.services.output.base import OutputPlugin
# from backend.services.output.registry import register_plugin


class VideoRendererConfig(BaseModel):
    """Configuration for the video renderer plugin."""

    resolution: str = Field(default="1080p", description="Video resolution")
    fps: int = Field(default=30, ge=1, le=60, description="Frames per second")


# --- Stub OutputPlugin (not registered, template only) ---


class ExampleVideoRenderer:
    """Stub output plugin for video rendering.

    This class follows the OutputPlugin contract but is NOT registered
    via @register_plugin because it's an external template.
    To make it functional:
    1. Import OutputPlugin from backend.services.output.base
    2. Subclass OutputPlugin
    3. Add @register_plugin decorator
    4. Implement render() method
    """

    plugin_key: ClassVar[str] = "example_video_renderer"
    plugin_name: ClassVar[str] = "Example Video Renderer"
    supported_formats: ClassVar[list[str]] = ["mp4", "webm"]
    config_schema: ClassVar[type[BaseModel]] = VideoRendererConfig

    async def render(
        self,
        artifact: object,
        config: BaseModel,
        job_id: str,
        output_dir: Path,
    ) -> list[Path]:
        """Render artifact to video files. NOT IMPLEMENTED."""
        raise NotImplementedError("ExampleVideoRenderer is a stub. Implement render() to produce actual video output.")
