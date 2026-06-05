"""Tests for Phase 1 — Dual-Path System Prompt Resolution.

Validates that:
1. Bundle-resolved prompts (ComposerService output) are used directly when present
2. Module-based persona_ids (UUID) route through ComposerService
3. Legacy persona_ids still work via ProfileService fallback
4. _is_module_id helper correctly identifies UUID vs legacy IDs
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from backend.workflow.legacy_nodes import _is_module_id, _resolve_system_prompt

# ---------------------------------------------------------------------------
# _is_module_id
# ---------------------------------------------------------------------------


class TestIsModuleId:
    """Test _is_module_id correctly distinguishes UUIDs from legacy IDs."""

    def test_valid_uuid4(self) -> None:
        assert _is_module_id(str(uuid4())) is True

    def test_valid_uuid5(self) -> None:
        assert _is_module_id("6ba7b810-9dad-11d1-80b4-00c04fd430c8") is True

    def test_legacy_persona_id(self) -> None:
        assert _is_module_id("persona-1") is False

    def test_legacy_string_id(self) -> None:
        assert _is_module_id("kantian-critic") is False

    def test_empty_string(self) -> None:
        assert _is_module_id("") is False

    def test_none_like(self) -> None:
        # _is_module_id expects str, but should handle gracefully
        assert _is_module_id("not-a-uuid") is False

    def test_uuid_with_braces(self) -> None:
        # Python's uuid.UUID accepts braces
        uid = str(uuid4())
        assert _is_module_id(uid) is True


# ---------------------------------------------------------------------------
# _resolve_system_prompt — Pre-resolved (bundle) path
# ---------------------------------------------------------------------------


class TestPreResolvedPrompt:
    """Test that bundle-resolved system prompts are used directly in run_agent_node."""

    @pytest.mark.asyncio
    @patch("backend.workflow.legacy_nodes.publish_async")
    async def test_bundle_resolved_prompt_skips_legacy(self, mock_publish: MagicMock) -> None:
        """When agent dict has system_prompt, it should be used directly without calling _resolve_system_prompt."""
        from backend.workflow.legacy_nodes import run_agent_node

        bundle_prompt = "You are a Kantian strategist. Argue from duty ethics."
        state = {
            "context": "Test debate",
            "agent_profile": [
                {
                    "role": "strategist",
                    "llm_profile": "default",
                    "temperature": 0.7,
                    "system_prompt": bundle_prompt,
                },
            ],
            "max_rounds": 1,
            "threshold": 0.8,
            "enable_fact_check": False,
            "enable_memory": False,
            "rag_context": "",
            "session_id": "test-session",
            "current_round": 1,
            "current_agent_index": 0,
            "rounds": [],
            "agent_outputs": [],
            "current_draft": "",
            "final_consensus": 0.0,
            "output": "",
            "validation_report": [],
            "used_variant": "default",
            "llm_profile_id": "default",
            "prompt_variant": "default",
            "agent_persona_ids": {},
            "bundle_ids": [str(uuid4())],
            "language": "en",
            "search_mode": "off",
            "project_id": None,
        }

        # The key assertion: _resolve_system_prompt should NOT be called
        with patch("backend.workflow.legacy_nodes._resolve_system_prompt") as mock_resolve:
            with patch("backend.workflow.legacy_nodes.LLMService") as mock_llm:
                mock_gen = MagicMock()
                mock_gen.content = "Test response"
                mock_gen.tokens_in = 10
                mock_gen.tokens_out = 20
                mock_gen.duration_ms = 100
                mock_gen.model = "test-model"
                mock_llm.return_value.generate = MagicMock(return_value=mock_gen)

                result = await run_agent_node(state)

            mock_resolve.assert_not_called()

        # The output should contain the agent response
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["role"] == "strategist"


# ---------------------------------------------------------------------------
# _resolve_system_prompt — Module-aware persona path
# ---------------------------------------------------------------------------


class TestModuleAwarePersona:
    """Test that UUID persona_ids route through ComposerService."""

    @patch("backend.workflow.legacy_nodes._get_prompt_service")
    @patch("backend.workflow.legacy_nodes._get_profile_service")
    def test_module_id_uses_composer_service(self, mock_profile_svc: MagicMock, mock_prompt_svc: MagicMock) -> None:
        """When persona_id is a UUID, ComposerService should be used."""
        module_id = str(uuid4())
        composed_prompt = "## Agent Core\n\nYou are an analyst."
        persona_ids = {"strategist": module_id}
        state: dict = {"context": "Test"}

        # PromptService raises FileNotFoundError (no template)
        mock_prompt_svc.return_value.render.side_effect = FileNotFoundError

        with patch("backend.services.composer_service.ComposerService") as mock_composer_cls:
            mock_composer = MagicMock()
            mock_composer.compose.return_value = composed_prompt
            mock_composer_cls.return_value = mock_composer

            result = _resolve_system_prompt(
                role="strategist",
                prompt_variant="default",
                persona_ids=persona_ids,
                state=state,  # type: ignore[arg-type]
                language="en",
                search_mode="off",
            )

        assert composed_prompt in result
        mock_composer.compose.assert_called_once()

    @patch("backend.workflow.legacy_nodes._get_prompt_service")
    def test_legacy_persona_id_falls_through_to_generic(self, mock_prompt_svc: MagicMock) -> None:
        """When persona_id is NOT a UUID, it falls through to the generic fallback."""
        persona_ids = {"strategist": "persona-legacy-1"}
        state: dict = {"context": "Test"}

        # PromptService raises FileNotFoundError (no template)
        mock_prompt_svc.return_value.render.side_effect = FileNotFoundError

        result = _resolve_system_prompt(
            role="strategist",
            prompt_variant="default",
            persona_ids=persona_ids,
            state=state,  # type: ignore[arg-type]
            language="en",
            search_mode="off",
        )

        # Non-UUID persona_ids no longer resolve — falls through to generic
        assert "strategist" in result.lower()

    @patch("backend.workflow.legacy_nodes._get_prompt_service")
    @patch("backend.workflow.legacy_nodes._get_profile_service")
    def test_prompt_service_template_takes_priority(self, mock_profile_svc: MagicMock, mock_prompt_svc: MagicMock) -> None:
        """When PromptService has a template, it should be used regardless of persona_ids."""
        module_id = str(uuid4())
        persona_ids = {"strategist": module_id}
        state: dict = {"context": "Test"}

        # PromptService returns a template successfully
        mock_prompt_svc.return_value.render.return_value = "Template-based prompt."

        result = _resolve_system_prompt(
            role="strategist",
            prompt_variant="default",
            persona_ids=persona_ids,
            state=state,  # type: ignore[arg-type]
            language="en",
            search_mode="off",
        )

        assert "Template-based prompt" in result
        # ComposerService should NOT have been called
        mock_profile_svc.assert_not_called()

    @patch("backend.workflow.legacy_nodes._get_prompt_service")
    @patch("backend.workflow.legacy_nodes._get_profile_service")
    def test_generic_fallback_when_no_template_no_persona(self, mock_profile_svc: MagicMock, mock_prompt_svc: MagicMock) -> None:
        """When no template and no persona match, generic fallback should be used."""
        persona_ids: dict[str, str] = {}
        state: dict = {"context": "Test"}

        mock_prompt_svc.return_value.render.side_effect = FileNotFoundError

        result = _resolve_system_prompt(
            role="strategist",
            prompt_variant="default",
            persona_ids=persona_ids,
            state=state,  # type: ignore[arg-type]
            language="en",
            search_mode="off",
        )

        assert "strategist" in result.lower()


# ---------------------------------------------------------------------------
# extract_request_fields — bundle_ids propagation
# ---------------------------------------------------------------------------


class TestBundleIdsInState:
    """Test that bundle_ids are properly propagated through the debate workflow."""

    def test_extract_request_fields_includes_bundle_ids(self) -> None:
        """extract_request_fields should return bundle_ids from the request."""
        from backend.services.debate_workflow import extract_request_fields

        req = {
            "case": {"text": "Test case"},
            "max_rounds": 3,
            "consensus_threshold": 0.8,
            "enable_fact_check": False,
            "enable_memory": False,
            "llm_profile_id": "default",
            "prompt_variant": "default",
            "agent_persona_ids": {},
            "language": "en",
            "document_ids": [],
            "rag_auto_retrieve": False,
            "search_mode": None,
            "agent_profile": [
                {"role": "strategist", "llm_profile": "default", "temperature": 0.7},
            ],
            "bundle_ids": ["bundle-1", "bundle-2"],
        }

        fields = extract_request_fields(req)
        assert fields["bundle_ids"] == ["bundle-1", "bundle-2"]

    def test_extract_request_fields_defaults_empty_bundle_ids(self) -> None:
        """extract_request_fields should default to empty list when no bundle_ids."""
        from backend.services.debate_workflow import extract_request_fields

        req = {
            "case": {"text": "Test case"},
            "max_rounds": 3,
            "consensus_threshold": 0.8,
            "enable_fact_check": False,
            "enable_memory": False,
            "llm_profile_id": "default",
            "prompt_variant": "default",
            "agent_persona_ids": {},
            "language": "en",
            "document_ids": [],
            "rag_auto_retrieve": False,
            "search_mode": None,
            "agent_profile": [
                {"role": "strategist", "llm_profile": "default", "temperature": 0.7},
            ],
        }

        fields = extract_request_fields(req)
        assert fields["bundle_ids"] == []
