"""STT Input Plugin — Speech-to-Text input via configurable STT profiles.

Supports local Whisper (faster-whisper) and cloud STT providers.
The plugin validates that the referenced LLMProfile has protocol='stt'.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.models.debate_input import DebateInput
from backend.services.input.base import InputPlugin
from backend.services.input.registry import register_input_plugin


class STTPluginConfig(BaseModel):
    """Configuration schema for the STT Input plugin."""

    llm_profile_id: str = Field(description="ID of the LLMProfile with protocol='stt'")
    stream_partial: bool = Field(
        default=True,
        description="Enable partial transcription streaming",
    )
    auto_submit: bool = Field(
        default=False,
        description="Automatically submit when transcription completes",
    )


@register_input_plugin
class STTInputPlugin(InputPlugin):
    """Speech-to-Text input plugin.

    The actual audio streaming happens via a dedicated SSE endpoint.
    This plugin provides the validation and wrapping logic.
    """

    plugin_key: ClassVar[str] = "stt"
    plugin_name: ClassVar[str] = "Speech-to-Text Input"
    config_schema: ClassVar[type[BaseModel]] = STTPluginConfig

    async def capture(self, config: BaseModel) -> DebateInput:
        """Create a DebateInput from transcribed text.

        Note: For STT, the transcription happens via the streaming
        endpoint.  This method wraps the result into a DebateInput.

        Args:
            config: Validated ``STTPluginConfig``.

        Returns:
            A skeleton ``DebateInput`` (topic filled by the service).
        """
        assert isinstance(config, STTPluginConfig)
        return DebateInput(
            source_plugin_key=self.plugin_key,
            topic="",  # filled by InputComposerService after transcription
            timestamp=datetime.now(UTC),
            source_metadata={
                "stt_profile_id": config.llm_profile_id,
                "stream_partial": config.stream_partial,
            },
        )

    async def validate(self, config: BaseModel) -> bool:
        """Check that the referenced LLMProfile exists and has protocol='stt'.

        Args:
            config: Validated ``STTPluginConfig``.

        Returns:
            ``True`` if the profile is valid.
        """
        assert isinstance(config, STTPluginConfig)
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository()
            profile = repo.get_llm_profile(config.llm_profile_id)
            if profile is None:
                return False
            return getattr(profile, "protocol", "litellm") == "stt"
        except Exception:
            return False

    def get_ui_hints(self) -> dict:
        """Retrieve and return ui hints."""
        return {
            "requires_microphone": True,
            "supports_streaming": True,
            "is_available": True,
        }
