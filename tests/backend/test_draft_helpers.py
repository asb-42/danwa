"""Tests for Sprint 39 (H2 fix) — shared tail-only truncation of the
``current_draft`` running log.

The helper is the single source of truth for the bound; the
agent, interjection, and legacy ``run_agent_node`` accumulators
all call it.  These tests cover the helper itself, the contract
it advertises, and a smoke test that the three call sites apply
the bound consistently.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.workflow.nodes._draft_helpers import (
    MAX_RUNNING_DRAFT_LEN,
    RUNNING_DRAFT_TRUNCATION_MARKER,
    truncate_running_draft,
)

# ---------------------------------------------------------------------------
# Helper unit tests
# ---------------------------------------------------------------------------


class TestTruncateRunningDraft:
    """``truncate_running_draft`` is a pure function: same input
    → same output, no I/O.  Tail-only — keeps the last
    ``max_len`` characters and prepends a marker when truncation
    fires.
    """

    def test_short_text_returned_unchanged(self) -> None:
        text = "hello world"
        assert truncate_running_draft(text) == "hello world"

    def test_empty_text_returned_unchanged(self) -> None:
        assert truncate_running_draft("") == ""

    def test_text_at_exact_limit_returned_unchanged(self) -> None:
        text = "a" * MAX_RUNNING_DRAFT_LEN
        assert truncate_running_draft(text) == text

    def test_text_over_limit_truncated_tail_only(self) -> None:
        """When the input exceeds ``max_len`` the helper
        returns the last ``max_len - len(marker)`` chars,
        prepended with the marker.  The head is dropped.
        """
        # Use a distinct character for the head so we can
        # verify it was dropped (a long run of "a"s is
        # ambiguous with the tail when the input is a single
        # repeated char).
        text = "HEAD" + "a" * (MAX_RUNNING_DRAFT_LEN + 100) + "TAIL"
        result = truncate_running_draft(text)
        assert result.startswith(RUNNING_DRAFT_TRUNCATION_MARKER)
        # The original "HEAD" prefix is gone — head was dropped.
        assert "HEAD" not in result
        # The "TAIL" suffix must be preserved.
        assert result.endswith("TAIL")
        # Tail is exactly the last (max_len - marker) chars of
        # the original input.
        expected_tail = text[-(MAX_RUNNING_DRAFT_LEN - len(RUNNING_DRAFT_TRUNCATION_MARKER)) :]
        assert result.endswith(expected_tail)
        # Total length is at most max_len.
        assert len(result) <= MAX_RUNNING_DRAFT_LEN

    def test_marker_appears_only_when_truncation_fires(self) -> None:
        """The marker is prepended only when the input is
        truncated.  Short text is returned verbatim, without
        a marker.
        """
        short = "just a few words"
        assert RUNNING_DRAFT_TRUNCATION_MARKER not in truncate_running_draft(short)
        long = "x" * (MAX_RUNNING_DRAFT_LEN + 1)
        assert RUNNING_DRAFT_TRUNCATION_MARKER in truncate_running_draft(long)

    def test_custom_max_len(self) -> None:
        text = "abcdefghij" * 10  # 100 chars
        # max_len > len(text) → no truncation, returned verbatim.
        result = truncate_running_draft(text, max_len=200)
        assert result == text
        # max_len < len(text) → truncated; tail preserved, head
        # dropped.  Use a short marker so max_len=20 is workable.
        result = truncate_running_draft("HEAD" + text + "TAIL", max_len=20, marker="[..]")
        assert "HEAD" not in result
        assert result.endswith("TAIL")
        assert len(result) <= 20

    def test_custom_marker_appears_when_truncated(self) -> None:
        text = "x" * 100
        result = truncate_running_draft(text, max_len=50, marker="[..]")
        assert result.startswith("[..]")
        # Total length is at most 50 (marker is 5 chars, so 45
        # tail chars).
        assert len(result) <= 50

    def test_max_len_too_small_raises(self) -> None:
        """If ``max_len < len(marker) + 1`` the helper cannot
        produce a meaningful output (the marker alone would
        already exceed the cap).  Raise ``ValueError`` rather
        than silently returning a wrong-sized string.
        """
        with pytest.raises(ValueError, match="max_len"):
            truncate_running_draft("hello", max_len=2, marker="[trunc]")

    def test_max_len_equal_marker_length_raises(self) -> None:
        """The helper needs at least one character of tail
        after the marker, so ``max_len == len(marker)`` is
        also rejected.
        """
        with pytest.raises(ValueError, match="max_len"):
            truncate_running_draft("hello", max_len=7, marker="[trunc]")

    def test_preserves_unicode_codepoints(self) -> None:
        """Truncation operates on Python ``str`` codepoints,
        not bytes.  Multi-byte UTF-8 sequences (e.g. German
        umlauts) must not be split mid-codepoint.
        """
        text = "ä" * (MAX_RUNNING_DRAFT_LEN + 50)
        result = truncate_running_draft(text)
        # Every char in the result is a valid ``ä`` codepoint
        # (or part of the marker).
        for ch in result:
            assert ch == "ä" or ch in RUNNING_DRAFT_TRUNCATION_MARKER
        assert len(result) <= MAX_RUNNING_DRAFT_LEN


# ---------------------------------------------------------------------------
# Integration: the three accumulators use the same bound
# ---------------------------------------------------------------------------


class TestAccumulatorSitesUseSharedHelper:
    """``agent_nodes._agent_node``, ``system_nodes.interjection_node``,
    and ``legacy_nodes.run_agent_node`` all accumulate into
    ``current_draft`` and must call the shared helper so the
    bound is applied uniformly.  These tests exercise each
    call site independently with a draft that exceeds the cap.
    """

    @pytest.mark.asyncio
    async def test_agent_node_truncates_when_oversized(self) -> None:
        """The wf-compiler agent factory's non-transactional
        branch concatenates and then truncates.  A long
        existing draft must come out bounded to
        ``MAX_RUNNING_DRAFT_LEN``.
        """
        from backend.workflow.nodes.agent_nodes import agent_node_factory

        # Long existing draft forces truncation on the very
        # first agent output.
        long_prefix = "x" * (MAX_RUNNING_DRAFT_LEN + 5000)
        config = {
            "blueprint_name": "Test",
            "llm_profile_id": "prof-1",
            "llm_model": "gpt-4",
            "role_definition_id": "role-1",
            "role": "strategist",
            "node_config": {"template": "{{context}}"},
        }
        state = {
            "current_draft": long_prefix,
            "current_round": 1,
            "context": "topic",
            "language": "de",
            "workflow_template": "non_transactional",  # takes the concat branch
            "node_outputs": [],
            "interjection_queue": [],
            "session_id": "s",
            "node_id": "n1",
        }
        node_fn = agent_node_factory("node-s1", "wf-strategist", config)

        with (
            patch("backend.workflow.node_functions._get_profile_service") as mock_ps,
            patch(
                "backend.workflow.nodes.agent_nodes.publish_async",
                new_callable=AsyncMock,
            ),
        ):
            mock_ps.return_value = AsyncMock()
            result = await node_fn(state)

        assert "current_draft" in result
        assert len(result["current_draft"]) <= MAX_RUNNING_DRAFT_LEN

    @pytest.mark.asyncio
    async def test_interjection_node_truncates_when_oversized(self) -> None:
        """``system_nodes.interjection_node`` previously
        accumulated without any cap.  It now applies the
        shared helper, so a long existing draft comes out
        bounded.
        """
        from backend.workflow.nodes.system_nodes import interjection_node

        long_prefix = "y" * (MAX_RUNNING_DRAFT_LEN + 5000)
        state = {
            "current_draft": long_prefix,
            "interjection_queue": [
                {"id": "inj-1", "content": "User note"},
            ],
            "consumed_interjections": [],
            "session_id": "s",
            "node_id": "interjection",
        }

        with (
            patch("backend.workflow.audit_logger.get_audit_logger") as mock_al,
            patch(
                "backend.workflow.nodes.system_nodes.publish_async",
                new_callable=AsyncMock,
            ),
        ):
            mock_al.return_value = AsyncMock()
            result = await interjection_node(state)

        assert "current_draft" in result
        assert len(result["current_draft"]) <= MAX_RUNNING_DRAFT_LEN
        # The user note (the new content) is at the tail.
        assert "User note" in result["current_draft"]

    @pytest.mark.asyncio
    async def test_legacy_run_agent_truncates_when_oversized(self) -> None:
        """``legacy_nodes.run_agent_node`` previously
        accumulated without any cap.  It now applies the
        shared helper.
        """
        from backend.workflow.legacy_nodes import run_agent_node

        long_prefix = "z" * (MAX_RUNNING_DRAFT_LEN + 5000)
        state = {
            "current_draft": long_prefix,
            "current_round": 1,
            "context": "topic",
            "language": "de",
            "session_id": "s",
            "node_id": "n1",
            "current_agent_index": 0,
            "agent_profile": [
                {"role": "strategist", "llm_profile_id": "prof-1"},
            ],
            "agent_outputs": [],
            "interjection_queue": [],
            "node_outputs": [],
            "messages": [],
        }

        with (
            patch("backend.workflow.legacy_nodes.LLMService") as mock_llm,
            patch(
                "backend.workflow.legacy_nodes.publish_async",
                new_callable=AsyncMock,
            ),
        ):
            mock_instance = mock_llm.return_value
            mock_instance.generate = AsyncMock(
                return_value=AsyncMock(
                    content="new content",
                    llm_profile_id="prof-1",
                    model_used="gpt-4",
                    tokens_out=2,
                    latency_ms=10,
                    failed=False,
                    anomaly_detail="",
                )
            )
            result = await run_agent_node(state)

        assert "current_draft" in result
        assert len(result["current_draft"]) <= MAX_RUNNING_DRAFT_LEN
        # The new content is at the tail.
        assert result["current_draft"].endswith("new content")
