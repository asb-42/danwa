"""Tests for PluginRegistry and OutputPlugin contract."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel

from backend.services.output.base import OutputPlugin
from backend.services.output.registry import PluginRegistry, register_plugin

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class DummyConfig(BaseModel):
    option: str = "default"


class DummyPlugin(OutputPlugin):
    plugin_key: ClassVar[str] = "dummy"
    plugin_name: ClassVar[str] = "Dummy Plugin"
    supported_formats: ClassVar[list[str]] = ["txt"]
    config_schema: ClassVar[type[BaseModel]] = DummyConfig

    async def render(self, artifact, config, job_id, output_dir):
        return []


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the singleton registry before each test."""
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPluginRegistry:
    def test_singleton(self) -> None:
        r1 = PluginRegistry.instance()
        r2 = PluginRegistry.instance()
        assert r1 is r2

    def test_register_and_get(self) -> None:
        registry = PluginRegistry.instance()
        registry.register(DummyPlugin)
        assert registry.get_plugin("dummy") is DummyPlugin

    def test_get_unknown_raises(self) -> None:
        registry = PluginRegistry.instance()
        with pytest.raises(KeyError, match="nonexistent"):
            registry.get_plugin("nonexistent")

    def test_list_empty(self) -> None:
        registry = PluginRegistry.instance()
        assert registry.list_plugins() == []

    def test_list_after_register(self) -> None:
        registry = PluginRegistry.instance()
        registry.register(DummyPlugin)
        plugins = registry.list_plugins()
        assert len(plugins) == 1
        assert plugins[0] is DummyPlugin

    def test_has_plugin(self) -> None:
        registry = PluginRegistry.instance()
        assert not registry.has_plugin("dummy")
        registry.register(DummyPlugin)
        assert registry.has_plugin("dummy")

    def test_duplicate_register_raises(self) -> None:
        """Registering a *different* class with the same key still raises.

        Re-registering the *same* class is now an idempotent no-op (useful
        when test runners re-import the plugin module), so this test
        constructs a second plugin class that differs from ``DummyPlugin``
        but uses the same ``plugin_key`` to assert the guard fires.
        """

        class _OtherDummyPlugin(OutputPlugin):
            plugin_key: ClassVar[str] = "dummy"  # same as DummyPlugin
            plugin_name: ClassVar[str] = "Other Dummy"
            supported_formats: ClassVar[list[str]] = ["txt"]
            config_schema: ClassVar[type[BaseModel]] = DummyConfig

            async def render(self, artifact, config, job_id, output_dir):
                return []

        registry = PluginRegistry.instance()
        registry.register(DummyPlugin)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_OtherDummyPlugin)


class TestRegisterPluginDecorator:
    def test_decorator_registers(self) -> None:
        @register_plugin
        class DecoratedPlugin(OutputPlugin):
            plugin_key: ClassVar[str] = "decorated"
            plugin_name: ClassVar[str] = "Decorated"
            supported_formats: ClassVar[list[str]] = ["pdf"]
            config_schema: ClassVar[type[BaseModel]] = DummyConfig

            async def render(self, artifact, config, job_id, output_dir):
                return []

        registry = PluginRegistry.instance()
        assert registry.has_plugin("decorated")
        assert registry.get_plugin("decorated") is DecoratedPlugin


class TestOutputPluginContract:
    def test_validate_config_valid(self) -> None:
        config = DummyPlugin.validate_config({"option": "custom"})
        assert isinstance(config, DummyConfig)
        assert config.option == "custom"

    def test_validate_config_default(self) -> None:
        config = DummyPlugin.validate_config({})
        assert config.option == "default"

    def test_config_json_schema(self) -> None:
        schema = DummyPlugin.config_json_schema()
        assert "properties" in schema
        assert "option" in schema["properties"]
