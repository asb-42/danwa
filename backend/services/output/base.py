"""OutputPlugin — abstract base class for output rendering plugins.

All output plugins must subclass ``OutputPlugin`` and implement the
:meth:`render` method.  Plugins are registered via the
:func:`register_plugin` decorator from :mod:`backend.services.output.registry`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel

from backend.models.artifact import DebateArtifact


class OutputPlugin(ABC):
    """Abstract base for all output rendering plugins.

    **Stateless contract:** Plugins MUST be stateless — no instance state
    may be persisted between ``render()`` calls.  Each ``render()``
    invocation is independent and receives all context it needs via
    parameters.  Implementations should use fresh helper/engine instances
    per call rather than storing them on ``self``.

    Subclasses must define the four ``ClassVar`` attributes below and
    implement :meth:`render`.
    """

    plugin_key: ClassVar[str]
    """Unique identifier for this plugin (e.g. ``"print"``, ``"tts"``)."""

    plugin_name: ClassVar[str]
    """Human-readable display name for UI (e.g. ``"Print / PDF / DOCX"``)."""

    supported_formats: ClassVar[list[str]]
    """Output formats this plugin can produce (e.g. ``["pdf", "docx"]``)."""

    config_schema: ClassVar[type[BaseModel]]
    """Pydantic model that defines the plugin-specific configuration schema."""

    @abstractmethod
    async def render(
        self,
        artifact: DebateArtifact,
        config: BaseModel,
        job_id: str,
        output_dir: Path,
    ) -> list[Path]:
        """Render the artifact to one or more output files.

        Args:
            artifact: The debate artifact to render.
            config: Validated plugin-specific configuration
                (instance of :attr:`config_schema`).
            job_id: Unique render job identifier.  Output files should
                be placed in ``output_dir / job_id /``.
            output_dir: Root output directory.  The implementation must
                create ``output_dir / job_id /`` if it does not exist.

        Returns:
            List of paths to the generated output files.
        """
        ...

    @classmethod
    def validate_config(cls, config: dict) -> BaseModel:
        """Validate a raw config dictionary against :attr:`config_schema`.

        Args:
            config: Raw configuration dictionary (e.g. from API request body).

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
