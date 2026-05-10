"""InputPlugin — abstract base class for input capture plugins.

All input plugins must subclass ``InputPlugin`` and implement the
:meth:`capture` method.  Plugins are registered via the
:func:`register_input_plugin` decorator from
:mod:`backend.services.input.registry`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel

from backend.models.debate_input import DebateInput


class InputPlugin(ABC):
    """Abstract base for all input capture plugins.

    **Stateless contract:** Plugins MUST be stateless — no instance state
    may be persisted between ``capture()`` calls.  Each ``capture()``
    invocation is independent and receives all context it needs via
    parameters.

    Subclasses must define the three ``ClassVar`` attributes below and
    implement :meth:`capture`.
    """

    plugin_key: ClassVar[str]
    """Unique identifier for this plugin (e.g. ``"standard_text"``, ``"stt"``)."""

    plugin_name: ClassVar[str]
    """Human-readable display name for UI."""

    config_schema: ClassVar[type[BaseModel]]
    """Pydantic model that defines the plugin-specific configuration schema."""

    @abstractmethod
    async def capture(self, config: BaseModel) -> DebateInput:
        """Capture or transform raw input into a standardized ``DebateInput``.

        Args:
            config: Validated plugin-specific configuration
                (instance of :attr:`config_schema`).

        Returns:
            A standardized ``DebateInput`` artifact.
        """
        ...

    async def validate(self, config: BaseModel) -> bool:
        """Check if the plugin is operational.

        Override to verify model availability, endpoint reachability, etc.
        Default returns ``True``.

        Args:
            config: Validated plugin-specific configuration.

        Returns:
            ``True`` if the plugin is ready to use.
        """
        return True

    @classmethod
    def validate_config(cls, config: dict) -> BaseModel:
        """Validate a raw config dictionary against :attr:`config_schema`.

        Args:
            config: Raw configuration dictionary.

        Returns:
            Validated config as an instance of :attr:`config_schema`.

        Raises:
            pydantic.ValidationError: If the config is invalid.
        """
        return cls.config_schema.model_validate(config)

    @classmethod
    def config_json_schema(cls) -> dict:
        """Return the JSON Schema for :attr:`config_schema`.

        Useful for dynamic form generation in the frontend.
        """
        return cls.config_schema.model_json_schema()

    def get_ui_hints(self) -> dict:
        """Return frontend metadata for this plugin.

        Override to provide hints like ``requires_microphone``,
        ``supports_streaming``, ``is_available``, etc.

        Returns:
            Dictionary of UI hints.  Default returns empty dict.
        """
        return {}
