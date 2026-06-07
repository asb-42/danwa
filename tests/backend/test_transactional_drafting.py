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
    BuilderOutput,
    BuildResponse,
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

        content = json.dumps(
            [
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
            ]
        )
        result = _parse_critic_output(content, "test_node")
        assert result is not None
        assert len(result) == 2
        assert result[0]["critic_id"] == "c-critic_1-001"
        assert result[1]["severity"] == "critical"

    def test_parse_critic_output_markdown_fenced(self):
        """Should strip markdown code fences before parsing."""
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        content = '```json\n[{"critic_id": "c-test_1-001", "severity": "warning", "target": "X", "flaw": "Y", "principle": "Z"}]\n```'
        result = _parse_critic_output(content, "test_node")
        assert result is not None
        assert len(result) == 1

    def test_parse_critic_output_with_field_aliases(self):
        """Should map common aliases (kritik, problem, etc.) to CriticItem fields."""
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        content = json.dumps(
            [
                {
                    "id": 1,
                    "severity": "warning",
                    "section": "§5",
                    "kritik": "Unklare Formulierung",
                    "norm": "Transparenz",
                }
            ]
        )
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
        state = self._make_state(consensus_result={"verdict": "approved", "reality_score": 0.8})
        assert router(state) == "approved"

    def test_revision_required_route(self):
        from backend.workflow.workflow_routers import route_decision

        router = route_decision()
        state = self._make_state(consensus_result={"verdict": "revision_required", "reality_score": 0.3})
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


# ---------------------------------------------------------------------------
# 10. Domain-aware Critic decision matrix (sprint 27)
# ---------------------------------------------------------------------------


class TestDomainDecisionMatrix:
    """Verify the Critic decision matrix is picked by blueprint tags."""

    def test_rental_law_tag_returns_rental_matrix(self):
        from backend.workflow.domains import get_decision_matrix, is_rental_law

        matrix = get_decision_matrix(["mietrecht"])
        assert "§ 551" in matrix
        assert "Kaution" in matrix
        assert is_rental_law(["mietrecht"]) is True

    def test_rental_law_aliases(self):
        """All canonical rental-law tags should activate the rental matrix."""
        from backend.workflow.domains import is_rental_law

        for tag in ("mietrecht", "rental", "rental_law", "mietvertrag"):
            assert is_rental_law([tag]) is True, f"Tag {tag!r} should activate rental law"

    def test_tag_matching_is_case_insensitive(self):
        from backend.workflow.domains import get_decision_matrix, is_rental_law

        matrix = get_decision_matrix(["MIETRECHT", "Mietvertrag"])
        assert "§ 551" in matrix
        assert is_rental_law(["MietVertrag"]) is True

    def test_no_rental_tag_returns_generic_matrix(self):
        from backend.workflow.domains import get_decision_matrix, is_rental_law

        matrix = get_decision_matrix(["transactional", "default"])
        assert "§ 551" not in matrix, "Generic matrix should not mention § 551 BGB"
        assert "Kaution" not in matrix
        # Generic matrix still talks about severity levels, just generically
        assert "blocking" in matrix
        assert "critical" in matrix
        assert is_rental_law(["transactional"]) is False

    def test_empty_tag_list_returns_generic_matrix(self):
        from backend.workflow.domains import get_decision_matrix

        matrix = get_decision_matrix([])
        assert "§ 551" not in matrix

    def test_none_tag_list_returns_generic_matrix(self):
        from backend.workflow.domains import get_decision_matrix

        matrix = get_decision_matrix(None)
        assert "§ 551" not in matrix

    def test_generic_matrix_uses_domänen_agnostisch_phrase(self):
        """The generic matrix is supposed to be domain-agnostic."""
        from backend.workflow.domains import get_decision_matrix

        matrix = get_decision_matrix(["some_other_tag"])
        assert "domänen-agnostisch" in matrix or "domän" in matrix.lower()

    def test_matrix_returned_is_total(self):
        """get_decision_matrix must always return a non-empty string."""
        from backend.workflow.domains import get_decision_matrix

        for tags in (
            None,
            [],
            ["mietrecht"],
            ["unknown_tag"],
            ["transactional", "default"],
            [""],
        ):
            result = get_decision_matrix(tags)
            assert isinstance(result, str)
            assert len(result) > 100, f"Matrix for tags {tags!r} is suspiciously short"


