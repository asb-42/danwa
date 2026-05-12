"""MCPAdapter — Protocol interface for future MCP server/client integration.

Danwa will act as an MCP-Server: external services can call Danwa
as a tool.  For Input Composer, this means an external MCP tool
submits a request that becomes a DebateInput.

This is a Protocol (structural subtyping) — concrete implementations
will be provided in a future phase.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class MCPAdapter(Protocol):
    """Interface for MCP server/client integration.

    Implementations must provide ``handle_tool_call`` which processes
    an incoming MCP tool invocation and returns a result dict.
    """

    async def handle_tool_call(self, tool_name: str, arguments: dict) -> dict:
        """Handle an incoming MCP tool call.

        Args:
            tool_name: The name of the tool being called.
            arguments: The tool arguments as a dict.

        Returns:
            A dict with the tool's response.
        """
        ...
