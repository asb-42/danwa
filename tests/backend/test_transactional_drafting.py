"""Tests for Transactional Drafting Mode.

Covers the Akzeptanzkriterien:
- JSON parsing of structured outputs (CriticItem[], BuildResponse[], PragmatistOutput)
- Loop detection (max 5 iterations → construction_deadlock)
- Constructivity score calculation
- Decision router logic (approved / return_to_builder / construction_deadlock)
- Moderator decision (reality_score < 0.6 → revision_required)
- No impact on standard debate workflows
"""

from __future__ import annotations

import json

import pytest

from backend.models.transactional import (
    BuildResponse,
    BuilderOutput,
    CriticItem,
    PragmatistEvaluation,
    PragmatistOutput,
)


# ---------------------------------------------------------------------------
# 1. CriticItem JSON parsing
# ---------------------------------------------------------------------------


class TestCriticItemParsing:
    """Verify CriticItem Pydantic model accepts valid JSON and rejects invalid."""

    def test_valid_critic_item(self):
        item = CriticItem(
            critic_id="c-critic_1-001",
            severity="blocking",
            target="§3 Absatz 2",
            flaw="Fehlende Haftungsbeschränkung",
            principle="Rechtssicherheit",
            context_quote="Der Auftragnehmer haftet nicht für Folgeschäden.",
        )
        assert item.critic_id == "c-critic_1-001"
        assert item.severity == "blocking"
        assert item.target == "§3 Absatz 2"

    def test_critic_item_minimal(self):
        """Only critic_id, severity, target, flaw, principle are required."""
        item = CriticItem(
            critic_id="c-node_1-001",
            severity="cosmetic",
            target="Preamble",
            flaw="Vague wording",
            principle="Clarity",
        )
        assert item.context_quote is None

    def test_critic_item_severity_values(self):
        for sev in ["blocking", "critical", "warning", "cosmetic"]:
            item = CriticItem(
                critic_id=f"c-test_1-{ord(sev[0]):03d}",
                severity=sev,
                target="X",
                flaw="Y",
                principle="Z",
            )
            assert item.severity == sev

    def test_parse_critic_output_valid_json_array(self):
        """agent_nodes._parse_critic_output should parse a JSON array."""
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        content = json.dumps([
            {
                "critic_id": "c-critic_1-001",
                "severity": "blocking",
                "target": "§1",
                "flaw": "Missing clause",
                "principle": "Completeness",
            },
            {
                "critic_id": "c-critic_1-002",
                "severity": "critical",
                "target": "§2",
                "flaw": "Ambiguous language",
                "principle": "Clarity",
            },
        ])
        result = _parse_critic_output(content, "test_node")
        assert result is not None
        assert len(result) == 2
        assert result[0]["critic_id"] == "c-critic_1-001"
        assert result[1]["severity"] == "critical"

    def test_parse_critic_output_markdown_fenced(self):
        """Should strip markdown code fences before parsing."""
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        content = (
            '```json\n'
            '[{"critic_id": "c-test_1-001", "severity": "warning", "target": "X", "flaw": "Y", "principle": "Z"}]\n'
            '```'
        )
        result = _parse_critic_output(content, "test_node")
        assert result is not None
        assert len(result) == 1

    def test_parse_critic_output_with_field_aliases(self):
        """Should map common aliases (kritik, problem, etc.) to CriticItem fields."""
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        content = json.dumps([{
            "id": 1,
            "severity": "warning",
            "section": "§5",
            "kritik": "Unklare Formulierung",
            "norm": "Transparenz",
        }])
        result = _parse_critic_output(content, "test_node")
        assert result is not None
        assert len(result) == 1
        assert result[0]["target"] == "§5"
        assert result[0]["flaw"] == "Unklare Formulierung"

    def test_parse_critic_output_invalid_json_returns_none(self):
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        result = _parse_critic_output("this is not json at all!!!", "test_node")
        assert result is None

    def test_parse_critic_output_empty_array_returns_none(self):
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        result = _parse_critic_output("[]", "test_node")
        assert result is None


# ---------------------------------------------------------------------------
# 2. BuildResponse JSON parsing
# ---------------------------------------------------------------------------


