"""Tests for InputPluginRegistry and InputPlugin contract."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel

from backend.models.debate_input import DebateInput
from backend.services.input.base import InputPlugin
from backend.services.input.registry import InputPluginRegistry, register_input_plugin

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class DummyInputConfig(BaseModel):
    placeholder: str = "default"


class DummyInputPlugin(InputPlugin):
    plugin_key: ClassVar[str] = "dummy_input"
    plugin_name: ClassVar[str] = "Dummy Input"
    config_schema: ClassVar[type[BaseModel]] = DummyInputConfig

    async def capture(self, config):
        return DebateInput(source_plugin_key="dummy_input", topic="test")


@pytest.fixture(autouse=True)
def _isolated_registry():
    """Save and restore the real registry around each test."""
    real_instance = InputPluginRegistry.instance()
    real_plugins = dict(real_instance._plugins)
    InputPluginRegistry.reset()
    yield
    # Restore the real singleton with all registered plugins
    InputPluginRegistry._instance = real_instance
    real_instance._plugins = real_plugins


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInputPluginRegistry:
    def test_singleton(self) -> None:
        r1 = InputPluginRegistry.instance()
        r2 = InputPluginRegistry.instance()
        assert r1 is r2

    def test_register_and_get(self) -> None:
        registry = InputPluginRegistry.instance()
        registry.register(DummyInputPlugin)
        assert registry.get_plugin("dummy_input") is DummyInputPlugin

    def test_get_unknown_raises(self) -> None:
        registry = InputPluginRegistry.instance()
        with pytest.raises(KeyError, match="nonexistent"):
            registry.get_plugin("nonexistent")

    def test_list_empty(self) -> None:
        registry = InputPluginRegistry.instance()
        assert registry.list_plugins() == []

    def test_list_after_register(self) -> None:
        registry = InputPluginRegistry.instance()
        registry.register(DummyInputPlugin)
        plugins = registry.list_plugins()
        assert len(plugins) == 1
        assert plugins[0] is DummyInputPlugin

    def test_has_plugin(self) -> None:
        registry = InputPluginRegistry.instance()
        assert not registry.has_plugin("dummy_input")
        registry.register(DummyInputPlugin)
        assert registry.has_plugin("dummy_input")

    def test_duplicate_register_raises(self) -> None:
        registry = InputPluginRegistry.instance()
        registry.register(DummyInputPlugin)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(DummyInputPlugin)


class TestRegisterInputPluginDecorator:
    def test_decorator_registers(self) -> None:
        @register_input_plugin
        class DecoratedPlugin(InputPlugin):
            plugin_key: ClassVar[str] = "decorated_input"
            plugin_name: ClassVar[str] = "Decorated Input"
            config_schema: ClassVar[type[BaseModel]] = DummyInputConfig

            async def capture(self, config):
                return DebateInput(source_plugin_key="decorated_input", topic="test")

        registry = InputPluginRegistry.instance()
        assert registry.has_plugin("decorated_input")
        assert registry.get_plugin("decorated_input") is DecoratedPlugin


class TestInputPluginContract:
    def test_validate_config_valid(self) -> None:
        config = DummyInputPlugin.validate_config({"placeholder": "custom"})
        assert isinstance(config, DummyInputConfig)
        assert config.placeholder == "custom"

    def test_validate_config_default(self) -> None:
        config = DummyInputPlugin.validate_config({})
        assert config.placeholder == "default"

    def test_config_json_schema(self) -> None:
        schema = DummyInputPlugin.config_json_schema()
        assert "properties" in schema
        assert "placeholder" in schema["properties"]

    def test_get_ui_hints_default(self) -> None:
        plugin = DummyInputPlugin()
        hints = plugin.get_ui_hints()
        assert hints == {}  # default empty
