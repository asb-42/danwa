"""MCP Input Plugin — stub for future MCP (Model Context Protocol) integration.

This plugin is registered but not yet functional.  It serves as a
template for future MCP server/client integration.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, Field

from backend.models.debate_input import DebateInput
from backend.services.input.base import InputPlugin
from backend.services.input.registry import register_input_plugin


class MCPPluginConfig(BaseModel):
    """Configuration schema for the MCP Input plugin (stub)."""

    server_name: str = Field(description="MCP server name")
    tool_name: str = Field(description="MCP tool name to invoke")


@register_input_plugin
class MCPInputPlugin(InputPlugin):
    """MCP Input plugin — stub for future extension.

    Currently raises ``NotImplementedError`` on ``capture()``.
    Listed in the registry with ``is_available: false``.
    """

    plugin_key: ClassVar[str] = "mcp"
    plugin_name: ClassVar[str] = "MCP Tool Input"
    config_schema: ClassVar[type[BaseModel]] = MCPPluginConfig

    async def capture(self, config: BaseModel) -> DebateInput:
        """Not yet implemented.

        Raises:
            NotImplementedError: Always — this is a stub.
        """
        raise NotImplementedError(
            "MCP input plugin is not yet implemented. "
            "This is a stub for future extension. "
            "Danwa will act as an MCP-Server where external MCP tools "
            "can submit requests that become DebateInput artifacts."
        )

    async def validate(self, config: BaseModel) -> bool:
        """Always returns False — plugin is not yet available."""
        return False

    def get_ui_hints(self) -> dict:
        """Retrieve and return ui hints."""
        return {
            "requires_microphone": False,
            "supports_streaming": False,
            "is_available": False,
            "coming_soon": True,
        }
