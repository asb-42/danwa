"""Tests for PrintOutputPlugin, PrintPluginConfig, and PrintLayoutEngine."""

from __future__ import annotations

from backend.models.artifact import (
    DebateArtifact,
    Injection,
    MinorityVote,
    Turn,
    UserQuery,
)
from backend.services.output.plugins.print_layout_engine import PrintLayoutEngine
from backend.services.output.plugins.print_models import (
    MarginNoteType,
    SectionType,
)
from backend.services.output.plugins.print_plugin import (
    PrintFormat,
    PrintOutputPlugin,
    PrintPluginConfig,
    PrintTemplate,
)


class TestPrintPluginConfig:
    def test_defaults(self) -> None:
        c = PrintPluginConfig()
        assert c.template_name == PrintTemplate.ACADEMIC_DEBATE
        assert c.include_audit_trail is True
        assert c.include_minority_votes is True
        assert c.primary_format == PrintFormat.PDF
        assert c.language == "de"

    def test_custom(self) -> None:
        c = PrintPluginConfig(
            template_name=PrintTemplate.MINIMAL,
            primary_format=PrintFormat.ALL,
            language="en",
        )
        assert c.template_name == PrintTemplate.MINIMAL
        assert c.primary_format == PrintFormat.ALL


class TestPrintLayoutEngine:
    def _make_artifact(self) -> DebateArtifact:
        return DebateArtifact(
            session_id="s1",
            workflow_id="w1",
            workflow_name="Test Workflow",
            topic="AI Ethics",
            transcript=[
                Turn(
                    id="t1",
                    round=1,
                    node_id="n1",
                    agent_name="Alice",
                    role_type="strategist",
                    content="Argument A",
                ),
                Turn(
                    id="t2",
                    round=1,
                    node_id="n2",
                    agent_name="Bob",
                    role_type="critic",
                    content="Counter B",
                ),
            ],
            interjections=[
                Injection(
                    id="ij1",
                    source="user",
                    target_node_id="n1",
                    content="Consider X",
                    injected_at_round=1,
                ),
            ],
            user_queries=[
                UserQuery(id="q1", content="Why A?", response_turn_id="t1"),
            ],
            minority_votes=[
                MinorityVote(
                    id="mv1",
                    agent_name="Carol",
                    dissent_content="I disagree with consensus",
                    target_turn_id="t2",
                ),
            ],
            consensus_result={"score": 0.85, "summary": "Good debate"},
            metadata={},
        )

    def test_rule_a_turns(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact(), include_audit_trail=False)
        turn_sections = [s for s in doc.sections if s.type == SectionType.TURN]
        assert len(turn_sections) == 2
        assert turn_sections[0].agent_name == "Alice"
        assert turn_sections[1].agent_name == "Bob"

    def test_rule_b_injections_as_margin_notes(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact())
        turn_sections = [s for s in doc.sections if s.type == SectionType.TURN]
        # First turn (n1) should have injection margin note
        assert len(turn_sections[0].margin_notes) == 1
        assert turn_sections[0].margin_notes[0].type == MarginNoteType.INJECTION
        # The ``markdown`` library is not installed in the test env, so
        # ``_md_to_html`` falls back to returning the raw text. The test
        # asserts the raw text is preserved.
        assert "Consider X" in turn_sections[0].margin_notes[0].content
        # Second turn (n2) should have no margin notes
        assert len(turn_sections[1].margin_notes) == 0

    def test_rule_c_user_queries(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact())
        query_sections = [s for s in doc.sections if s.type == SectionType.USER_QUERY_BLOCK]
        assert len(query_sections) == 1
        # Same markdown-fallback as above: raw text preserved.
        assert "Why A?" in query_sections[0].content

    def test_rule_d_minority_votes(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact(), include_minority_votes=True)
        minority_sections = [s for s in doc.sections if s.type == SectionType.MINORITY_CALLOUT]
        assert len(minority_sections) == 1
        assert "Carol" in minority_sections[0].title

    def test_rule_e_consensus(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact())
        consensus = [s for s in doc.sections if s.type == SectionType.CONSENSUS_SUMMARY]
        assert len(consensus) == 1
        assert "0.85" in consensus[0].content

    def test_rule_f_audit_trail(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact(), include_audit_trail=True)
        audit = [s for s in doc.sections if s.type == SectionType.AUDIT_APPENDIX]
        assert len(audit) == 1

    def test_no_audit_when_disabled(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact(), include_audit_trail=False)
        audit = [s for s in doc.sections if s.type == SectionType.AUDIT_APPENDIX]
        assert len(audit) == 0

    def test_metadata(self) -> None:
        engine = PrintLayoutEngine()
        doc = engine.transform(self._make_artifact())
        assert doc.metadata.topic == "AI Ethics"
        assert "Alice" in doc.metadata.participants
        assert "Bob" in doc.metadata.participants


class TestPrintOutputPlugin:
    def test_plugin_properties(self) -> None:
        assert PrintOutputPlugin.plugin_key == "print"
        assert "pdf" in PrintOutputPlugin.supported_formats
        assert "docx" in PrintOutputPlugin.supported_formats
        assert "odt" in PrintOutputPlugin.supported_formats
        assert "md" in PrintOutputPlugin.supported_formats
