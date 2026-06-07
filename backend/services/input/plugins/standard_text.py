"""Standard Text Input Plugin — always available, minimal config.

The default input plugin.  Takes a topic string from the API request
and wraps it into a ``DebateInput`` artifact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.models.debate_input import DebateInput
from backend.services.input.base import InputPlugin
from backend.services.input.registry import register_input_plugin


class StandardTextConfig(BaseModel):
    """Configuration schema for the Standard Text Input plugin."""

    placeholder_text: str | None = Field(
        default=None,
        description="Optional placeholder text shown in the UI",
    )


@register_input_plugin
class StandardTextInputPlugin(InputPlugin):
    """Standard text input — the default, always-available plugin.

    Takes a topic string and wraps it into a ``DebateInput``.
    The actual text comes from the API request body, not from
    this plugin's capture method.
    """

    plugin_key: ClassVar[str] = "standard_text"
    plugin_name: ClassVar[str] = "Standard Text Input"
    config_schema: ClassVar[type[BaseModel]] = StandardTextConfig

    async def capture(self, config: BaseModel) -> DebateInput:
        """Create a DebateInput from a topic string.

        Note: For this plugin, the topic is passed externally via the
        InputComposerService, not obtained through the capture method.
        This method returns a skeleton — the service fills in the topic.

        Args:
            config: Validated ``StandardTextConfig``.

        Returns:
            A skeleton ``DebateInput`` (topic filled by the service).
        """
        return DebateInput(
            source_plugin_key=self.plugin_key,
            topic="",  # filled by InputComposerService
            timestamp=datetime.now(UTC),
            source_metadata={"placeholder": config.placeholder_text},
        )

    def get_ui_hints(self) -> dict:
        """Retrieve and return ui hints."""
        return {
            "requires_microphone": False,
            "supports_streaming": False,
            "is_available": True,
        }
