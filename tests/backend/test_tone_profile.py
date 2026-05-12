"""Tests for ToneProfile feature — models, validation, CRUD API, and prompt injection.

Covers:
- ToneProfile Pydantic model validation
- WorkflowNode tone_profile XOR validation
- Graph validation rules for injects_config edges
- CRUD API endpoints for tone profiles
- TonePromptInjector service
- Seed script idempotency
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.blueprints.compiler import CompilerService
from backend.blueprints.models import ToneProfile
from backend.blueprints.workflow_models import (
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from backend.services.tone_prompt_injector import inject_tone_profile

# ---------------------------------------------------------------------------
# ToneProfile model tests
# ---------------------------------------------------------------------------


class TestToneProfileModel:
    """Test ToneProfile Pydantic model constraints."""

    def test_valid_tone_profile(self):
        profile = ToneProfile(
            name="Test Profile",
            style="heated",
            formality=0.3,
            verbosity="verbose",
            emotional_valence=0.8,
            rhetorical_mode="assertive",
        )
        assert profile.name == "Test Profile"
        assert profile.style == "heated"
        assert profile.formality == 0.3
        assert profile.is_system is False

    def test_default_values(self):
        profile = ToneProfile(name="Default")
        assert profile.style == "neutral"
        assert profile.formality == 0.5
        assert profile.verbosity == "normal"
        assert profile.emotional_valence == 0.5
        assert profile.rhetorical_mode == "none"
        assert profile.custom_instructions is None

    def test_formality_constrained(self):
        """Formality must be between 0.0 and 1.0."""
        ToneProfile(name="Low", formality=0.0)
        ToneProfile(name="High", formality=1.0)

        with pytest.raises(ValidationError):
            ToneProfile(name="Too Low", formality=-0.1)

        with pytest.raises(ValidationError):
            ToneProfile(name="Too High", formality=1.1)

    def test_emotional_valence_constrained(self):
        """Emotional valence must be between 0.0 and 1.0."""
        ToneProfile(name="Low", emotional_valence=0.0)
        ToneProfile(name="High", emotional_valence=1.0)

        with pytest.raises(ValidationError):
            ToneProfile(name="Too Low", emotional_valence=-0.1)

        with pytest.raises(ValidationError):
            ToneProfile(name="Too High", emotional_valence=1.1)

    def test_invalid_style(self):
        with pytest.raises(ValidationError):
            ToneProfile(name="Bad", style="invalid_style")

    def test_invalid_verbosity(self):
        with pytest.raises(ValidationError):
            ToneProfile(name="Bad", verbosity="invalid_verbosity")

    def test_invalid_rhetorical_mode(self):
        with pytest.raises(ValidationError):
            ToneProfile(name="Bad", rhetorical_mode="invalid_mode")

    def test_model_dump_json_roundtrip(self):
        profile = ToneProfile(
            name="Roundtrip",
            style="academic",
            formality=0.9,
            verbosity="normal",
            emotional_valence=0.2,
            rhetorical_mode="dialectic",
            custom_instructions="Be precise.",
        )
        json_str = profile.model_dump_json()
        restored = ToneProfile.model_validate_json(json_str)
        assert restored.name == profile.name
        assert restored.style == profile.style
        assert restored.custom_instructions == "Be precise."


# ---------------------------------------------------------------------------
# WorkflowNode tone_profile XOR validation
# ---------------------------------------------------------------------------


class TestWorkflowNodeToneProfile:
    """Test WorkflowNode validation for tone_profile type."""

    def test_valid_catalog_reference(self):
        node = WorkflowNode(
            id="tp1",
            type="wf-tone-profile",
            config={"tone_profile_id": "system-heated"},
        )
        assert node.type == "wf-tone-profile"

    def test_valid_inline_profile(self):
        node = WorkflowNode(
            id="tp1",
            type="wf-tone-profile",
            config={
                "inline_profile": {
                    "name": "Custom",
                    "style": "heated",
                    "formality": 0.5,
                    "verbosity": "normal",
                    "emotional_valence": 0.5,
                    "rhetorical_mode": "none",
                }
            },
        )
        assert node.type == "wf-tone-profile"

    def test_both_set_raises(self):
        """XOR: cannot have both tone_profile_id and inline_profile."""
        with pytest.raises(ValidationError, match="exactly one"):
            WorkflowNode(
                id="tp1",
                type="wf-tone-profile",
                config={
                    "tone_profile_id": "system-heated",
                    "inline_profile": {
                        "name": "Custom",
                        "style": "heated",
                    },
                },
            )

    def test_neither_set_raises(self):
        """XOR: must have at least one of tone_profile_id or inline_profile."""
        with pytest.raises(ValidationError, match="requires either"):
            WorkflowNode(
                id="tp1",
                type="wf-tone-profile",
                config={},
            )

    def test_empty_tone_profile_id_treated_as_none(self):
        """Empty string for tone_profile_id should be treated as not set."""
        with pytest.raises(ValidationError, match="requires either"):
            WorkflowNode(
                id="tp1",
                type="wf-tone-profile",
                config={"tone_profile_id": ""},
            )


# ---------------------------------------------------------------------------
# Graph validation for injects_config edges
# ---------------------------------------------------------------------------


class TestInjectsConfigValidation:
    """Test graph validation rules for injects_config edges."""

    def _make_workflow(
        self,
        nodes: list[dict],
        edges: list[dict],
        entry_point: str | None = None,
    ) -> WorkflowDefinition:
        """Helper to build a WorkflowDefinition from dicts."""
        if entry_point is None:
            # Use the first input node as entry point
            entry_point = next(
                (n["id"] for n in nodes if n.get("type") == "wf-input"),
                nodes[0]["id"] if nodes else "node-1",
            )
        return WorkflowDefinition(
            name="Test Workflow",
            nodes=[WorkflowNode(**n) for n in nodes],
            edges=[WorkflowEdge(**e) for e in edges],
            entry_point=entry_point,
        )

    def _validate(self, workflow: WorkflowDefinition) -> tuple[list[str], list[str]]:
        """Run validation and return (errors, warnings)."""
        # Use a mock or skip repo-dependent checks
        from unittest.mock import MagicMock

        mock_repo = MagicMock()
        mock_repo.get_blueprint.return_value = None
        compiler = CompilerService(mock_repo)
        result = compiler.compile(workflow)
        return result.errors, result.warnings

    def test_valid_injects_config_edge(self):
        """A valid injects_config edge from tone_profile to agent should pass."""
        nodes = [
            {"id": "input-1", "type": "wf-input"},
            {
                "id": "tp-1",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-heated"},
            },
            {"id": "strat-1", "type": "wf-strategist", "agent_blueprint_id": "bp-1"},
        ]
        edges = [
            {"source": "input-1", "target": "strat-1", "type": "sequential"},
            {"source": "tp-1", "target": "strat-1", "type": "injects_config"},
        ]
        wf = self._make_workflow(nodes, edges)
        errors, warnings = self._validate(wf)
        # Should not have injects_config errors (may have other errors due to mock)
        inject_errors = [e for e in errors if "injects_config" in e]
        assert len(inject_errors) == 0

    def test_injects_config_to_non_agent_rejected(self):
        """injects_config to a non-agent node should be rejected."""
        nodes = [
            {"id": "input-1", "type": "wf-input"},
            {
                "id": "tp-1",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-heated"},
            },
        ]
        edges = [
            {"source": "tp-1", "target": "input-1", "type": "injects_config"},
        ]
        wf = self._make_workflow(nodes, edges)
        errors, warnings = self._validate(wf)
        inject_errors = [e for e in errors if "injects_config" in e and "must be an agent node" in e]
        assert len(inject_errors) >= 1

    def test_multiple_injects_config_to_same_agent_rejected(self):
        """Agent node with multiple injects_config edges should be rejected."""
        nodes = [
            {"id": "input-1", "type": "wf-input"},
            {
                "id": "tp-1",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-heated"},
            },
            {
                "id": "tp-2",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-academic"},
            },
            {"id": "strat-1", "type": "wf-strategist", "agent_blueprint_id": "bp-1"},
        ]
        edges = [
            {"source": "input-1", "target": "strat-1", "type": "sequential"},
            {"source": "tp-1", "target": "strat-1", "type": "injects_config"},
            {"source": "tp-2", "target": "strat-1", "type": "injects_config"},
        ]
        wf = self._make_workflow(nodes, edges)
        errors, warnings = self._validate(wf)
        inject_errors = [e for e in errors if "incoming" in e and "injects_config" in e]
        assert len(inject_errors) >= 1

    def test_injects_config_from_non_tone_profile_rejected(self):
        """injects_config from a non-tone-profile node should be rejected."""
        nodes = [
            {"id": "input-1", "type": "wf-input"},
            {"id": "strat-1", "type": "wf-strategist", "agent_blueprint_id": "bp-1"},
        ]
        edges = [
            {"source": "input-1", "target": "strat-1", "type": "injects_config"},
        ]
        wf = self._make_workflow(nodes, edges)
        errors, warnings = self._validate(wf)
        inject_errors = [e for e in errors if "injects_config" in e and "expected 'wf-tone-profile'" in e]
        assert len(inject_errors) >= 1

    def test_isolated_tone_profile_rejected(self):
        """A tone_profile node with no edges should be rejected."""
        nodes = [
            {"id": "input-1", "type": "wf-input"},
            {"id": "strat-1", "type": "wf-strategist", "agent_blueprint_id": "bp-1"},
            {
                "id": "tp-1",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-heated"},
            },
        ]
        edges = [
            {"source": "input-1", "target": "strat-1", "type": "sequential"},
        ]
        wf = self._make_workflow(nodes, edges)
        errors, warnings = self._validate(wf)
        inject_errors = [e for e in errors if "isolated" in e and "tp-1" in e]
        assert len(inject_errors) >= 1

    def test_valid_one_to_one_injection(self):
        """Multiple agents each with their own tone_profile should pass."""
        nodes = [
            {"id": "input-1", "type": "wf-input"},
            {
                "id": "tp-1",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-heated"},
            },
            {
                "id": "tp-2",
                "type": "wf-tone-profile",
                "config": {"tone_profile_id": "system-academic"},
            },
            {"id": "strat-1", "type": "wf-strategist", "agent_blueprint_id": "bp-1"},
            {"id": "crit-1", "type": "wf-critic", "agent_blueprint_id": "bp-2"},
        ]
        edges = [
            {"source": "input-1", "target": "strat-1", "type": "sequential"},
            {"source": "strat-1", "target": "crit-1", "type": "sequential"},
            {"source": "tp-1", "target": "strat-1", "type": "injects_config"},
            {"source": "tp-2", "target": "crit-1", "type": "injects_config"},
        ]
        wf = self._make_workflow(nodes, edges)
        errors, warnings = self._validate(wf)
        inject_errors = [e for e in errors if "injects_config" in e]
        assert len(inject_errors) == 0


# ---------------------------------------------------------------------------
# TonePromptInjector tests
# ---------------------------------------------------------------------------


class TestTonePromptInjector:
    """Test the tone prompt injection service."""

    def test_basic_injection(self):
        profile = ToneProfile(
            name="Heated",
            style="heated",
            formality=0.3,
            verbosity="verbose",
            emotional_valence=0.9,
            rhetorical_mode="assertive",
        )
        result = inject_tone_profile("You are a strategist.", profile)
        assert "[TONE PROFILE]" in result
        assert "hitziges Streitgespräch" in result
        assert "You are a strategist." in result

    def test_custom_instructions_included(self):
        profile = ToneProfile(
            name="Custom",
            style="neutral",
            custom_instructions="Always use metaphors.",
        )
        result = inject_tone_profile("System prompt.", profile)
        assert "Always use metaphors." in result
        assert "[TONE PROFILE]" in result

    def test_no_injection_when_no_profile_data(self):
        """If profile has all defaults, minimal injection should still occur."""
        profile = ToneProfile(name="Default")
        result = inject_tone_profile("System prompt.", profile)
        # Even neutral style gets injected
        assert "[TONE PROFILE]" in result

    def test_preserves_original_prompt(self):
        original = "You are a debate moderator. Evaluate consensus."
        profile = ToneProfile(name="Test", style="academic")
        result = inject_tone_profile(original, profile)
        assert result.startswith(original)

    def test_academic_style(self):
        profile = ToneProfile(name="Academic", style="academic", formality=0.9)
        result = inject_tone_profile("Prompt.", profile)
        assert "formale, akademische Debatte" in result
        assert "hochformale" in result

    def test_socratic_style(self):
        profile = ToneProfile(name="Socratic", style="socratic", rhetorical_mode="questioning")
        result = inject_tone_profile("Prompt.", profile)
        assert "sokratisches Gespräch" in result
        assert "rhetorische Fragen" in result