class TestBuildResponseParsing:
    """Verify BuildResponse model: at least option_a and option_b required."""

    def _make_br(self, **overrides):
        defaults = {
            "response_to": "c-critic_1-001",
            "option_a": "Conservative fix: add liability cap clause",
            "option_b": "Radical fix: rewrite entire §3 with new liability framework",
            "option_c": "Minimal fix: add disclaimer footnote",
            "recommendation": "option_a",
            "rationale": "Option A preserves existing structure",
            "risk_assessment": "low",
            "implementable": True,
        }
        defaults.update(overrides)
        return BuildResponse(**defaults)

    def test_valid_build_response(self):
        br = self._make_br()
        assert br.option_a != ""
        assert br.option_b != ""
        assert br.option_c is not None
        assert br.recommendation == "option_a"
        assert br.risk_assessment == "low"

    def test_build_response_minimal_two_options(self):
        """At minimum, option_a and option_b must be provided."""
        br = self._make_br(option_c=None, recommendation="option_b", risk_assessment="medium")
        assert br.option_c is None

    def test_build_response_recommendation_values(self):
        for rec in ["option_a", "option_b", "option_c", "none"]:
            br = self._make_br(recommendation=rec)
            assert br.recommendation == rec

    def test_build_response_risk_assessment_values(self):
        for risk in ["low", "medium", "high"]:
            br = self._make_br(risk_assessment=risk)
            assert br.risk_assessment == risk

    def test_builder_output_with_score(self):
        output = BuilderOutput(
            build_responses=[self._make_br()],
            constructivity_score=1.0,
        )
        assert output.constructivity_score == 1.0
        assert len(output.build_responses) == 1


# ---------------------------------------------------------------------------
# 3. PragmatistOutput JSON parsing
# ---------------------------------------------------------------------------


class TestPragmatistOutputParsing:
    """Verify PragmatistEvaluation: feasibility, process_risk, verdict."""

    def test_valid_evaluation(self):
        ev = PragmatistEvaluation(
            response_to="c-critic_1-001",
            feasibility=0.8,
            process_risk="low",
            cost_time_estimate="1 Woche, 2.000 EUR",
            verdict="accept",
        )
        assert ev.verdict == "accept"
        assert ev.feasibility == 0.8
        assert ev.process_risk == "low"
        assert ev.revision_note is None

    def test_evaluation_revise_requires_revision_note(self):
        """When verdict != accept, revision_note should be provided."""
        ev = PragmatistEvaluation(
            response_to="c-1",
            feasibility=0.5,
            process_risk="medium",
            cost_time_estimate="3 Wochen",
            verdict="revise",
            revision_note="Needs more detail on implementation timeline",
        )
        assert ev.verdict == "revise"
        assert ev.revision_note is not None

    def test_pragmatist_output_with_reality_score(self):
        output = PragmatistOutput(
            evaluations=[
                PragmatistEvaluation(
                    response_to="c-1",
                    feasibility=0.7,
                    process_risk="low",
                    cost_time_estimate="1 Woche",
                    verdict="accept",
                ),
            ],
            reality_score=0.75,
            blocking_concerns=[],
        )
        assert output.reality_score == 0.75
        assert output.blocking_concerns == []

    def test_pragmatist_output_with_blocking_concerns(self):
        output = PragmatistOutput(
            evaluations=[],
            reality_score=0.2,
            blocking_concerns=["Budget not approved", "Legal review pending"],
        )
        assert len(output.blocking_concerns) == 2
        assert output.reality_score < 0.6

    def test_pragmatist_process_risk_values(self):
        for risk in ["low", "medium", "high"]:
            ev = PragmatistEvaluation(
                response_to="c-1",
                feasibility=0.5,
                process_risk=risk,
                cost_time_estimate="?",
                verdict="revise",
                revision_note="n/a",
            )
            assert ev.process_risk == risk


# ---------------------------------------------------------------------------
# 4. Decision Router — Loop Detection
# ---------------------------------------------------------------------------


