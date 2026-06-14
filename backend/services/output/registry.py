"""PluginRegistry — singleton registry for output plugins.

Plugins self-register via the :func:`register_plugin` class decorator.
The registry is populated at import time when the ``plugins`` subpackage
is imported.
"""

from __future__ import annotations

import logging

from backend.services.output.base import OutputPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """Singleton registry that maps plugin keys to plugin classes.

    Usage::

        registry = PluginRegistry.instance()
        registry.register(MyPlugin)
        plugin = registry.get_plugin("my_key")
    """

    _instance: PluginRegistry | None = None
    _plugins: dict[str, type[OutputPlugin]]

    def __init__(self) -> None:
        """Initialise PluginRegistry."""
        self._plugins = {}

    @classmethod
    def instance(cls) -> PluginRegistry:
        """Return the singleton instance, creating it if necessary."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (primarily for testing)."""
        cls._instance = None

    def register(self, plugin_class: type[OutputPlugin]) -> None:
        """Register a plugin class.

        Idempotent for the same fully-qualified class identity: re-registering
        a class with the same ``__module__ + __qualname__`` is treated as the
        same plugin and is a no-op. Registering a *different* class with the
        same key still raises ``ValueError``.

        Args:
            plugin_class: A subclass of :class:`OutputPlugin` with
                ``plugin_key`` defined as a ``ClassVar[str]``.

        Raises:
            ValueError: If a *different* plugin with the same key is
                already registered.
        """
        key = plugin_class.plugin_key
        new_identity = f"{plugin_class.__module__}.{plugin_class.__qualname__}"
        if key in self._plugins:
            existing = self._plugins[key]
            existing_identity = f"{existing.__module__}.{existing.__qualname__}"
            if existing_identity == new_identity:
                # Idempotent re-registration (e.g. coverage re-imports the
                # module and re-runs the decorator on a new class object
                # that represents the same logical plugin).
                return
            raise ValueError(f"Plugin with key {key!r} is already registered ({existing.__name__}). Cannot register {plugin_class.__name__}.")
        self._plugins[key] = plugin_class
        logger.info("Output plugin registered: %s (%s)", key, plugin_class.plugin_name)

    def get_plugin(self, key: str) -> type[OutputPlugin]:
        """Return the plugin class for *key*.

        Args:
            key: The plugin key (e.g. ``"print"``).

        Returns:
            The registered plugin class.

        Raises:
            KeyError: If no plugin is registered with *key*.
        """
        if key not in self._plugins:
            available = ", ".join(sorted(self._plugins.keys())) or "(none)"
            raise KeyError(f"No output plugin registered with key {key!r}. Available plugins: {available}")
        return self._plugins[key]

    def list_plugins(self) -> list[type[OutputPlugin]]:
        """Return all registered plugin classes, sorted by key."""
        return [self._plugins[k] for k in sorted(self._plugins.keys())]

    def has_plugin(self, key: str) -> bool:
        """Return ``True`` if a plugin with *key* is registered."""
        return key in self._plugins


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------


def register_plugin(cls: type[OutputPlugin]) -> type[OutputPlugin]:
    """Class decorator that registers an ``OutputPlugin`` with the registry.

    Usage::

        @register_plugin
        class MyPlugin(OutputPlugin):
            plugin_key = "my_key"
            ...
    """
    PluginRegistry.instance().register(cls)
    return cls