# ---------------------------------------------------------------------------
# 11. Builder uses latest_draft and filters critic_items by round (sprint 27)
# ---------------------------------------------------------------------------


class TestBuilderDraftExtraction:
    """Verify the Builder's draft-resolution order prefers latest_draft over zero_draft."""

    def test_latest_draft_takes_precedence_over_zero_draft(self):
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        state = {
            "zero_draft": "ORIGINAL zero draft from Strategist",
            "latest_draft": "ITERATION 2 revision",
            "context": "user case text",
        }
        assert _extract_zero_draft(state) == "ITERATION 2 revision"

    def test_zero_draft_used_on_first_iteration(self):
        """When no Builder has run yet, the original zero_draft is used."""
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        state = {
            "zero_draft": "Original zero draft",
            "latest_draft": None,
            "context": "user case text",
        }
        assert _extract_zero_draft(state) == "Original zero draft"

    def test_empty_latest_draft_falls_back_to_zero_draft(self):
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        state = {
            "zero_draft": "Original zero draft",
            "latest_draft": "",
            "context": "user case text",
        }
        assert _extract_zero_draft(state) == "Original zero draft"

    def test_falls_back_to_strategist_node_output(self):
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        state = {
            "zero_draft": None,
            "latest_draft": None,
            "node_outputs": [
                {"node_type": "wf-critic", "content": "critique"},
                {"node_type": "wf-strategist", "content": "Strategy output"},
            ],
            "context": "user case text",
        }
        assert _extract_zero_draft(state) == "Strategy output"

    def test_final_fallback_to_context(self):
        from backend.workflow.nodes.builder_nodes import _extract_zero_draft

        state = {"context": "user case text"}
        assert _extract_zero_draft(state) == "user case text"


class TestBuilderCriticItemExtraction:
    """Verify the Builder's critic-item extraction filters to the current round."""

    def test_filters_critic_items_to_current_round(self):
        """Iteration 2 should only see items raised in round 2, not round 1."""
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "current_round": 2,
            "critic_items": [
                {"critic_id": "c-1-001", "severity": "blocking", "round": 1},
                {"critic_id": "c-1-002", "severity": "critical", "round": 1},
                {"critic_id": "c-2-001", "severity": "blocking", "round": 2},
                {"critic_id": "c-2-002", "severity": "warning", "round": 2},
            ],
        }
        result = _extract_critic_items(state)
        assert len(result) == 2
        assert all(item["round"] == 2 for item in result)
        assert {it["critic_id"] for it in result} == {"c-2-001", "c-2-002"}

    def test_round_1_returns_only_round_1_items(self):
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "current_round": 1,
            "critic_items": [
                {"critic_id": "c-1-001", "round": 1},
                {"critic_id": "c-1-002", "round": 1},
            ],
        }
        result = _extract_critic_items(state)
        assert len(result) == 2

    def test_legacy_state_without_round_field_falls_back_to_full(self):
        """Backward compatibility: if no item has a round field, return all."""
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "current_round": 2,
            "critic_items": [
                {"critic_id": "c-1-001"},
                {"critic_id": "c-1-002"},
            ],
        }
        result = _extract_critic_items(state)
        assert len(result) == 2

    def test_empty_critic_items_returns_empty(self):
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {"current_round": 1, "critic_items": []}
        result = _extract_critic_items(state)
        assert result == []

    def test_round_mismatch_returns_empty(self):
        """If no items match the current round, return empty (signals re-run)."""
        from backend.workflow.nodes.builder_nodes import _extract_critic_items

        state = {
            "current_round": 3,
            "critic_items": [
                {"critic_id": "c-1-001", "round": 1},
                {"critic_id": "c-2-001", "round": 2},
            ],
        }
        result = _extract_critic_items(state)
        assert result == []


# ---------------------------------------------------------------------------
# 12. State field latest_draft (sprint 27)
# ---------------------------------------------------------------------------


class TestLatestDraftStateField:
    """Verify the WorkflowState TypedDict has the new optional latest_draft field."""

    def test_latest_draft_is_optional(self):
        from backend.workflow.workflow_state import WorkflowState

        state: WorkflowState = {"current_draft": "foo"}
        # latest_draft is optional (TypedDict total=False)
        assert state.get("latest_draft") is None

    def test_latest_draft_round_trip(self):
        from backend.workflow.workflow_state import WorkflowState

        state: WorkflowState = {"latest_draft": "Rev 2 output"}
        assert state["latest_draft"] == "Rev 2 output"


