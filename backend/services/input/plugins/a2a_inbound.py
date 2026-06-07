"""A2A Inbound Plugin — handles incoming A2A agent requests.

When an external A2A agent sends a request to Danwa, this plugin
validates and wraps it into a ``DebateInput`` artifact.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

from pydantic import BaseModel, Field

from backend.models.debate_input import DebateInput
from backend.services.input.base import InputPlugin
from backend.services.input.registry import register_input_plugin


class A2AInboundConfig(BaseModel):
    """Configuration schema for the A2A Inbound plugin."""

    allowed_agents: list[str] = Field(
        default_factory=list,
        description="List of allowed external agent IDs (empty = all allowed)",
    )
    require_approval: bool = Field(
        default=True,
        description="Require user approval before processing",
    )


@register_input_plugin
class A2AInboundPlugin(InputPlugin):
    """A2A Inbound input plugin.

    The actual A2A request handling happens via the A2A inbound
    endpoint.  This plugin provides validation and wrapping logic.
    """

    plugin_key: ClassVar[str] = "a2a_inbound"
    plugin_name: ClassVar[str] = "A2A Agent Request"
    config_schema: ClassVar[type[BaseModel]] = A2AInboundConfig

    async def capture(self, config: BaseModel) -> DebateInput:
        """Create a DebateInput from an A2A message.

        Note: For A2A, the message is received by the inbound endpoint.
        This method wraps it into a DebateInput.

        Args:
            config: Validated ``A2AInboundConfig``.

        Returns:
            A skeleton ``DebateInput`` (topic filled by the endpoint).
        """
        return DebateInput(
            source_plugin_key=self.plugin_key,
            topic="",  # filled by the A2A inbound endpoint
            timestamp=datetime.now(UTC),
            source_metadata={
                "require_approval": config.require_approval,
                "allowed_agents": config.allowed_agents,
            },
        )

    def get_ui_hints(self) -> dict:
        """Retrieve and return ui hints."""
        return {
            "requires_microphone": False,
            "supports_streaming": False,
            "is_available": True,
            "requires_external_request": True,
        }
