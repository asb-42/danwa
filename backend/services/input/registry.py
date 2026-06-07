"""InputPluginRegistry — singleton registry for input plugins.

Plugins self-register via the :func:`register_input_plugin` class
decorator.  The registry is populated at import time when the ``plugins``
subpackage is imported.
"""

from __future__ import annotations

import logging

from backend.services.input.base import InputPlugin

logger = logging.getLogger(__name__)


class InputPluginRegistry:
    """Singleton registry that maps input plugin keys to plugin classes.

    Usage::

        registry = InputPluginRegistry.instance()
        registry.register(MyPlugin)
        plugin = registry.get_plugin("my_key")
    """

    _instance: InputPluginRegistry | None = None
    _plugins: dict[str, type[InputPlugin]]

    def __init__(self) -> None:
        """Initialise InputPluginRegistry."""
        self._plugins = {}

    @classmethod
    def instance(cls) -> InputPluginRegistry:
        """Return the singleton instance, creating it if necessary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (primarily for testing)."""
        cls._instance = None

    def register(self, plugin_class: type[InputPlugin]) -> None:
        """Register a plugin class.

        Args:
            plugin_class: A subclass of :class:`InputPlugin`.

        Raises:
            ValueError: If a plugin with the same key is already registered.
        """
        key = plugin_class.plugin_key
        if key in self._plugins:
            raise ValueError(
                f"Input plugin with key {key!r} is already registered ({self._plugins[key].__name__}). Cannot register {plugin_class.__name__}."
            )
        self._plugins[key] = plugin_class
        logger.info("Input plugin registered: %s (%s)", key, plugin_class.plugin_name)

    def get_plugin(self, key: str) -> type[InputPlugin]:
        """Return the plugin class for *key*.

        Args:
            key: The plugin key (e.g. ``"standard_text"``).

        Returns:
            The registered plugin class.

        Raises:
            KeyError: If no plugin is registered with *key*.
        """
        if key not in self._plugins:
            available = ", ".join(sorted(self._plugins.keys())) or "(none)"
            raise KeyError(f"No input plugin registered with key {key!r}. Available plugins: {available}")
        return self._plugins[key]

    def list_plugins(self) -> list[type[InputPlugin]]:
        """Return all registered plugin classes, sorted by key."""
        return [self._plugins[k] for k in sorted(self._plugins.keys())]

    def has_plugin(self, key: str) -> bool:
        """Return ``True`` if a plugin with *key* is registered."""
        return key in self._plugins


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def register_input_plugin(cls: type[InputPlugin]) -> type[InputPlugin]:
    """Class decorator that registers an ``InputPlugin`` with the registry.

    Usage::

        @register_input_plugin
        class MyPlugin(InputPlugin):
            plugin_key = "my_key"
            ...
    """
    InputPluginRegistry.instance().register(cls)
    return cls