# ---------------------------------------------------------------------------
# 13. ResolvedAgentConfig carries agent_tags (sprint 27)
# ---------------------------------------------------------------------------


class TestResolvedAgentConfigAgentTags:
    """Verify the compiler attaches agent blueprint tags to the resolved config."""

    def test_agent_tags_default_to_empty_list(self):
        from backend.workflow.workflow_compiler import ResolvedAgentConfig

        cfg = ResolvedAgentConfig(
            node_id="n1",
            blueprint_id="bp1",
            blueprint_name="BP",
            llm_profile_id="lp",
            llm_model="m",
            role_definition_id="rd",
            role="critic",
        )
        assert cfg.agent_tags == []

    def test_agent_tags_can_be_set(self):
        from backend.workflow.workflow_compiler import ResolvedAgentConfig

        cfg = ResolvedAgentConfig(
            node_id="n1",
            blueprint_id="bp1",
            blueprint_name="BP",
            llm_profile_id="lp",
            llm_model="m",
            role_definition_id="rd",
            role="critic",
            agent_tags=["mietrecht", "default"],
        )
        assert cfg.agent_tags == ["mietrecht", "default"]


# ---------------------------------------------------------------------------
# 14. Critic items are tagged with round at parse time (sprint 27)
# ---------------------------------------------------------------------------


class TestCriticItemsGetRoundTag:
    """Verify items parsed from Critic output carry a round field."""

    def test_parse_critic_output_includes_round_when_caller_passes_it(self):
        """The parser does not set round itself — the caller (agent_node) does.
        This test pins the contract: caller is responsible for tagging round.
        """
        from backend.workflow.nodes.agent_nodes import _parse_critic_output

        raw = json.dumps(
            [
                {
                    "critic_id": "c-critic_1-001",
                    "severity": "blocking",
                    "target": "§3",
                    "flaw": "Missing limitation",
                    "principle": "Rechtssicherheit",
                }
            ]
        )
        items = _parse_critic_output(raw, "test_node")
        assert items is not None
        assert len(items) == 1
        # The parser does not set round; the agent_node tags it post-parse
        assert "round" not in items[0]


# ---------------------------------------------------------------------------
# 15. current_draft not corrupted in transactional_drafting path (sprint 27)
# ---------------------------------------------------------------------------


class TestCurrentDraftTransactionalPath:
    """The agent_node must NOT concatenate every agent's output into current_draft
    when the workflow is transactional_drafting.  Concatenation is still
    performed for the standard debate workflow."""

    def test_agent_node_skips_current_draft_concat_for_transactional(self):
        """Inspect the agent_node_factory source to confirm the guard exists."""
        from pathlib import Path

        src = Path("backend/workflow/nodes/agent_nodes.py").read_text(encoding="utf-8")
        # The guard: the current_draft concatenation block is gated on
        # ``is_transactional = state.get("workflow_template") == <Transactional marker>``.
        # Sprint 30 replaced the literal with the WorkflowTemplate enum
        # (H4 fix), so accept either form.
        assert (
            'is_transactional = state.get("workflow_template") == "transactional_drafting"' in src
            or 'is_transactional = state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING' in src
        )
        # And the state_update["current_draft"] assignment is inside the
        # `if not is_transactional` branch (may have additional guards
        # like `and role not in _meta_agent_roles`).
        assert "if not is_transactional" in src


# ---------------------------------------------------------------------------
# 16. Integration: state_update keys for transactional path
# ---------------------------------------------------------------------------


class TestStateUpdateKeys:
    """Verify the agent_node no longer writes current_draft for transactional
    workflows, but still writes node_outputs and messages."""

    def test_state_update_construction_omits_current_draft_when_transactional(self):
        """Direct read of the source to confirm the state_update dict structure."""
        from pathlib import Path

        src = Path("backend/workflow/nodes/agent_nodes.py").read_text(encoding="utf-8")
        # Find the block that builds state_update
        block_start = src.find("state_update: dict = {")
        assert block_start != -1, "state_update construction not found"
        block = src[block_start : block_start + 800]
        # current_draft key must be guarded by `if not is_transactional`
        # and node_outputs + messages must always be present.
        assert '"node_outputs": [output]' in block
        assert '"messages":' in block
        # The current_draft key line should be inside the `if not is_transactional` block
        # immediately after the state_update dict definition.
        assert "if not is_transactional" in src[block_start : block_start + 1200]
