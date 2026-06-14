"""Tests for backend/workflow/report_generator.py — workflow report generation.

The module had 7 % coverage. These tests focus on the pure helpers and
static methods (no docx/weasyprint/odf rendering) which together account
for the bulk of the 630 statements.  Rendering the actual file formats
is not exercised here because of the heavy native dependencies
(``weasyprint``, ``odf``); the report format validation and the data
shaping that feeds the renderers are fully covered.
"""

from __future__ import annotations

import pytest

from backend.workflow.report_generator import (
    WorkflowReportGenerator,
    _build_node_phase_map,
    _display_agent_role,
    _format_audit_content,
    _format_content_for_display,
)

# ---------------------------------------------------------------------------
# _display_agent_role
# ---------------------------------------------------------------------------


class TestDisplayAgentRole:
    def test_empty_returns_unknown(self) -> None:
        assert _display_agent_role("") == "Unbekannt"

    def test_uppercase_passthrough(self) -> None:
        # MVP-formatted names like "Strategist (deepseek-v4-flash)" stay as-is
        assert _display_agent_role("Strategist (deepseek-v4-flash)") == "Strategist (deepseek-v4-flash)"

    def test_lowercase_capitalised(self) -> None:
        # Legacy raw role names get capitalised
        assert _display_agent_role("critic") == "Critic"

    def test_mixed_case_passthrough(self) -> None:
        # Already capitalised roles are not re-capitalised
        assert _display_agent_role("Fact-checker") == "Fact-checker"


# ---------------------------------------------------------------------------
# _format_content_for_display
# ---------------------------------------------------------------------------


class TestFormatContentForDisplay:
    def test_empty_content(self) -> None:
        assert _format_content_for_display("") == ""

    def test_plain_text_unchanged(self) -> None:
        assert _format_content_for_display("Just a thought.") == "Just a thought."

    def test_json_without_orchestrator_keys_unchanged(self) -> None:
        # JSON without reasoning/next_agent etc. is left as-is
        raw = '{"foo": "bar"}'
        assert _format_content_for_display(raw) == raw

    def test_invalid_json_unchanged(self) -> None:
        assert _format_content_for_display("{not json") == "{not json"

    def test_orchestrator_json_rendered_as_text(self) -> None:
        raw = '{"reasoning": "Need more data.", "next_agent": "analyst"}'
        out = _format_content_for_display(raw)
        assert "Reasoning:" in out
        assert "Need more data." in out
        assert "Next Agent:" in out
        assert "analyst" in out
        # Original JSON is gone
        assert "{" not in out

    def test_orchestrator_json_with_all_fields(self) -> None:
        raw = (
            '{"reasoning": "R", "contextual_directive": "D", '
            '"injection_context": "I", "debate_status": "S", '
            '"phase_transition": "P", "next_agent": "A"}'
        )
        out = _format_content_for_display(raw)
        for label in ("Reasoning", "Directive", "Context", "Status", "Phase Transition", "Next Agent"):
            assert label in out

    def test_orchestrator_json_skips_empty_values(self) -> None:
        raw = '{"reasoning": "  ", "next_agent": "analyst"}'
        out = _format_content_for_display(raw)
        # Empty reasoning should not produce a "Reasoning:" line
        assert "Reasoning:" not in out
        assert "Next Agent:" in out

    def test_non_dict_json_unchanged(self) -> None:
        assert _format_content_for_display("[1, 2, 3]") == "[1, 2, 3]"

    def test_whitespace_only_unchanged(self) -> None:
        assert _format_content_for_display("   ") == "   "


# ---------------------------------------------------------------------------
# _build_node_phase_map
# ---------------------------------------------------------------------------


def _fake_wf_def(phase_configs: dict) -> object:
    """Build a minimal stand-in for ``WorkflowDefinition`` with phase_configs."""
    return type(
        "FakeWF",
        (),
        {"phase_configs": phase_configs},
    )()


def _make_repo_stub(monkeypatch, phase_configs: dict) -> None:
    """Stub ``backend.blueprints.repository.BlueprintRepository`` to return a fake WF def."""
    import backend.blueprints.repository as repo_mod

    fake = _fake_wf_def(phase_configs)

    class _RepoStub:
        def get_workflow_definition(self, _wid: str):
            return fake

    monkeypatch.setattr(repo_mod, "BlueprintRepository", _RepoStub)


def _stub_repo_returns_none(monkeypatch) -> None:
    """Stub the repo so that ``get_workflow_definition`` returns ``None``."""
    import backend.blueprints.repository as repo_mod

    class _RepoStub:
        def get_workflow_definition(self, _wid: str):
            return None

    monkeypatch.setattr(repo_mod, "BlueprintRepository", _RepoStub)


