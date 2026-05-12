"""Tests for Phase 8 Group G — A2A Payload Translator."""

from __future__ import annotations

from backend.a2a.payload_translator import translate_from_a2a, translate_to_a2a


class TestTranslateToA2A:
    def test_basic_messages(self):
        messages = [
            {"role": "system", "content": "You are a strategist."},
            {"role": "user", "content": "Analyze this."},
        ]
        result = translate_to_a2a(messages)
        assert "You are a strategist" in result
        assert "Analyze this" in result

    def test_with_context(self):
        messages = [{"role": "user", "content": "Task"}]
        result = translate_to_a2a(messages, context="Case text", role="critic", round_num=2)
        assert "Case text" in result
        assert "critic" in result
        assert "round 2" in result.lower() or "Round 2" in result

    def test_with_previous_outputs(self):
        messages = []
        result = translate_to_a2a(
            messages,
            previous_outputs=[{"role": "strategist", "content": "Analysis"}],
        )
        assert "strategist" in result
        assert "Analysis" in result

    def test_empty_messages(self):
        result = translate_to_a2a([], round_num=0)
        assert result == ""


class TestTranslateFromA2A:
    def test_from_artifacts(self):
        result = {"artifacts": [{"parts": [{"type": "text", "text": "Hello world"}]}]}
        translated = translate_from_a2a(result)
        assert translated["content"] == "Hello world"
        assert translated["tokens_out"] > 0

    def test_from_result_string(self):
        result = {"result": "Direct text"}
        translated = translate_from_a2a(result)
        assert translated["content"] == "Direct text"

    def test_from_result_dict(self):
        result = {"result": {"text": "Dict text"}}
        translated = translate_from_a2a(result)
        assert translated["content"] == "Dict text"

    def test_empty_result(self):
        result = {}
        translated = translate_from_a2a(result)
        assert translated["content"] == ""
        assert translated["tokens_out"] == 0

    def test_returns_expected_keys(self):
        result = {"artifacts": []}
        translated = translate_from_a2a(result)
        assert "content" in translated
        assert "tokens_in" in translated
        assert "tokens_out" in translated
        assert "duration_ms" in translated
        assert "model" in translated
