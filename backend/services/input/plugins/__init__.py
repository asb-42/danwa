"""Auto-import all input plugins to trigger @register_input_plugin decorators."""

from backend.services.input.plugins.a2a_inbound import A2AInboundPlugin  # noqa: F401
from backend.services.input.plugins.mcp_plugin import MCPInputPlugin  # noqa: F401
from backend.services.input.plugins.standard_text import StandardTextInputPlugin  # noqa: F401
from backend.services.input.plugins.stt_plugin import STTInputPlugin  # noqa: F401

__all__ = [
    "StandardTextInputPlugin",
    "STTInputPlugin",
    "A2AInboundPlugin",
    "MCPInputPlugin",
]