class TestBuildNodePhaseMap:
    def test_empty_sequence(self) -> None:
        assert _build_node_phase_map({}) == {}

    def test_no_workflow_returns_empty(self, monkeypatch) -> None:
        _stub_repo_returns_none(monkeypatch)
        result = _build_node_phase_map({"node_sequence": ["a", "b"]}, workflow_id="wf-1")
        assert result == {}

    def test_phase_assigns_subsequent_nodes(self, monkeypatch) -> None:
        from backend.blueprints.workflow_models import PhaseConfig

        _make_repo_stub(
            monkeypatch,
            {
                "phase-1": PhaseConfig(name="Analyse", phase_node_id="phase-1"),
                "phase-2": PhaseConfig(name="Synthese", phase_node_id="phase-2"),
            },
        )
        state = {"node_sequence": ["phase-1", "a", "b", "phase-2", "c"]}
        result = _build_node_phase_map(state, workflow_id="wf-1")
        assert result["a"]["phase_name"] == "Analyse"
        assert result["a"]["phase_index"] == 1
        assert result["b"]["phase_name"] == "Analyse"
        assert result["b"]["phase_index"] == 1
        assert result["c"]["phase_name"] == "Synthese"
        assert result["c"]["phase_index"] == 2

    def test_phase_nodes_are_not_in_map(self, monkeypatch) -> None:
        from backend.blueprints.workflow_models import PhaseConfig

        _make_repo_stub(
            monkeypatch,
            {"phase-1": PhaseConfig(name="P1", phase_node_id="phase-1")},
        )
        state = {"node_sequence": ["phase-1", "a"]}
        result = _build_node_phase_map(state, workflow_id="wf-1")
        # The phase node itself is not a target
        assert "phase-1" not in result
        assert "a" in result
        assert result["a"]["phase_name"] == "P1"

    def test_continues_phase_after_unrecognised_node(self, monkeypatch) -> None:
        # An unrecognised id is treated as a regular node (assigned the
        # current phase) — the function does not break out of the phase.
        from backend.blueprints.workflow_models import PhaseConfig

        _make_repo_stub(
            monkeypatch,
            {"phase-1": PhaseConfig(name="P1", phase_node_id="phase-1")},
        )
        state = {"node_sequence": ["phase-1", "a", "unknown", "b"]}
        result = _build_node_phase_map(state, workflow_id="wf-1")
        assert result["a"]["phase_name"] == "P1"
        # "unknown" is a non-phase node but still gets the current phase
        assert result["unknown"]["phase_name"] == "P1"
        assert result["b"]["phase_name"] == "P1"


# ---------------------------------------------------------------------------
# _format_audit_content
# ---------------------------------------------------------------------------


class TestFormatAuditContent:
    def test_empty_content(self) -> None:
        assert _format_audit_content("") == ""

    def test_plain_text_passthrough(self) -> None:
        assert _format_audit_content("hello world") == "hello world"

    def test_string_value_extracted(self) -> None:
        data = '{"value": "some output"}'
        out = _format_audit_content(data)
        assert "some output" in out

    def test_node_outputs_extracted(self) -> None:
        data = '{"node_outputs": [{"content": "agent said X"}]}'
        out = _format_audit_content(data)
        assert "agent said X" in out

    def test_gate_decision_extracted(self) -> None:
        data = '{"gate_decision": {"decision": "approve", "reason": "looks good"}}'
        out = _format_audit_content(data)
        assert "approve" in out
        assert "looks good" in out

    def test_context_extracted(self) -> None:
        data = '{"context": "injected context"}'
        out = _format_audit_content(data)
        assert "injected context" in out

    def test_output_extracted(self) -> None:
        data = '{"output": "final output"}'
        out = _format_audit_content(data)
        assert "final output" in out

    def test_content_fallback(self) -> None:
        data = '{"content": "direct content"}'
        out = _format_audit_content(data)
        assert "direct content" in out

    def test_oversized_json_truncated(self) -> None:
        # 600 chars of junk — should be truncated with ellipsis
        data = '{"unrecognized": "' + ("x" * 600) + '"}'
        out = _format_audit_content(data)
        assert out.endswith("…")
        assert len(out) <= 520

    def test_non_json_passthrough(self) -> None:
        assert _format_audit_content("plain text") == "plain text"


# ---------------------------------------------------------------------------
# generate() — format validation
# ---------------------------------------------------------------------------


class TestGenerateFormatValidation:
    @pytest.mark.asyncio
    async def test_unsupported_format_raises(self, tmp_path) -> None:
        gen = WorkflowReportGenerator(db_path=tmp_path / "audit.db")
        with pytest.raises(ValueError, match="Unsupported format"):
            await gen.generate("session-123", fmt="xlsx")