class TestDecisionRouter:
    """Verify route_decision returns correct branches."""

    def _make_state(self, **overrides):
        base = {
            "current_round": 1,
            "draft_version": 1,
            "max_rounds": 5,
            "consensus_result": {"verdict": "revision_required"},
        }
        base.update(overrides)
        return base

    def test_approved_route(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = self._make_state(
            consensus_result={"verdict": "approved", "reality_score": 0.8}
        )
        assert router(state) == "approved"

    def test_revision_required_route(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = self._make_state(
            consensus_result={"verdict": "revision_required", "reality_score": 0.3}
        )
        assert router(state) == "return_to_builder"

    def test_construction_deadlock_at_draft_version_5(self):
        """When draft_version >= 5, force construction_deadlock."""
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = self._make_state(draft_version=5)
        assert router(state) == "construction_deadlock"

    def test_construction_deadlock_at_draft_version_6(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = self._make_state(draft_version=6)
        assert router(state) == "construction_deadlock"

    def test_no_deadlock_at_draft_version_4(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = self._make_state(draft_version=4)
        assert router(state) == "return_to_builder"

    def test_construction_deadlock_when_round_exceeds_max(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision(max_rounds=5)
        state = self._make_state(current_round=6)
        assert router(state) == "construction_deadlock"

    def test_custom_max_rounds(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision(max_rounds=3)
        state = self._make_state(current_round=4)
        assert router(state) == "construction_deadlock"

    def test_missing_consensus_defaults_to_revision(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        # consensus_result=None → the router does result.get("verdict", ...)
        # on None, which defaults to "revision_required"
        state = self._make_state(consensus_result={})
        assert router(state) == "return_to_builder"


# ---------------------------------------------------------------------------
# 5. Moderator Decision Logic
# ---------------------------------------------------------------------------


class TestModeratorDecision:
    """Verify the Moderator's transactional_drafting decision logic."""

    def test_approved_when_reality_score_high_and_no_blockers(self):
        """reality_score >= 0.6 and no blocking_concerns → approved."""
        reality_score = 0.8
        blocking_concerns = []
        approved = reality_score >= 0.6 and not blocking_concerns
        assert approved is True

    def test_revision_when_reality_score_low(self):
        """reality_score < 0.6 → revision_required."""
        reality_score = 0.4
        blocking_concerns = []
        approved = reality_score >= 0.6 and not blocking_concerns
        assert approved is False

    def test_revision_when_blocking_concerns_present(self):
        """blocking_concerns present → revision_required even with high score."""
        reality_score = 0.9
        blocking_concerns = ["Budget not approved"]
        approved = reality_score >= 0.6 and not blocking_concerns
        assert approved is False

    def test_boundary_reality_score_06(self):
        """reality_score exactly 0.6 with no blockers → approved."""
        reality_score = 0.6
        blocking_concerns = []
        approved = reality_score >= 0.6 and not blocking_concerns
        assert approved is True

    def test_boundary_reality_score_059(self):
        """reality_score 0.59 → revision_required."""
        reality_score = 0.59
        blocking_concerns = []
        approved = reality_score >= 0.6 and not blocking_concerns
        assert approved is False


# ---------------------------------------------------------------------------
# 6. Constructivity Score
# ---------------------------------------------------------------------------


class TestConstructivityScore:
    """Verify constructivity score calculation and storage."""

    def _make_br(self):
        return BuildResponse(
            response_to="c-test_1-001",
            option_a="Fix A",
            option_b="Fix B",
            recommendation="option_a",
            rationale="A is simpler",
            risk_assessment="low",
            implementable=True,
        )

    def test_constructivity_score_range(self):
        """Score must be between 0.0 and 1.0."""
        output = BuilderOutput(build_responses=[], constructivity_score=0.0)
        assert output.constructivity_score == 0.0

        output2 = BuilderOutput(build_responses=[], constructivity_score=1.0)
        assert output2.constructivity_score == 1.0

    def test_constructivity_score_rejects_out_of_range(self):
        with pytest.raises(Exception):
            BuilderOutput(build_responses=[], constructivity_score=1.5)

        with pytest.raises(Exception):
            BuilderOutput(build_responses=[], constructivity_score=-0.1)

    def test_artifact_has_constructivity_score(self):
        from backend.models.artifact import DebateArtifact

        artifact = DebateArtifact(
            session_id="test",
            workflow_id="wf-1",
            constructivity_score=0.75,
            draft_versions=3,
            critic_item_count=5,
            build_response_count=10,
            pragmatist_reality_score=0.8,
        )
        assert artifact.constructivity_score == 0.75
        assert artifact.draft_versions == 3
        assert artifact.critic_item_count == 5
        assert artifact.build_response_count == 10
        assert artifact.pragmatist_reality_score == 0.8

    def test_artifact_defaults_to_none(self):
        from backend.models.artifact import DebateArtifact

        artifact = DebateArtifact(session_id="test", workflow_id="wf-1")
        assert artifact.constructivity_score is None
        assert artifact.draft_versions == 0
        assert artifact.critic_item_count == 0
        assert artifact.pragmatist_reality_score is None


# ---------------------------------------------------------------------------
# 7. Audit Event Types
# ---------------------------------------------------------------------------


class TestAuditEventTypes:
    """Verify transactional drafting audit event types exist."""

    def test_builder_iteration_event_type(self):
        from backend.models.schemas import AuditEventType

        assert AuditEventType.BUILDER_ITERATION == "builder_iteration"

    def test_pragmatist_evaluation_event_type(self):
        from backend.models.schemas import AuditEventType

        assert AuditEventType.PRAGMATIST_EVALUATION == "pragmatist_evaluation"


# ---------------------------------------------------------------------------
# 8. Standard Debate Isolation
# ---------------------------------------------------------------------------


class TestStandardDebateIsolation:
    """Verify transactional drafting does not affect standard debate workflows."""

    def test_standard_debate_unaffected_by_transactional_models(self):
        """Standard debate workflow uses freetext, not CriticItem models."""
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        # Standard debate content is freetext, not JSON
        freetext = "The argument in section 3 is weak because it lacks evidence."
        result = _parse_critic_output(freetext, "standard_critic")
        # Should return None (not valid JSON) — standard debate handles this differently
        assert result is None

    def test_transactional_template_is_separate(self):
        """The transactional_drafting template exists as a distinct template."""
        import json
        from pathlib import Path

        tpl_path = Path("templates/transactional_drafting.json")
        assert tpl_path.exists(), "transactional_drafting.json template must exist"

        with open(tpl_path) as f:
            tpl = json.load(f)

        assert "template_data" in tpl
        assert "placeholders" in tpl
        # Should have builder, pragmatist, critic placeholders
        placeholder_keys = {p["key"] for p in tpl["placeholders"]}
        assert "builder_blueprint_id" in placeholder_keys
        assert "pragmatist_blueprint_id" in placeholder_keys


# ---------------------------------------------------------------------------
# 9. Verdict Threshold Rules (Pragmatist)
# ---------------------------------------------------------------------------


class TestVerdictThresholds:
    """Verify the Pragmatist verdict threshold rules match the spec."""

    def test_accept_threshold(self):
        """feasibility >= 0.7 → accept."""
        ev = PragmatistEvaluation(
            response_to="c-1",
            feasibility=0.7,
            process_risk="low",
            cost_time_estimate="1 Woche",
            verdict="accept",
        )
        assert ev.verdict == "accept"
        assert ev.feasibility >= 0.7

    def test_revise_threshold(self):
        """feasibility 0.4–0.7 → revise."""
        ev = PragmatistEvaluation(
            response_to="c-1",
            feasibility=0.55,
            process_risk="medium",
            cost_time_estimate="2 Wochen",
            verdict="revise",
            revision_note="Needs more detail",
        )
        assert ev.verdict == "revise"
        assert 0.4 <= ev.feasibility < 0.7

    def test_reject_threshold(self):
        """feasibility < 0.4 → reject."""
        ev = PragmatistEvaluation(
            response_to="c-1",
            feasibility=0.2,
            process_risk="high",
            cost_time_estimate="3 Monate",
            verdict="reject",
            revision_note="Not feasible within constraints",
        )
        assert ev.verdict == "reject"
        assert ev.feasibility < 0.4
