"""Tests for backend/workflow/workflow_runner.py — helpers and session lifecycle.

Focus areas (previously uncovered):
* ``_serialize_state`` — JSON serialization with depth guard
* ``normalize_transcript_content`` — JSON→Markdown for critic/builder/pragmatist
* ``normalize_transcript_for_display`` — zero-draft/critic/builder from state
* ``_build_artifact_from_state`` + ``_build_artifact_common`` + ``_build_verdict_map``
* ``is_cancelled`` / ``cancel_session`` / ``pause_session`` / ``resume_session``
  / ``get_session_status`` / ``set_session_status`` / ``get_pause_event``
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any
from unittest.mock import patch

from pydantic import BaseModel

from backend.workflow.workflow_runner import (
    _build_artifact_from_state,
    _build_verdict_map,
    _serialize_state,
    cancel_session,
    get_pause_event,
    get_session_status,
    is_cancelled,
    normalize_transcript_content,
    normalize_transcript_for_display,
    pause_session,
    resume_session,
    set_session_status,
)
from backend.workflow.workflow_state import WorkflowTemplate

# ---------------------------------------------------------------------------
# _serialize_state
# ---------------------------------------------------------------------------


class _Color(Enum):
    RED = "red"
    BLUE = "blue"


class _Point(BaseModel):
    x: int
    y: int


class TestSerializeState:
    def test_primitives_pass_through(self) -> None:
        state = {"a": 1, "b": 1.5, "c": "hi", "d": True, "e": None}
        assert _serialize_state(state) == state

    def test_nested_dict_preserved(self) -> None:
        state = {"outer": {"inner": {"deep": 42}}}
        assert _serialize_state(state) == state

    def test_list_preserved(self) -> None:
        state = {"items": [1, 2, {"x": 3}]}
        assert _serialize_state(state) == state

    def test_pydantic_model_dump(self) -> None:
        state = {"p": _Point(x=1, y=2)}
        out = _serialize_state(state)
        assert out == {"p": {"x": 1, "y": 2}}

    def test_enum_value_extracted(self) -> None:
        state = {"color": _Color.RED}
        assert _serialize_state(state) == {"color": "red"}

    def test_fallback_to_str_for_unknown(self) -> None:
        # An object that has no model_dump, no .value, isn't primitive
        class _Weird:
            def __repr__(self) -> str:
                return "<weird>"

        out = _serialize_state({"k": _Weird()})
        assert out == {"k": "<weird>"}

    def test_depth_limit_truncates(self) -> None:
        from backend.workflow.workflow_runner import _MAX_SERIALIZE_DEPTH

        # Build a deeply nested dict. The serializer keeps recursing into
        # dicts/lists until ``depth >= _MAX_SERIALIZE_DEPTH``, at which
        # point the value is converted to ``str()``. The number of dict
        # levels that survive serialisation equals the depth limit.
        depth = _MAX_SERIALIZE_DEPTH + 5
        deep: Any = "leaf"
        for _ in range(depth):
            deep = {"k": deep}
        out = _serialize_state({"x": deep})
        # Walk down through the dict levels that survived
        cur = out["x"]
        level = 0
        while isinstance(cur, dict):
            cur = cur["k"]
            level += 1
        # Final value is a string (depth limit hit)
        assert isinstance(cur, str)
        # And we made it through at least the configured number of levels
        assert level >= _MAX_SERIALIZE_DEPTH

    def test_self_referential_does_not_crash(self) -> None:
        a: dict = {}
        a["self"] = a
        # Should not raise RecursionError
        out = _serialize_state(a)
        # Final leaf falls back to str at the depth limit
        assert "self" in out


# ---------------------------------------------------------------------------
# normalize_transcript_content
# ---------------------------------------------------------------------------


class TestNormalizeTranscriptContent:
    def test_empty_returns_empty(self) -> None:
        assert normalize_transcript_content("", "critic") == ""
        assert normalize_transcript_content("   ", "critic") == "   "

    def test_non_json_passes_through(self) -> None:
        txt = "Just plain text without JSON."
        assert normalize_transcript_content(txt, "strategist") == txt

    def test_json_code_fences_stripped(self) -> None:
        fenced = '```json\n[{"critic_id": "C1", "severity": "high"}]\n```'
        out = normalize_transcript_content(fenced, "critic")
        assert "C1" in out
        assert "HIGH" in out

    def test_critic_renders_severity_principle_flaw(self) -> None:
        payload = json.dumps(
            [
                {
                    "critic_id": "C1",
                    "severity": "hoch",
                    "target": "Absatz 1",
                    "flaw": "Unklare Aussage",
                    "principle": "Klarheit",
                    "context_quote": "Beispieltext",
                }
            ]
        )
        out = normalize_transcript_content(payload, "critic")
        assert "C1" in out
        assert "HOCH" in out
        assert "Absatz 1" in out
        assert "Unklare Aussage" in out
        assert "Klarheit" in out
        assert "> Beispieltext" in out

    def test_builder_renders_options_and_recommendation(self) -> None:
        payload = json.dumps(
            {
                "build_responses": [
                    {
                        "response_to": "critic-1",
                        "option_a": "Plan A",
                        "option_b": "Plan B",
                        "option_c": "Plan C",
                        "recommendation": "A",
                        "risk_assessment": "low",
                        "rationale": "Schnell umsetzbar",
                    }
                ]
            }
        )
        out = normalize_transcript_content(payload, "builder")
        assert "critic-1" in out
        assert "Plan A" in out
        assert "Plan B" in out
        assert "Plan C" in out
        assert "**Recommendation:** A" in out
        assert "Schnell umsetzbar" in out

    def test_pragmatist_renders_evaluations_and_concerns(self) -> None:
        payload = json.dumps(
            {
                "evaluations": [
                    {
                        "response_to": "resp-1",
                        "feasibility": "high",
                        "process_risk": "low",
                        "cost_time_estimate": "2d",
                        "verdict": "approve",
                        "revision_note": "Looks good",
                    }
                ],
                "blocking_concerns": ["Budget fehlt", "Skill-Gap"],
                "reality_score": 0.8,
            }
        )
        out = normalize_transcript_content(payload, "pragmatist")
        assert "resp-1" in out
        assert "Feasibility: high" in out
        assert "**Verdict:** approve" in out
        assert "**Reality Score:** 0.8" in out
        assert "Budget fehlt" in out
        assert "Skill-Gap" in out

    def test_unknown_role_passes_content_through(self) -> None:
        payload = json.dumps({"foo": "bar"})
        out = normalize_transcript_content(payload, "strategist")
        assert out == payload


# ---------------------------------------------------------------------------
# normalize_transcript_for_display
# ---------------------------------------------------------------------------


class TestNormalizeTranscriptForDisplay:
    def test_empty_state_returns_empty(self) -> None:
        assert normalize_transcript_for_display({}) == []

    def test_zero_draft_added(self) -> None:
        out = normalize_transcript_for_display({"zero_draft": "Hello draft"})
        assert len(out) == 1
        assert out[0]["role_type"] == "strategist"
        assert "Zero-Draft erstellt" in out[0]["content"]
        assert "Hello draft" in out[0]["content"]

    def test_zero_draft_truncates_huge_content(self) -> None:
        huge = "X" * 60000
        out = normalize_transcript_for_display({"zero_draft": huge})
        assert len(out) == 1
        assert "content truncated" in out[0]["content"]

    def test_zero_draft_non_string_converted(self) -> None:
        out = normalize_transcript_for_display({"zero_draft": 12345})
        assert out[0]["content"].endswith("12345")

    def test_critic_items_rendered(self) -> None:
        state = {
            "critic_items": [
                {
                    "severity": "hoch",
                    "flaw": "Logikfehler",
                    "principle": "Konsistenz",
                    "target": "Absatz 2",
                }
            ]
        }
        out = normalize_transcript_for_display(state)
        assert len(out) == 1
        assert out[0]["role_type"] == "critic"
        assert "Logikfehler" in out[0]["content"]
        assert "Konsistenz" in out[0]["content"]

    def test_build_responses_with_pragmatist_evaluations(self) -> None:
        state = {
            "build_responses": [
                {
                    "response_to": "C1",
                    "option_a": "Plan A",
                    "option_b": "Plan B",
                    "recommendation": "A",
                    "rationale": "Risk-minimiert",
                    "provenance": {
                        "draft_version": 2,
                        "critic_item_id": "C1",
                        "revision_type": "conservative",
                    },
                }
            ],
            "pragmatist_output": {
                "evaluations": [
                    {
                        "response_to": "C1",
                        "verdict": "approve",
                        "feasibility": "high",
                    }
                ]
            },
        }
        out = normalize_transcript_for_display(state)
        assert len(out) == 1
        assert out[0]["role_type"] == "builder"
        assert "C1" in out[0]["content"]
        assert "Plan A" in out[0]["content"]
        assert "Iteration 2" in out[0]["content"]
        assert "Critic: C1" in out[0]["content"]
        assert "Option A" in out[0]["content"]
        assert "Pragmatist: approve" in out[0]["content"]

    def test_build_responses_handles_pydantic_items(self) -> None:
        # Use plain dicts only; just ensure the code doesn't crash
        state = {"build_responses": [{"response_to": "x", "option_a": "A"}]}
        out = normalize_transcript_for_display(state)
        assert out[0]["role_type"] == "builder"


# ---------------------------------------------------------------------------
# _build_verdict_map
# ---------------------------------------------------------------------------


class TestBuildVerdictMap:
    def test_empty_inputs(self) -> None:
        assert _build_verdict_map([], []) == []

    def test_links_build_response_to_evaluation(self) -> None:
        br = {
            "response_to": "C1",
            "option_a": "Plan A",
            "option_b": "Plan B",
            "rationale": "R",
            "implementable": True,
            "provenance": {"draft_version": 2, "revision_type": "conservative"},
        }
        ev = {"response_to": "C1", "verdict": "approve", "feasibility": "high"}
        out = _build_verdict_map([br], [ev])
        assert len(out) == 1
        row = out[0]
        assert row["critic_item_id"] == "C1"
        assert row["option_a"] == "Plan A"
        assert row["implementable"] is True
        assert row["verdict"] == "approve"
        assert row["feasibility"] == "high"
        assert row["revision_type"] == "conservative"
        assert row["draft_version"] == 2

    def test_missing_evaluation_falls_back_to_provenance(self) -> None:
        br = {
            "response_to": "C2",
            "provenance": {
                "pragmatist_verdict": "reject",
                "pragmatist_score": 0.2,
            },
        }
        out = _build_verdict_map([br], [])
        assert out[0]["verdict"] == "reject"
        assert out[0]["feasibility"] == 0.2

    def test_no_provenance_falls_back_to_pending(self) -> None:
        br = {"response_to": "C3"}
        out = _build_verdict_map([br], [])
        assert out[0]["verdict"] == "pending"
        assert out[0]["feasibility"] is None
        assert out[0]["draft_version"] == 0

    def test_evaluation_does_not_match_response_to_ignored(self) -> None:
        br = {"response_to": "C4"}
        ev = {"response_to": "OTHER", "verdict": "approve"}
        out = _build_verdict_map([br], [ev])
        assert out[0]["verdict"] == "pending"


# ---------------------------------------------------------------------------
# _build_artifact_from_state
# ---------------------------------------------------------------------------


class TestBuildArtifactFromState:
    def test_standard_node_outputs_path(self) -> None:
        state = {
            "node_outputs": [
                {
                    "role": "strategist",
                    "node_id": "n1",
                    "round": 1,
                    "content": "Plan",
                    "duration_ms": 100,
                    "tokens_used": 5,
                }
            ],
            "node_configs": {
                "n1": {
                    "role_type_name": "Strategist",
                    "llm_model": "owl",
                }
            },
            "node_sequence": ["n1"],
            "consumed_interjections": [
                {
                    "interjection_id": "ij1",
                    "source": "user",
                    "target_node_id": "n1",
                    "content": "stop",
                }
            ],
            "title": "T",
            "context": "C",
        }
        art = _build_artifact_from_state(session_id="s1", workflow_id="w1", state=state, duration_ms=42)
        assert art.session_id == "s1"
        assert art.workflow_id == "w1"
        assert art.title == "T"
        assert art.topic == "C"
        assert art.metadata["duration_ms"] == 42
        assert len(art.transcript) == 1
        assert art.transcript[0].agent_name == "Strategist (owl)"
        assert len(art.interjections) == 1
        assert art.interjections[0].id == "ij1"
        assert art.consensus_result == {"score": 0.0}

    def test_skips_system_roles(self) -> None:
        state = {
            "node_outputs": [
                {"role": "complete", "node_id": "x", "content": "done"},
                {"role": "input", "node_id": "y", "content": "user"},
                {"role": "strategist", "node_id": "z", "content": "Plan"},
            ],
            "node_sequence": ["x", "y", "z"],
        }
        art = _build_artifact_from_state(session_id="s1", workflow_id="w1", state=state)
        assert len(art.transcript) == 1
        assert art.transcript[0].node_id == "z"

    def test_string_node_config_is_parsed(self) -> None:
        cfg = json.dumps({"role_type_name": "Critic", "llm_profile_id": "p1"})
        state = {
            "node_outputs": [
                {
                    "role": "critic",
                    "node_id": "n1",
                    "round": 1,
                    "content": "no",
                }
            ],
            "node_configs": {"n1": cfg},
            "node_sequence": ["n1"],
        }
        art = _build_artifact_from_state(session_id="s1", workflow_id="w1", state=state)
        assert "(p1)" in art.transcript[0].agent_name

    def test_transactional_path_uses_state_keys(self) -> None:
        state = {
            "workflow_template": WorkflowTemplate.TRANSACTIONAL_DRAFTING,
            "zero_draft": "First draft",
            "critic_items": [{"severity": "low", "flaw": "f", "principle": "p"}],
            "build_responses": [{"response_to": "ci_0", "option_a": "A"}],
            "pragmatist_output": {"reality_score": 0.7, "evaluations": []},
            "draft_version": 1,
        }
        art = _build_artifact_from_state(session_id="s1", workflow_id="w1", state=state)
        # Zero-draft + critic + builder = 3 turns
        assert len(art.transcript) == 3
        # Transactional metadata block populated
        meta = art.metadata.get("transactional", {})
        assert len(meta.get("critic_items", [])) == 1
        assert len(meta.get("build_responses", [])) == 1
        # Pragmatist scores reflected
        assert art.pragmatist_reality_score == 0.7
        assert art.draft_versions == 1
        assert art.critic_item_count == 1
        assert art.build_response_count == 1

    def test_metadata_workflow_template_default(self) -> None:
        state = {"node_outputs": []}
        art = _build_artifact_from_state(session_id="s1", workflow_id="w1", state=state)
        assert art.metadata["workflow_template"] == "debate"


# ---------------------------------------------------------------------------
# Session lifecycle helpers
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    """Tests for is_cancelled / cancel_session / pause / resume / status helpers.

    These delegate to the WorkflowState backend singleton — we patch the
    factory to return a MagicMock and assert the right calls happen.
    """

    def _patch_state(self):
        """Return a mock state backend + patcher for the factory."""
        mock = patch("backend.workflow.workflow_runner.get_workflow_state").start()
        backend = mock.return_value
        return backend, patch

    def teardown_method(self) -> None:
        patch.stopall()

    def test_is_cancelled_delegates(self) -> None:
        backend, _ = self._patch_state()
        backend.is_cancelled.return_value = True
        assert is_cancelled("s1") is True
        backend.is_cancelled.assert_called_once_with("s1")

    def test_cancel_session_marks_cancelled_and_fires_signal(self) -> None:
        backend, _ = self._patch_state()
        cancel_session("s1")
        backend.cancel.assert_called_once_with("s1")
        # extension signal is set best-effort
        backend.set_extension_signal.assert_called_once_with("s1")

    def test_cancel_session_swallows_signal_error(self) -> None:
        backend, _ = self._patch_state()
        backend.set_extension_signal.side_effect = RuntimeError("nope")
        # No task is registered for "s1" so we don't try to cancel asyncio
        cancel_session("s1")
        # Cancel itself was still called
        backend.cancel.assert_called_once()

    def test_get_set_status(self) -> None:
        backend, _ = self._patch_state()
        backend.get_status.return_value = "running"
        assert get_session_status("s1") == "running"
        set_session_status("s1", "paused")
        backend.set_status.assert_called_once_with("s1", "paused")

    def test_get_pause_event(self) -> None:
        backend, _ = self._patch_state()
        ev = object()
        backend.get_pause_event.return_value = ev
        assert get_pause_event("s1") is ev

    def test_pause_session_writes_audit_log(self) -> None:
        backend, _ = self._patch_state()
        with patch("backend.workflow.workflow_runner.get_audit_logger") as get_logger:
            pause_session("s1")
        backend.pause.assert_called_once_with("s1")
        get_logger.return_value.log_workflow_event.assert_called_once()

    def test_pause_session_swallows_audit_error(self) -> None:
        backend, _ = self._patch_state()
        with patch("backend.workflow.workflow_runner.get_audit_logger") as get_logger:
            get_logger.return_value.log_workflow_event.side_effect = RuntimeError("audit down")
            # Should not raise
            pause_session("s1")

    def test_resume_session_writes_audit_log(self) -> None:
        backend, _ = self._patch_state()
        with patch("backend.workflow.workflow_runner.get_audit_logger") as get_logger:
            resume_session("s1")
        backend.resume.assert_called_once_with("s1")
        get_logger.return_value.log_workflow_event.assert_called_once()

    def test_resume_session_swallows_audit_error(self) -> None:
        backend, _ = self._patch_state()
        with patch("backend.workflow.workflow_runner.get_audit_logger") as get_logger:
            get_logger.return_value.log_workflow_event.side_effect = RuntimeError("audit down")
            # Should not raise
            resume_session("s1")
