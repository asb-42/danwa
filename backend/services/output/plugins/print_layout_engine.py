"""PrintLayoutEngine — transforms DebateArtifact into PrintDocument.

Applies the academic_debate template rules to produce a semantic
layout that can be rendered to HTML by Jinja2 templates.

Template rules (academic_debate):
  a) Each Turn → PrintSection(type=turn)
  b) Injections → MarginNote on matching Turn section (by target_node_id)
  c) UserQueries → standalone PrintSection(type=user_query_block) before the referenced round
  d) MinorityVotes → PrintSection(type=minority_callout) with visual emphasis
  e) consensus_result → PrintSection(type=consensus_summary) at the end
  f) If include_audit_trail: PrintSection(type=audit_appendix) with agent/latency/tokens table
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime

from backend.models.artifact import DebateArtifact
from backend.services.output.plugins.print_models import (
    MarginNote,
    MarginNoteType,
    PrintDocument,
    PrintMetadata,
    PrintSection,
    SectionType,
)

logger = logging.getLogger(__name__)


class PrintLayoutEngine:
    """Transforms a ``DebateArtifact`` into a ``PrintDocument``.

    Stateless — a fresh instance is created per render call.
    Content is converted from Markdown to HTML during transformation.
    """

    @staticmethod
    def _md_to_html(text: str) -> str:
        """Convert Markdown text to HTML, preserving empty strings."""
        if not text:
            return ""
        try:
            import markdown
            return markdown.markdown(
                text,
                extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
            )
        except ImportError:
            # Fallback: basic line-break conversion
            return text.replace("\n", "<br>")

    def transform(
        self,
        artifact: DebateArtifact,
        include_audit_trail: bool = True,
        include_minority_votes: bool = True,
    ) -> PrintDocument:
        """Build a ``PrintDocument`` from the artifact.

        Args:
            artifact: The debate artifact to transform.
            include_audit_trail: Whether to append an audit appendix.
            include_minority_votes: Whether to include minority callouts.

        Returns:
            A ``PrintDocument`` ready for HTML rendering.
        """
        sections: list[PrintSection] = []

        # Build lookup maps
        injections_by_node = self._group_injections_by_node(artifact)
        queries_by_round = self._group_queries_by_round(artifact)
        minority_by_turn = self._group_minority_by_turn(artifact)

        # Collect all rounds from transcript
        rounds = sorted({t.round for t in artifact.transcript})

        for rnd in rounds:
            # (c) UserQueries before this round
            queries = queries_by_round.get(rnd, [])
            for q in queries:
                sections.append(
                    PrintSection(
                        type=SectionType.USER_QUERY_BLOCK,
                        title=f"Nutzerfrage (Runde {rnd})",
                        content=self._md_to_html(q.content),
                        timestamp=q.timestamp,
                        round=rnd,
                        css_class="user-query-block",
                    )
                )

            # (a) Turns for this round
            round_turns = [t for t in artifact.transcript if t.round == rnd]
            for turn in round_turns:
                # (b) Attach injections as margin notes
                margin_notes: list[MarginNote] = []
                injections = injections_by_node.get(turn.node_id, [])
                for inj in injections:
                    margin_notes.append(
                        MarginNote(
                            type=MarginNoteType.INJECTION,
                            content=self._md_to_html(inj.content),
                            reference_id=inj.id,
                        )
                    )

                sections.append(
                    PrintSection(
                        type=SectionType.TURN,
                        title=f"{turn.agent_name} ({turn.role_type})",
                        content=self._md_to_html(turn.content),
                        agent_name=turn.agent_name,
                        timestamp=turn.timestamp,
                        round=turn.round,
                        margin_notes=margin_notes,
                        css_class="debate-turn",
                    )
                )

                # (d) MinorityVotes for this turn
                if include_minority_votes:
                    votes = minority_by_turn.get(turn.id, [])
                    for vote in votes:
                        sections.append(
                            PrintSection(
                                type=SectionType.MINORITY_CALLOUT,
                                title=f"Minderheitsvotum: {vote.agent_name}",
                                content=self._md_to_html(vote.dissent_content),
                                agent_name=vote.agent_name,
                                timestamp=vote.timestamp,
                                round=turn.round,
                                css_class="minority-callout",
                            )
                        )

        # (e) Consensus summary
        if artifact.consensus_result:
            consensus_content = self._md_to_html(self._format_consensus(artifact.consensus_result))
            sections.append(
                PrintSection(
                    type=SectionType.CONSENSUS_SUMMARY,
                    title="Konsens-Zusammenfassung",
                    content=self._md_to_html(consensus_content),
                    css_class="consensus-summary",
                )
            )

        # (f) Audit trail appendix
        if include_audit_trail:
            sections.append(self._build_audit_appendix(artifact))

        # Build metadata
        participants = list(
            {t.agent_name for t in artifact.transcript if t.agent_name}
        )
        total_tokens = sum(
            t.token_usage.get("total", 0) for t in artifact.transcript
        )
        metadata = self._build_metadata(artifact, participants, total_tokens)

        return PrintDocument(sections=sections, metadata=metadata)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _group_injections_by_node(
        artifact: DebateArtifact,
    ) -> dict[str, list]:
        """Group injections by their target_node_id."""
        result: dict[str, list] = defaultdict(list)
        for inj in artifact.interjections:
            result[inj.target_node_id].append(inj)
        return dict(result)

    @staticmethod
    def _group_queries_by_round(
        artifact: DebateArtifact,
    ) -> dict[int, list]:
        """Group user queries by the round they relate to.

        Uses the round of the response_turn_id if available,
        otherwise places them at round 0.
        """
        result: dict[int, list] = defaultdict(list)
        # Build turn_id → round map
        turn_rounds = {t.id: t.round for t in artifact.transcript}
        for q in artifact.user_queries:
            rnd = turn_rounds.get(q.response_turn_id, 0) if q.response_turn_id else 0
            result[rnd].append(q)
        return dict(result)

    @staticmethod
    def _group_minority_by_turn(
        artifact: DebateArtifact,
    ) -> dict[str, list]:
        """Group minority votes by their target_turn_id."""
        result: dict[str, list] = defaultdict(list)
        for vote in artifact.minority_votes:
            result[vote.target_turn_id].append(vote)
        return dict(result)

    @staticmethod
    def _format_consensus(consensus: dict) -> str:
        """Format consensus_result dict into readable text."""
        parts: list[str] = []
        if "score" in consensus:
            parts.append(f"Konsens-Score: {consensus['score']}")
        if "summary" in consensus:
            parts.append(consensus["summary"])
        if "key_agreements" in consensus:
            agreements = consensus["key_agreements"]
            if isinstance(agreements, list):
                parts.append("Zentrale Einigungen:")
                for a in agreements:
                    parts.append(f"  • {a}")
        return "\n".join(parts) if parts else str(consensus)

    @staticmethod
    def _build_audit_appendix(artifact: DebateArtifact) -> PrintSection:
        """Build the audit trail appendix section."""
        rows: list[str] = []
        for turn in artifact.transcript:
            tokens = turn.token_usage.get("total", 0)
            rows.append(
                f"{turn.agent_name} | {turn.role_type} | "
                f"{turn.llm_profile_id} | {turn.latency_ms}ms | {tokens} tokens"
            )
        content = "\n".join(rows) if rows else "Keine Audit-Daten verfügbar."
        return PrintSection(
            type=SectionType.AUDIT_APPENDIX,
            title="Audit-Trail",
            content=content,
            css_class="audit-appendix",
        )

    @staticmethod
    def _build_metadata(
        artifact: DebateArtifact,
        participants: list[str],
        total_tokens: int,
    ) -> PrintMetadata:
        """Build PrintMetadata from the artifact."""
        # Calculate duration from metadata timestamps
        duration = ""
        timestamps = artifact.metadata.get("timestamps", {})
        if timestamps:
            start = timestamps.get("start", "")
            end = timestamps.get("end", "")
            if start and end:
                try:
                    t_start = datetime.fromisoformat(start)
                    t_end = datetime.fromisoformat(end)
                    delta = t_end - t_start
                    minutes = int(delta.total_seconds() // 60)
                    seconds = int(delta.total_seconds() % 60)
                    duration = f"{minutes}m {seconds}s"
                except (ValueError, TypeError):
                    duration = f"{start} → {end}"

        return PrintMetadata(
            topic=artifact.topic,
            workflow_name=artifact.workflow_name,
            participants=sorted(participants),
            duration=duration,
            total_tokens=total_tokens,
        )
