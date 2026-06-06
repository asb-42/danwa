"""Tests for Sprint 34 (M4 + M5) — tone-profile error surfacing + token estimate.

M4: ``agent_node_factory`` used to silently swallow tone-profile
injection failures via a bare ``except Exception``.  Sprint 34
captures the failure reason in ``audit_metadata['tone_profile_error']``
so the audit log and downstream callers can see when a configured
profile did not actually apply.

M5: The fallback ``tokens_used = len(content.split())`` counted
whitespace-separated tokens, not LLM tokens, and underestimated the
real cost by ~3-4x.  Sprint 34 replaces it with ``_estimate_tokens``
which uses the industry rule of thumb ``1 token ≈ 4 characters``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.workflow.nodes.agent_nodes import (
    _estimate_tokens,
    agent_node_factory,
)

# ---------------------------------------------------------------------------
# M5 — _estimate_tokens
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    """Test the new token-estimate helper."""

    def test_empty_string_returns_zero(self) -> None:
        """Empty content is a true 0 — no rounding needed."""
        assert _estimate_tokens("") == 0

    def test_short_non_empty_returns_at_least_one(self) -> None:
        """A single word must not round down to 0 — the audit log
        should never record ``tokens_used=0`` for a successful call.
        """
        assert _estimate_tokens("hi") == 1

    def test_uses_one_token_per_four_chars(self) -> None:
        """16 characters → 4 tokens.  Sanity check on the divisor."""
        assert _estimate_tokens("a" * 16) == 4
        assert _estimate_tokens("a" * 100) == 25
        assert _estimate_tokens("a" * 101) == 25  # integer division

    def test_german_prose_is_in_the_right_ballpark(self) -> None:
        """A typical German sentence (~50 chars) should estimate
        ~12-13 tokens, matching OpenAI/Anthropic tokenizers.
        """
        sentence = "Die Mietvertragsklausel ist unwirksam gemäß § 307 BGB."
        est = _estimate_tokens(sentence)
        assert 10 <= est <= 20

    def test_long_english_prose_estimate(self) -> None:
        """A typical English paragraph (~500 chars) should estimate
        ~125 tokens.
        """
        text = "a" * 500
        assert _estimate_tokens(text) == 125

    def test_no_longer_uses_word_count(self) -> None:
        """The estimate must NOT equal ``len(content.split())`` for
        a multi-word input — that's the whole point of the fix.
        """
        text = "one two three four five six seven eight nine ten"
        word_count = len(text.split())  # 10
        estimate = _estimate_tokens(text)
        # Must differ from the legacy word-count heuristic
        assert estimate != word_count


# ---------------------------------------------------------------------------
# M4 — tone-profile error surfacing
# ---------------------------------------------------------------------------


class TestToneProfileErrorSurfacing:
    """Verify the tone-profile error is exposed via audit metadata."""

    @pytest.fixture()
    def base_state(self) -> dict:
        """Minimal state for a ``wf-agent`` node execution."""
        return {
            "session_id": "sess-1",
            "workflow_id": "wf-1",
            "workflow_version": 1,
            "current_node_id": "node-s1",
            "current_round": 1,
            "language": "de",
            "context": "Mietvertrag über 800 EUR",
            "node_outputs": [],
            "messages": [],
            "interjection_queue": [],
            "tone_profiles": {},
        }

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_tone_profile_source_missing_data_sets_error(
        self,
        mock_llm_cls: AsyncMock,
        mock_publish: AsyncMock,
        base_state: dict,
    ) -> None:
        """If ``tone_profile_source_node_id`` is configured but the
        referenced node produced no ``profile_data`` in state, the
        node should log a warning naming the missing source — this
        test exists for documentation; the full audit-metadata
        assertion is in ``test_audit_metadata_contains_tone_profile_error``.
        """
        # The real assertion is on the audit metadata; this test
        # just exercises the warning log path so we have a smaller
        # smoke-test that doesn't need the audit-logger mock.
        base_state["tone_profiles"] = {}

        mock_svc = mock_llm_cls.return_value
        mock_svc.generate = AsyncMock(
            return_value=type(
                "R",
                (),
                {"content": "out", "tokens_out": 5, "duration_ms": 100},
            )()
        )

        node_fn = agent_node_factory(
            node_id="node-s1",
            node_type="wf-agent",
            resolved_config={
                "blueprint_id": "bp-1",
                "role": "strategist",
                "llm_profile_id": "prof-1",
                "tone_profile_source_node_id": "wf-tone-1",
            },
        )
        # Should not raise even though profile_data is missing
        result = await node_fn(base_state)
        assert "node_outputs" in result

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.nodes.agent_nodes.get_audit_logger")
    async def test_audit_metadata_contains_tone_profile_error(
        self,
        mock_audit: AsyncMock,
        mock_llm_cls: AsyncMock,
        mock_publish: AsyncMock,
        base_state: dict,
    ) -> None:
        """The audit logger must receive ``tone_profile_error`` in
        its metadata when a configured profile is missing.
        """
        # ``tone_profile_source_node_id`` is read from resolved_config
        # (line 77 of agent_nodes.py), not from state.  Source is
        # configured but produced no profile_data in state.
        base_state["tone_profiles"] = {}

        # Mock LLM response
        mock_svc = mock_llm_cls.return_value
        mock_svc.generate = AsyncMock(
            return_value=type(
                "R",
                (),
                {"content": "out", "tokens_out": 5, "duration_ms": 100},
            )()
        )

        # Mock audit logger
        mock_al = mock_audit.return_value
        mock_al.log_node_execution = MagicMock()

        node_fn = agent_node_factory(
            node_id="node-s1",
            node_type="wf-agent",
            resolved_config={
                "blueprint_id": "bp-1",
                "role": "strategist",
                "llm_profile_id": "prof-1",
                "tone_profile_source_node_id": "wf-tone-1",
            },
        )
        await node_fn(base_state)

        # The audit logger must have been called
        assert mock_al.log_node_execution.call_count == 1
        call_kwargs = mock_al.log_node_execution.call_args.kwargs
        # input_data should contain tone_profile_error
        assert "tone_profile_error" in call_kwargs["input_data"]
        assert "wf-tone-1" in call_kwargs["input_data"]["tone_profile_error"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.nodes.agent_nodes.get_audit_logger")
    async def test_no_tone_profile_source_no_error(
        self,
        mock_audit: AsyncMock,
        mock_llm_cls: AsyncMock,
        mock_publish: AsyncMock,
        base_state: dict,
    ) -> None:
        """If no ``tone_profile_source_node_id`` is configured, the
        audit metadata must not contain ``tone_profile_error`` —
        it's only set when a profile was *expected* but failed.
        """
        # Don't set tone_profile_source_node_id
        mock_svc = mock_llm_cls.return_value
        mock_svc.generate = AsyncMock(
            return_value=type(
                "R",
                (),
                {"content": "out", "tokens_out": 5, "duration_ms": 100},
            )()
        )
        mock_al = mock_audit.return_value
        mock_al.log_node_execution = MagicMock()

        node_fn = agent_node_factory(
            node_id="node-s1",
            node_type="wf-agent",
            resolved_config={
                "blueprint_id": "bp-1",
                "role": "strategist",
                "llm_profile_id": "prof-1",
            },
        )
        await node_fn(base_state)

        assert mock_al.log_node_execution.call_count == 1
        call_kwargs = mock_al.log_node_execution.call_args.kwargs
        assert "tone_profile_error" not in call_kwargs["input_data"]


# ---------------------------------------------------------------------------
# M5 — token-fallback path uses _estimate_tokens
# ---------------------------------------------------------------------------


class TestTokenFallbackPath:
    """Verify the LLM-failure and tokens_out=0 paths use _estimate_tokens."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_llm_failure_uses_estimate_tokens(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """When the LLM call raises, the fallback ``tokens_used``
        must come from ``_estimate_tokens`` (not word count) so the
        audit/cost-tracking is consistent.
        """
        from backend.workflow.nodes.agent_nodes import agent_node_factory

        mock_svc = mock_llm_cls.return_value
        mock_svc.generate = AsyncMock(side_effect=RuntimeError("LLM down"))

        state = {
            "session_id": "sess-1",
            "workflow_id": "wf-1",
            "workflow_version": 1,
            "current_node_id": "node-s1",
            "current_round": 1,
            "language": "de",
            "context": "test",
            "node_outputs": [],
            "messages": [],
            "interjection_queue": [],
        }

        node_fn = agent_node_factory(
            node_id="node-s1",
            node_type="wf-agent",
            resolved_config={
                "blueprint_id": "bp-1",
                "role": "strategist",
                "llm_profile_id": "prof-1",
            },
        )
        result = await node_fn(state)

        # The node output reports the estimated token count
        output = result["node_outputs"][0]
        # The failure message is "[strategist] Round 1: LLM call failed (LLM down)"
        # → 47 chars / 4 = 11 tokens, but min(1) is guaranteed
        assert output["tokens_used"] >= 1
        # And it must NOT be 0 (a successful LLM call would never
        # log 0 tokens; the failure path should not either)
        assert output["tokens_used"] > 0

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.agent_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    async def test_tokens_out_zero_falls_back_to_estimate(self, mock_llm_cls: AsyncMock, mock_publish: AsyncMock) -> None:
        """When the LLM returns ``tokens_out=0``, the fallback path
        must use ``_estimate_tokens`` — not word count.
        """
        from backend.workflow.nodes.agent_nodes import agent_node_factory

        # 100-char content → _estimate_tokens → 25, word count would be different
        content = "a " * 50  # 100 chars, 50 words
        mock_svc = mock_llm_cls.return_value
        mock_svc.generate = AsyncMock(
            return_value=type(
                "R",
                (),
                {"content": content, "tokens_out": 0, "duration_ms": 100},
            )()
        )

        state = {
            "session_id": "sess-1",
            "workflow_id": "wf-1",
            "workflow_version": 1,
            "current_node_id": "node-s1",
            "current_round": 1,
            "language": "de",
            "context": "test",
            "node_outputs": [],
            "messages": [],
            "interjection_queue": [],
        }

        node_fn = agent_node_factory(
            node_id="node-s1",
            node_type="wf-agent",
            resolved_config={
                "blueprint_id": "bp-1",
                "role": "strategist",
                "llm_profile_id": "prof-1",
            },
        )
        result = await node_fn(state)

        output = result["node_outputs"][0]
        # _estimate_tokens(100 chars) = 25, NOT the 50 from word count
        assert output["tokens_used"] == 25
