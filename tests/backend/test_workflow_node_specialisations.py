"""Tests for ``backend/workflow/nodes/{builder,moderator,pragmatist,angels_advocate,system}_nodes``.

This single file collects focused tests for the five P2.9 workflow node
modules.  Together they raise the per-file coverage from ~10–13 % to
>=75 %.

Coverage targets (from ``reports/2026-06-12_test-coverage-analysis.md``):
- backend/workflow/nodes/builder_nodes.py            10% → 70%+
- backend/workflow/nodes/moderator_nodes.py          12% → 70%+
- backend/workflow/nodes/pragmatist_nodes.py         13% → 70%+
- backend/workflow/nodes/angels_advocate_nodes.py    12% → 70%+
- backend/workflow/nodes/system_nodes.py             12% → 70%+

The tests follow the patterns already established in
``tests/backend/test_workflow_nodes.py`` and
``tests/backend/test_transactional_drafting.py`` — patching
``publish_async``, ``LLMService``, ``get_audit_logger``, and
``_get_profile_service`` to drive the factory closures without
external I/O.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.workflow.workflow_state import WorkflowState, WorkflowTemplate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> WorkflowState:
    """Build a minimal ``WorkflowState`` dict for testing."""
    base: dict = {
        "workflow_id": "wf-test",
        "session_id": "sess-test",
        "project_id": "default",
        "context": "Test case context",
        "language": "de",
        "node_sequence": ["wf-input"],
        "node_configs": {},
        "edge_map": {},
        "termination_conditions": [],
        "current_node_id": "wf-input",
        "current_round": 1,
        "max_rounds": 10,
        "threshold": 0.7,
        "node_outputs": [],
        "messages": [],
        "current_draft": "",
        "interjection_queue": [],
        "consumed_interjections": [],
        "final_consensus": 0.0,
        "output": "",
        "status": "running",
        "is_paused": False,
    }
    base.update(overrides)
    return base  # type: ignore[return-value]


def _fake_llm_result(content: str, tokens_out: int = 10, duration_ms: int = 50) -> MagicMock:
    r = MagicMock()
    r.content = content
    r.tokens_out = tokens_out
    r.duration_ms = duration_ms
    return r


_VALID_CRITIC_ITEM: dict = {
    "critic_id": "c-test-001",
    "severity": "blocking",
    "target": "§1",
    "flaw": "f",
    "principle": "p",
    "context_quote": "q",
}


def _build_response_a() -> dict:
    """Return a valid ``BuildResponse`` dict for the Builder LLM payload."""
    return {
        "response_to": "c-test-001",
        "option_a": "conservative fix",
        "option_b": "radical fix",
        "option_c": None,
        "recommendation": "option_a",
        "rationale": "r",
        "risk_assessment": "low",
        "implementable": True,
    }


def _pragmatist_evaluation() -> dict:
    return {
        "response_to": "c-test-001",
        "feasibility": 0.8,
        "process_risk": "low",
        "cost_time_estimate": "1h",
        "verdict": "accept",
        "revision_note": "ok",
    }


def _aa_valid_payload() -> str:
    return json.dumps(
        {
            "preserved_elements": [
                {
                    "element_id": "aa-001",
                    "preserved_text": "T",
                    "source_location": "§1",
                    "rationale": "important",
                    "priority": "important",
                }
            ],
            "overall_stability_score": 0.8,
        }
    )


def _pragmatist_valid_payload() -> str:
    return json.dumps(
        {
            "evaluations": [_pragmatist_evaluation()],
            "reality_score": 0.8,
            "blocking_concerns": [],
        }
    )


def _builder_valid_payload(with_global: bool = True) -> str:
    obj = {
        "build_responses": [_build_response_a()],
        "constructivity_score": 0.0,
    }
    if with_global:
        obj["global_revision"] = "G"
    return json.dumps(obj)


# ===========================================================================
# system_nodes.py
# ===========================================================================


class TestInputNode:
    """``input_node`` — no LLM call."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_returns_context(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import input_node

        mock_al.return_value = MagicMock()
        result = await input_node(_make_state(context="hello world"))
        assert result["current_draft"] == "hello world"
        assert result["node_outputs"][0]["content"] == "hello world"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_truncates_to_200_chars(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import input_node

        mock_al.return_value = MagicMock()
        long_text = "x" * 500
        result = await input_node(_make_state(context=long_text))
        # Truncation in the publish event only (not in current_draft)
        events = [c.args[2] for c in mock_publish.call_args_list]
        complete = [e for e in events if e.get("content")]
        assert len(complete[0]["content"]) == 200
        assert result["current_draft"] == long_text

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_audit_logger_called(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import input_node

        al = MagicMock()
        mock_al.return_value = al
        await input_node(_make_state())
        al.log_node_execution.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_audit_failure_is_swallowed(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import input_node

        al = MagicMock()
        al.log_node_execution = MagicMock(side_effect=Exception("audit broken"))
        mock_al.return_value = al
        # The audit log call is wrapped in a try/except — must not raise
        result = await input_node(_make_state())
        assert result["current_draft"] == "Test case context"


class TestInitializeWfNode:
    """``initialize_wf_node`` — resets runtime state."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_resets_state(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import initialize_wf_node

        mock_al.return_value = MagicMock()
        result = await initialize_wf_node(_make_state(current_round=5, current_draft="old", final_consensus=0.9))
        assert result["current_round"] == 1
        assert result["current_draft"] == ""
        assert result["final_consensus"] == 0.0
        assert result["output"] == ""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_publishes_two_events(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import initialize_wf_node

        mock_al.return_value = MagicMock()
        await initialize_wf_node(_make_state())
        assert mock_publish.call_count == 2


class TestCompleteWfNode:
    """``complete_wf_node`` — assembles final output and publishes."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_assembles_from_node_outputs(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import complete_wf_node

        mock_al.return_value = MagicMock()
        state = _make_state(
            node_outputs=[
                {"role": "strategist", "round": 1, "content": "Strategy text"},
                {"role": "critic", "round": 1, "content": "Critique"},
            ],
            current_draft="ignored",
        )
        result = await complete_wf_node(state)
        assert "[STRATEGIST Round 1]" in result["output"]
        assert "Strategy text" in result["output"]
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_falls_back_to_current_draft(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import complete_wf_node

        mock_al.return_value = MagicMock()
        state = _make_state(node_outputs=[], current_draft="plain text")
        result = await complete_wf_node(state)
        assert result["output"] == "plain text"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_includes_td_fields(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import complete_wf_node

        mock_al.return_value = MagicMock()
        state = _make_state(
            node_outputs=[],
            consensus_result={"verdict": "approved", "reality_score": 0.8},
            constructivity_score=0.75,
            draft_version=2,
            pragmatist_output={"reality_score": 0.8, "blocking_concerns": []},
        )
        result = await complete_wf_node(state)
        assert result["consensus_result"]["verdict"] == "approved"
        assert result["constructivity_score"] == 0.75
        assert result["draft_version"] == 2
        assert result["reality_score"] == 0.8

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_omits_td_fields_when_not_set(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import complete_wf_node

        mock_al.return_value = MagicMock()
        # constructivity_score default is 0.0, draft_version default 1 — neither
        # is "carries data", so the result must NOT include the TD fields.
        state = _make_state(node_outputs=[], current_draft="x")
        result = await complete_wf_node(state)
        assert "consensus_result" not in result
        assert "constructivity_score" not in result
        assert "draft_version" not in result

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_publishes_workflow_complete(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import complete_wf_node

        mock_al.return_value = MagicMock()
        await complete_wf_node(_make_state())
        events = [c.args[1] for c in mock_publish.call_args_list]
        assert "workflow.complete" in events


class TestInterjectionNode:
    """``interjection_node`` — drains queues, optionally blocks, or pauses."""

    @pytest.fixture(autouse=True)
    def _isolate_interjection_service(self) -> Generator[None, None, None]:
        """Make ``interjection_service.consume`` deterministic for these tests.

        The ``interjection_service`` is a process-wide singleton backed by
        an in-memory queue *and* a SQLite table (``data/blueprints.db``).
        If a previous test (or a parallel test worker) left an item in
        the queue for ``"sess-test"``, the SQLite-backed
        ``_ensure_loaded`` re-hydrates it on the next call and
        ``interjection_node`` takes the *drain* path — the
        ``test_empty_queue_pauses`` assertion ``result["is_paused"] is True``
        would then fail with ``KeyError: 'is_paused'``.

        We patch the two service methods that ``interjection_node``
        uses to read state with ``AsyncMock`` returning an empty list
        for any session id, so neither ``consume`` nor
        ``consume_blocking`` can return a leftover item.  Tests that
        seed via the *in-state* ``interjection_queue`` (the drain
        tests) keep their current observable behaviour because they
        never exercise ``interjection_service``.

        CI-history: this test was flaky in run ``<previous-CI-run>`` and
        the fix preserves the existing test contract (no API changes
        in production code).
        """
        from unittest.mock import patch as _patch

        from backend.workflow.interjection import interjection_service

        pcm = _patch.object(
            interjection_service,
            "consume",
            new_callable=AsyncMock,
            return_value=[],
        )
        pcm_blocking = _patch.object(
            interjection_service,
            "consume_blocking",
            new_callable=AsyncMock,
            return_value=[],
        )
        pcm.start()
        pcm_blocking.start()
        try:
            yield
        finally:
            pcm.stop()
            pcm_blocking.stop()

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_empty_queue_pauses(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import interjection_node

        mock_al.return_value = MagicMock()
        result = await interjection_node(_make_state(interjection_queue=[]))
        assert result["is_paused"] is True
        assert result["node_outputs"][0]["status"] == "pending"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_in_state_queue_drained(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import interjection_node

        mock_al.return_value = MagicMock()
        state = _make_state(
            interjection_queue=[
                {"id": "i-1", "content": "first note"},
                {"id": "i-2", "content": "second note"},
            ]
        )
        result = await interjection_node(state)
        assert "is_paused" not in result
        assert result["interjection_queue"] == []
        assert result["consumed_interjections"] == ["i-1", "i-2"]
        assert "first note" in result["node_outputs"][0]["content"]
        assert "second note" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.system_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.system_nodes.get_audit_logger")
    async def test_appends_to_draft(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.system_nodes import interjection_node

        mock_al.return_value = MagicMock()
        state = _make_state(
            current_draft="Existing",
            interjection_queue=[{"id": "i-1", "content": "user note"}],
        )
        result = await interjection_node(state)
        assert "Existing" in result["current_draft"]
        assert "user note" in result["current_draft"]


# ===========================================================================
# angels_advocate_nodes.py
# ===========================================================================


class TestExtractZeroDraftAA:
    """``angels_advocate_nodes._extract_zero_draft`` — prefer zero_draft."""

    def test_prefers_zero_draft(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_zero_draft

        assert _extract_zero_draft({"zero_draft": "Z", "context": "C"}) == "Z"

    def test_falls_back_to_strategist_node_output(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_zero_draft

        assert _extract_zero_draft({"node_outputs": [{"node_type": "wf-strategist", "content": "S"}], "context": "C"}) == "S"

    def test_final_fallback_to_context(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_zero_draft

        assert _extract_zero_draft({"context": "C"}) == "C"

    def test_no_zero_draft_falls_through(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_zero_draft

        assert _extract_zero_draft({"zero_draft": None, "context": "C"}) == "C"


class TestExtractCriticItemsAA:
    """``angels_advocate_nodes._extract_critic_items`` — JSON from critic node."""

    def test_uses_critic_items_field(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_critic_items

        items = [{"a": 1}]
        assert _extract_critic_items({"critic_items": items}) == items

    def test_parses_json_from_node_outputs(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_critic_items

        items = [{"a": 1}]
        state = {
            "critic_items": [],
            "node_outputs": [{"node_type": "wf-critic", "content": json.dumps(items)}],
        }
        assert _extract_critic_items(state) == items

    def test_strips_markdown_fence(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_critic_items

        items = [{"a": 1}]
        state = {
            "critic_items": [],
            "node_outputs": [{"node_type": "wf-critic", "content": "```json\n" + json.dumps(items) + "\n```"}],
        }
        assert _extract_critic_items(state) == items

    def test_returns_empty_on_broken(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_critic_items

        state = {
            "critic_items": [],
            "node_outputs": [{"node_type": "wf-critic", "content": "not json"}],
        }
        assert _extract_critic_items(state) == []

    def test_skips_empty_content(self) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import _extract_critic_items

        state = {
            "critic_items": [],
            "node_outputs": [{"node_type": "wf-critic", "content": ""}],
        }
        assert _extract_critic_items(state) == []


class TestAngelsAdvocateNodeFactory:
    """``angels_advocate_node_factory`` — full LLM-driven flow."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.angels_advocate_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.angels_advocate_nodes.get_audit_logger")
    async def test_no_inputs_returns_placeholder(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import angels_advocate_node_factory

        mock_al.return_value = MagicMock()
        node_fn = angels_advocate_node_factory("node-aa", {"role": "angels-advocate"})
        result = await node_fn(_make_state(context="", zero_draft="", critic_items=[], node_outputs=[]))
        assert result["preserved_elements"] == []
        assert "No draft or critique available" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.angels_advocate_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.angels_advocate_nodes.LLMService")
    @patch("backend.workflow.nodes.angels_advocate_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.angels_advocate_nodes._get_profile_service")
    async def test_llm_success(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import angels_advocate_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result(_aa_valid_payload()))
        mock_llm_cls.return_value = llm

        node_fn = angels_advocate_node_factory("node-aa", {"role": "angels-advocate"})
        result = await node_fn(_make_state(zero_draft="Z", critic_items=[_VALID_CRITIC_ITEM]))
        assert result["stability_score"] == 0.8
        assert len(result["preserved_elements"]) == 1

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.angels_advocate_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.angels_advocate_nodes.LLMService")
    @patch("backend.workflow.nodes.angels_advocate_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.angels_advocate_nodes._get_profile_service")
    async def test_json_repair_rescues(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes import angels_advocate_nodes as aa_mod

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        # Missing closing brace — only the json_repair fallback can fix it
        llm.generate = AsyncMock(return_value=_fake_llm_result("{" + _aa_valid_payload()))
        mock_llm_cls.return_value = llm

        # Mock json_repair to be importable and to fix the missing brace
        fake_repair_module = MagicMock()
        fake_repair_module.repair_json = MagicMock(return_value=_aa_valid_payload())
        import sys

        sys.modules["json_repair"] = fake_repair_module
        try:
            # Force the lazy import inside the node to pick up our mock
            if hasattr(aa_mod, "json_repair"):
                aa_mod.json_repair = fake_repair_module

            node_fn = aa_mod.angels_advocate_node_factory("node-aa", {"role": "angels-advocate"})
            result = await node_fn(_make_state(zero_draft="Z", critic_items=[_VALID_CRITIC_ITEM]))
            assert len(result["preserved_elements"]) == 1
        finally:
            sys.modules.pop("json_repair", None)
            if hasattr(aa_mod, "json_repair"):
                delattr(aa_mod, "json_repair")

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.angels_advocate_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.angels_advocate_nodes.LLMService")
    @patch("backend.workflow.nodes.angels_advocate_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.angels_advocate_nodes._get_profile_service")
    async def test_all_retries_fail(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import angels_advocate_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("not json at all"))
        mock_llm_cls.return_value = llm

        node_fn = angels_advocate_node_factory("node-aa", {"role": "angels-advocate"})
        result = await node_fn(_make_state(zero_draft="Z", critic_items=[_VALID_CRITIC_ITEM]))
        # All retries fail: status="failed" but preserved elements is empty list
        assert result["node_outputs"][0]["status"] == "failed"
        assert result["preserved_elements"] == []
        assert result["stability_score"] == 0.0
        # Audit logger should have been called with log_node_failed
        mock_al.return_value.log_node_failed.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.angels_advocate_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.angels_advocate_nodes.LLMService")
    @patch("backend.workflow.nodes.angels_advocate_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.angels_advocate_nodes._get_profile_service")
    async def test_llm_service_raises(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import angels_advocate_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=Exception("LLM down"))
        mock_llm_cls.return_value = llm

        node_fn = angels_advocate_node_factory("node-aa", {"role": "angels-advocate"})
        result = await node_fn(_make_state(zero_draft="Z", critic_items=[_VALID_CRITIC_ITEM]))
        assert result["node_outputs"][0]["status"] == "failed"
        assert "LLM call failed" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.angels_advocate_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.angels_advocate_nodes.LLMService")
    @patch("backend.workflow.nodes.angels_advocate_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.angels_advocate_nodes._get_profile_service")
    async def test_list_payload_wrapped_in_dict(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.angels_advocate_nodes import angels_advocate_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        list_payload = json.dumps(
            [
                {
                    "element_id": "aa-001",
                    "preserved_text": "T",
                    "source_location": "§1",
                    "rationale": "important",
                    "priority": "important",
                }
            ]
        )
        llm.generate = AsyncMock(return_value=_fake_llm_result(list_payload))
        mock_llm_cls.return_value = llm

        node_fn = angels_advocate_node_factory("node-aa", {"role": "angels-advocate"})
        result = await node_fn(_make_state(zero_draft="Z", critic_items=[_VALID_CRITIC_ITEM]))
        # Default stability_score is 0.5 when the LLM returns a bare list
        assert result["stability_score"] == 0.5
        assert len(result["preserved_elements"]) == 1


# ===========================================================================
# pragmatist_nodes.py
# ===========================================================================


class TestPragmatistNodeFactory:
    """``pragmatist_node_factory`` — evaluates build responses."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.pragmatist_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.pragmatist_nodes.get_audit_logger")
    async def test_no_build_responses(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.pragmatist_nodes import pragmatist_node_factory

        mock_al.return_value = MagicMock()
        node_fn = pragmatist_node_factory("node-prag", {"llm_profile_id": "p1", "system_prompt": "sp"})
        result = await node_fn(_make_state())
        assert result["pragmatist_output"]["reality_score"] == 0.0
        assert "No build responses" in result["pragmatist_output"]["blocking_concerns"][0]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.pragmatist_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.pragmatist_nodes.LLMService")
    @patch("backend.workflow.nodes.pragmatist_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.pragmatist_nodes._get_profile_service")
    async def test_llm_success(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.pragmatist_nodes import pragmatist_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result(_pragmatist_valid_payload()))
        mock_llm_cls.return_value = llm

        node_fn = pragmatist_node_factory("node-prag", {"llm_profile_id": "p1", "system_prompt": "sp"})
        result = await node_fn(
            _make_state(
                build_responses=[
                    {
                        "response_to": "c-test-001",
                        "provenance": {"draft_version": 1, "critic_item_id": "c-test-001"},
                    }
                ]
            )
        )
        assert result["pragmatist_output"]["reality_score"] == 0.8
        # Provenance is enriched with verdict + feasibility
        assert result["build_responses"][0]["provenance"]["pragmatist_verdict"] == "accept"
        assert result["build_responses"][0]["provenance"]["pragmatist_score"] == 0.8

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.pragmatist_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.pragmatist_nodes.LLMService")
    @patch("backend.workflow.nodes.pragmatist_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.pragmatist_nodes._get_profile_service")
    async def test_json_repair_rescues(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes import pragmatist_nodes as prag_mod

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("{" + _pragmatist_valid_payload()))
        mock_llm_cls.return_value = llm

        # Mock json_repair to be importable and to fix the missing brace
        fake_repair_module = MagicMock()
        fake_repair_module.repair_json = MagicMock(return_value=_pragmatist_valid_payload())
        import sys

        sys.modules["json_repair"] = fake_repair_module
        try:
            if hasattr(prag_mod, "json_repair"):
                prag_mod.json_repair = fake_repair_module

            node_fn = prag_mod.pragmatist_node_factory("node-prag", {"llm_profile_id": "p1", "system_prompt": "sp"})
            result = await node_fn(_make_state(build_responses=[{"response_to": "c-test-001", "provenance": {"draft_version": 1}}]))
            assert result["pragmatist_output"]["reality_score"] == 0.8
        finally:
            sys.modules.pop("json_repair", None)
            if hasattr(prag_mod, "json_repair"):
                delattr(prag_mod, "json_repair")

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.pragmatist_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.pragmatist_nodes.LLMService")
    @patch("backend.workflow.nodes.pragmatist_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.pragmatist_nodes._get_profile_service")
    async def test_all_retries_fail(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.pragmatist_nodes import pragmatist_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("not json"))
        mock_llm_cls.return_value = llm

        node_fn = pragmatist_node_factory("node-prag", {"llm_profile_id": "p1", "system_prompt": "sp"})
        result = await node_fn(_make_state(build_responses=[{"response_to": "c-test-001", "provenance": {}}]))
        assert result["node_outputs"][0]["status"] == "failed"
        # pragmatist_output is None when all retries fail
        assert result["pragmatist_output"] is None

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.pragmatist_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.pragmatist_nodes.LLMService")
    @patch("backend.workflow.nodes.pragmatist_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.pragmatist_nodes._get_profile_service")
    async def test_llm_service_raises(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.pragmatist_nodes import pragmatist_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=Exception("LLM down"))
        mock_llm_cls.return_value = llm

        node_fn = pragmatist_node_factory("node-prag", {"llm_profile_id": "p1", "system_prompt": "sp"})
        result = await node_fn(_make_state(build_responses=[{"response_to": "c-test-001", "provenance": {}}]))
        assert result["node_outputs"][0]["status"] == "failed"
        assert "LLM call failed" in result["node_outputs"][0]["content"]


class TestSaveProvenanceBatch:
    """``_save_provenance_batch`` — delegates to BlueprintRepository."""

    def test_success(self) -> None:
        from backend.workflow.nodes.pragmatist_nodes import _save_provenance_batch

        with patch("backend.blueprints.repository.BlueprintRepository") as repo_cls:
            repo = MagicMock()
            repo_cls.return_value = repo
            _save_provenance_batch("s", "wf", [{"response_to": "c"}])
            repo.save_provenance_batch.assert_called_once()

    def test_failure_is_swallowed(self) -> None:
        from backend.workflow.nodes.pragmatist_nodes import _save_provenance_batch

        with patch(
            "backend.blueprints.repository.BlueprintRepository",
            side_effect=Exception("db down"),
        ):
            # Must NOT raise
            _save_provenance_batch("s", "wf", [])


# ===========================================================================
# moderator_nodes.py
# ===========================================================================


class TestIsEvaluationAcceptable:
    """``_is_evaluation_acceptable`` — veto + feasibility floor check."""

    def test_none_is_rejected(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable(None) is False

    def test_non_dict_is_rejected(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable("string") is False
        assert _is_evaluation_acceptable(42) is False

    def test_empty_dict_rejected(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({}) is False

    def test_reject_verdict_rejected(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({"verdict": "reject", "feasibility": 0.9}) is False

    def test_non_numeric_feasibility_rejected(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({"verdict": "accept", "feasibility": "x"}) is False

    def test_below_floor_rejected(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({"verdict": "accept", "feasibility": 0.05}) is False

    def test_accept_above_floor_accepted(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({"verdict": "accept", "feasibility": 0.5}) is True

    def test_revise_above_floor_accepted(self) -> None:
        from backend.workflow.nodes.moderator_nodes import _is_evaluation_acceptable

        assert _is_evaluation_acceptable({"verdict": "revise", "feasibility": 0.5}) is True


class TestModeratorNodeFactory:
    """``moderator_node_factory`` — standard + transactional paths."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.node_functions._get_profile_service")
    async def test_standard_path_uses_draft_length(
        self,
        mock_ps: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import moderator_node_factory

        mock_ps.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("M output"))
        mock_llm_cls.return_value = llm

        node_fn = moderator_node_factory("node-mod", {"role": "moderator"}, threshold=0.7)
        result = await node_fn(_make_state(current_draft="x" * 5000))
        # Standard path — no consensus_result key
        assert "consensus_result" not in result
        assert 0.0 <= result["final_consensus"] <= 1.0
        assert result["final_assessment"] == "M output"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.node_functions._get_profile_service")
    async def test_td_path_hard_reject_overrides(
        self,
        mock_ps: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import moderator_node_factory

        mock_ps.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("M output"))
        mock_llm_cls.return_value = llm

        node_fn = moderator_node_factory("node-mod", {"role": "moderator"}, threshold=0.7)
        result = await node_fn(
            _make_state(
                workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING,
                pragmatist_output={
                    "reality_score": 0.9,  # LLM says high
                    "blocking_concerns": [],
                    "evaluations": [
                        # …but the hard floor says no
                        {"response_to": "c1", "verdict": "reject", "feasibility": 0.9},
                    ],
                },
            )
        )
        assert result["consensus_result"]["verdict"] == "revision_required"
        assert "Hard-rejected" in result["consensus_result"]["blocking_concerns"][0]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.node_functions._get_profile_service")
    async def test_td_path_approved(
        self,
        mock_ps: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import moderator_node_factory

        mock_ps.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("M output"))
        mock_llm_cls.return_value = llm

        node_fn = moderator_node_factory("node-mod", {"role": "moderator"}, threshold=0.7)
        result = await node_fn(
            _make_state(
                workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING,
                pragmatist_output={
                    "reality_score": 0.8,
                    "blocking_concerns": [],
                    "evaluations": [
                        {"response_to": "c1", "verdict": "accept", "feasibility": 0.8},
                    ],
                },
            )
        )
        assert result["consensus_result"]["verdict"] == "approved"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.node_functions._get_profile_service")
    async def test_td_path_no_pragmatist_force_approve_after_3(
        self,
        mock_ps: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import moderator_node_factory

        mock_ps.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("M output"))
        mock_llm_cls.return_value = llm

        node_fn = moderator_node_factory("node-mod", {"role": "moderator"}, threshold=0.7)
        result = await node_fn(
            _make_state(
                workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING,
                build_responses=[],
                draft_version=3,
            )
        )
        assert result["consensus_result"]["verdict"] == "approved"
        assert "Approved with warning" in result["consensus_result"]["blocking_concerns"][0]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.node_functions._get_profile_service")
    async def test_td_path_no_pragmatist_first_attempt_revision(
        self,
        mock_ps: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import moderator_node_factory

        mock_ps.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("M output"))
        mock_llm_cls.return_value = llm

        node_fn = moderator_node_factory("node-mod", {"role": "moderator"}, threshold=0.7)
        result = await node_fn(
            _make_state(
                workflow_template=WorkflowTemplate.TRANSACTIONAL_DRAFTING,
            )
        )
        assert result["consensus_result"]["verdict"] == "revision_required"
        # draft_version increments on revision
        assert result["draft_version"] >= 2

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.agent_nodes.LLMService")
    @patch("backend.workflow.node_functions._get_profile_service")
    async def test_publishes_consensus_reached(
        self,
        mock_ps: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import moderator_node_factory

        mock_ps.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("M output"))
        mock_llm_cls.return_value = llm

        node_fn = moderator_node_factory("node-mod", {"role": "moderator"})
        await node_fn(_make_state())
        events = [c.args[1] for c in mock_publish.call_args_list]
        assert "consensus.reached" in events
        assert "round_update" in events


class TestGateNodeFactory:
    """``gate_node_factory`` — safe-eval condition evaluation."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    @patch("backend.workflow.workflow_runner._serialize_state", side_effect=lambda s: s)
    @patch("backend.workflow.state_snapshot.StateSnapshotStore")
    async def test_evaluates_true(
        self,
        mock_ss: MagicMock,
        mock_ser: MagicMock,
        mock_al: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import gate_node_factory

        mock_al.return_value = MagicMock()
        mock_ss.return_value = MagicMock()
        node_fn = gate_node_factory("gate-1", "current_round >= 1")
        result = await node_fn(_make_state(current_round=3))
        assert "True" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    async def test_empty_condition_does_not_raise(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.moderator_nodes import gate_node_factory

        mock_al.return_value = MagicMock()
        node_fn = gate_node_factory("gate-1", "")
        result = await node_fn(_make_state())
        assert "False" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    async def test_unsafe_condition_swallows_error(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.moderator_nodes import gate_node_factory

        mock_al.return_value = MagicMock()
        node_fn = gate_node_factory("gate-1", "import os")
        # ``import os`` is rejected by the safe evaluator — must not raise
        result = await node_fn(_make_state())
        assert "node_outputs" in result


class TestToneProfileNodeFactory:
    """``tone_profile_node_factory`` — load or inline profile."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    async def test_inline_profile_dict(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.moderator_nodes import tone_profile_node_factory

        mock_al.return_value = MagicMock()
        inline = {"name": "My Profile", "description": "d", "style": "academic"}
        node_fn = tone_profile_node_factory("node-tp", {"inline_profile": inline})
        result = await node_fn(_make_state())
        assert "node-tp" in result["tone_profiles"]
        assert result["tone_profiles"]["node-tp"]["name"] == "My Profile"
        assert result["node_outputs"][0]["status"] == "completed"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    async def test_invalid_inline_profile_fails(self, mock_al: MagicMock, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.moderator_nodes import tone_profile_node_factory

        mock_al.return_value = MagicMock()
        node_fn = tone_profile_node_factory("node-tp", {"inline_profile": {"bad": "data"}})
        result = await node_fn(_make_state())
        assert result["node_outputs"][0]["status"] == "failed"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    @patch("backend.blueprints.repository.BlueprintRepository")
    async def test_catalog_hit(
        self,
        mock_repo_cls: MagicMock,
        mock_al: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.blueprints.models import ToneProfile
        from backend.workflow.nodes.moderator_nodes import tone_profile_node_factory

        mock_al.return_value = MagicMock()
        repo = MagicMock()
        repo.get_tone_profile = MagicMock(return_value=ToneProfile(name="cat", description="d", style="academic"))
        mock_repo_cls.return_value = repo

        node_fn = tone_profile_node_factory("node-tp", {"tone_profile_id": "tp-1"})
        result = await node_fn(_make_state())
        assert result["tone_profiles"]["node-tp"]["name"] == "cat"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    @patch("backend.blueprints.repository.BlueprintRepository")
    async def test_catalog_miss(
        self,
        mock_repo_cls: MagicMock,
        mock_al: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import tone_profile_node_factory

        mock_al.return_value = MagicMock()
        repo = MagicMock()
        repo.get_tone_profile = MagicMock(return_value=None)
        mock_repo_cls.return_value = repo

        node_fn = tone_profile_node_factory("node-tp", {"tone_profile_id": "missing"})
        result = await node_fn(_make_state())
        assert "node-tp" not in result["tone_profiles"]
        assert result["node_outputs"][0]["status"] == "failed"

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.moderator_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.moderator_nodes.get_audit_logger")
    @patch("backend.blueprints.repository.BlueprintRepository", side_effect=Exception("db down"))
    async def test_repo_raises_swallows(
        self,
        mock_repo_cls: MagicMock,
        mock_al: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.moderator_nodes import tone_profile_node_factory

        mock_al.return_value = MagicMock()
        node_fn = tone_profile_node_factory("node-tp", {"tone_profile_id": "tp-1"})
        # Must NOT raise
        result = await node_fn(_make_state())
        assert "node_outputs" in result


# ===========================================================================
# builder_nodes.py
# ===========================================================================


class TestStripMarkdownJson:
    """``_strip_markdown_json`` — strips code-block fences."""

    def test_plain_text_unchanged(self) -> None:
        from backend.workflow.nodes.builder_nodes import _strip_markdown_json

        assert _strip_markdown_json("hello") == "hello"

    def test_json_fence(self) -> None:
        from backend.workflow.nodes.builder_nodes import _strip_markdown_json

        assert _strip_markdown_json("```json\nhello\n```") == "hello"

    def test_plain_fence(self) -> None:
        from backend.workflow.nodes.builder_nodes import _strip_markdown_json

        assert _strip_markdown_json("```\nhello\n```") == "hello"

    def test_opening_only_fence_removed(self) -> None:
        """Stray opening fence (no close) is removed; the content kept."""
        from backend.workflow.nodes.builder_nodes import _strip_markdown_json

        assert _strip_markdown_json("```\nhello") == "hello"


class TestCleanLlmOutput:
    """``_clean_llm_output`` — strips control chars."""

    def test_strips_null_byte(self) -> None:
        from backend.workflow.nodes.builder_nodes import _clean_llm_output

        assert _clean_llm_output("a\x00b") == "ab"

    def test_keeps_tab_and_newline(self) -> None:
        from backend.workflow.nodes.builder_nodes import _clean_llm_output

        assert _clean_llm_output("a\tb\nc") == "a\tb\nc"

    def test_no_op_on_clean_text(self) -> None:
        from backend.workflow.nodes.builder_nodes import _clean_llm_output

        assert _clean_llm_output("clean text") == "clean text"


class TestExtractZeroDraft:
    """``_extract_zero_draft`` — latest_draft > zero_draft > strategist > context."""

    def test_latest_wins(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        assert _extract_zero_draft({"latest_draft": "L", "zero_draft": "Z", "context": "C"}) == "L"

    def test_zero_when_no_latest(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        assert _extract_zero_draft({"latest_draft": "", "zero_draft": "Z", "context": "C"}) == "Z"

    def test_strategist_fallback(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        state = {
            "node_outputs": [{"node_type": "wf-strategist", "content": "S"}],
            "context": "C",
        }
        assert _extract_zero_draft(state) == "S"

    def test_context_fallback(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        assert _extract_zero_draft({"context": "C"}) == "C"


class TestExtractCriticItems:
    """``_extract_critic_items`` — round-filtered + node-output fallback."""

    def test_filters_by_round(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "current_round": 2,
            "critic_items": [
                {"round": 1, "a": 1},
                {"round": 2, "a": 2},
            ],
        }
        result = _extract_critic_items(state)
        assert len(result) == 1
        assert result[0]["a"] == 2

    def test_no_round_tag_returns_all(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        items = [{"a": 1}, {"a": 2}]
        assert _extract_critic_items({"critic_items": items}) == items

    def test_no_current_round_match_returns_empty(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "current_round": 2,
            "critic_items": [{"round": 1, "a": 1}],
        }
        assert _extract_critic_items(state) == []

    def test_parses_from_node_outputs(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        item = {
            "critic_id": "c-test-001",
            "severity": "blocking",
            "target": "§1",
            "flaw": "x",
            "principle": "p",
            "context_quote": "q",
        }
        state = {
            "critic_items": [],
            "node_outputs": [{"node_type": "wf-critic", "content": json.dumps([item])}],
        }
        assert _extract_critic_items(state) == [item]

    def test_returns_empty_on_broken_json(self) -> None:
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "critic_items": [],
            "node_outputs": [{"node_type": "wf-critic", "content": "not json"}],
        }
        assert _extract_critic_items(state) == []


class TestBuilderNodeFactory:
    """``builder_node_factory`` — full LLM-driven flow."""

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    async def test_no_critic_items_returns_placeholder(self, mock_publish: AsyncMock) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(_make_state())
        assert "No critique" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_llm_success(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result(_builder_valid_payload()))
        mock_llm_cls.return_value = llm

        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(
            _make_state(
                critic_items=[_VALID_CRITIC_ITEM],
                zero_draft="Z",
                preserved_elements=[{"source_location": "§1", "preserved_text": "T", "rationale": "R"}],
                pragmatist_output={"blocking_concerns": ["concern 1"]},
                draft_version=2,
            )
        )
        # global_revision wins → latest_draft == "G"
        assert result["latest_draft"] == "G"
        assert result["constructivity_score"] == 1.0  # 1 build_responses / 1 critic
        assert len(result["build_responses"]) == 1

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_no_global_revision_falls_back_to_content(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result(_builder_valid_payload(with_global=False)))
        mock_llm_cls.return_value = llm

        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM]))
        # No global_revision → latest_draft == raw content
        assert result["latest_draft"] == _builder_valid_payload(with_global=False)

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_list_payload_wrapped(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        list_payload = json.dumps([_build_response_a()])
        llm.generate = AsyncMock(return_value=_fake_llm_result(list_payload))
        mock_llm_cls.return_value = llm

        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM]))
        assert len(result["build_responses"]) == 1

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_json_repair_rescues(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes import builder_nodes as bld_mod

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("{" + _builder_valid_payload()))
        mock_llm_cls.return_value = llm

        # Mock json_repair to be importable and to fix the missing brace
        fake_repair_module = MagicMock()
        fake_repair_module.repair_json = MagicMock(return_value=_builder_valid_payload())
        import sys

        sys.modules["json_repair"] = fake_repair_module
        try:
            if hasattr(bld_mod, "json_repair"):
                bld_mod.json_repair = fake_repair_module

            node_fn = bld_mod.builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
            result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM]))
            assert len(result["build_responses"]) == 1
        finally:
            sys.modules.pop("json_repair", None)
            if hasattr(bld_mod, "json_repair"):
                delattr(bld_mod, "json_repair")

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_all_retries_fail(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result("not json"))
        mock_llm_cls.return_value = llm

        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM]))
        assert result["node_outputs"][0]["status"] == "failed"
        assert result["build_responses"] == []
        assert result["constructivity_score"] == 0.0
        mock_al.return_value.log_node_failed.assert_called_once()

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_llm_service_raises(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(side_effect=Exception("LLM down"))
        mock_llm_cls.return_value = llm

        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM]))
        assert result["node_outputs"][0]["status"] == "failed"
        assert "LLM call failed" in result["node_outputs"][0]["content"]

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_recommendation_routes_to_revision_type(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        """``recommendation`` value selects the provenance ``revision_type``."""
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()

        cases: list[tuple[str, str]] = [
            ("option_a", "conservative"),
            ("option_b", "radical"),
            ("option_c", "minimal"),
            ("none", "conservative"),  # unknown falls back
        ]
        for recommendation, expected in cases:
            br = dict(_build_response_a(), recommendation=recommendation)
            payload = json.dumps({"build_responses": [br], "constructivity_score": 0.0})
            llm = MagicMock()
            llm.generate = AsyncMock(return_value=_fake_llm_result(payload))
            mock_llm_cls.return_value = llm

            node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
            result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM]))
            assert result["build_responses"][0]["provenance"]["revision_type"] == expected

    @pytest.mark.asyncio
    @patch("backend.workflow.nodes.builder_nodes.publish_async", new_callable=AsyncMock)
    @patch("backend.workflow.nodes.builder_nodes.LLMService")
    @patch("backend.workflow.nodes.builder_nodes.get_audit_logger")
    @patch("backend.workflow.nodes.builder_nodes._get_profile_service")
    async def test_english_language_branch(
        self,
        mock_ps: MagicMock,
        mock_al: MagicMock,
        mock_llm_cls: MagicMock,
        mock_publish: AsyncMock,
    ) -> None:
        from backend.workflow.nodes.builder_nodes import builder_node_factory

        mock_ps.return_value = MagicMock()
        mock_al.return_value = MagicMock()
        llm = MagicMock()
        llm.generate = AsyncMock(return_value=_fake_llm_result(_builder_valid_payload()))
        mock_llm_cls.return_value = llm

        # Just check that the english branch doesn't crash
        node_fn = builder_node_factory("node-bld", {"llm_profile_id": "p1", "role": "builder"})
        result = await node_fn(_make_state(critic_items=[_VALID_CRITIC_ITEM], language="en"))
        assert result["node_outputs"][0]["status"] == "completed"
