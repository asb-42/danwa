"""Output plugins — auto-registration on import.

Importing this package triggers the ``@register_plugin`` decorator on
each plugin class, populating the :class:`PluginRegistry` singleton.
"""

from backend.services.output.plugins.print_plugin import PrintOutputPlugin  # noqa: F401
from backend.services.output.plugins.tts_plugin import TTSOutputPlugin  # noqa: F401

__all__ = ["PrintOutputPlugin", "TTSOutputPlugin"]
