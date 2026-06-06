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
    TOCEntry,
)


def _fmt_marginalia(metadata: dict) -> str:
    """Build an HTML marginalia line from Turn metadata (provenance)."""
    prov = metadata.get("provenance", {})
    if not prov or not prov.get("critic_item_id"):
        return ""
    parts = []
    dv = prov.get("draft_version")
    if dv:
        parts.append(f"revidiert in Iteration {dv}")
    ci = prov.get("critic_item_id", "")
    parts.append(f"Critic: {ci}")
    rt = prov.get("revision_type", "")
    if rt == "conservative":
        parts.append("Builder: Option A")
    elif rt == "radical":
        parts.append("Builder: Option B")
    elif rt == "minimal":
        parts.append("Builder: Option C")
    pv = prov.get("pragmatist_verdict")
    ps = prov.get("pragmatist_score")
    if pv and ps is not None:
        parts.append(f"Pragmatist: {pv} ({ps})")
    return " | ".join(parts)


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
        include_toc: bool = True,
    ) -> PrintDocument:
        """Build a ``PrintDocument`` from the artifact.

        Args:
            artifact: The debate artifact to transform.
            include_audit_trail: Whether to append an audit appendix.
            include_minority_votes: Whether to include minority callouts.
            include_toc: Whether to build a Table of Contents.

        Returns:
            A ``PrintDocument`` ready for HTML rendering.
        """
        import re

        # Defensive: strip system-internal nodes from stored artifacts
        # that were persisted before the export-pipeline fix.
        _system_roles = {"complete", "input", "initialize"}
        artifact.transcript = [t for t in artifact.transcript if t.role_type not in _system_roles]

        sections: list[PrintSection] = []
        toc: list[TOCEntry] = []
        section_idx = 0

        def _make_id(prefix: str, idx: int) -> str:
            return f"{prefix}-{idx}"

        def _inject_heading_ids(html_content: str, base_id: str) -> tuple[str, list[TOCEntry]]:
            """Inject ``id`` attributes into h1/h2 headings for TOC anchoring.

            Returns the modified HTML (with ``id`` attributes added) and a
            list of :class:`TOCEntry` objects extracted from the headings.
            """
            entries: list[TOCEntry] = []
            heading_re = re.compile(r"<(h[12])([^>]*)>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
            counter = 0

            def _replace(m: re.Match) -> str:
                nonlocal counter
                tag = m.group(1).lower()
                attrs = m.group(2)
                inner = m.group(3)
                title = re.sub(r"<[^>]+>", "", inner).strip()
                level = 1 if tag == "h1" else 2
                hid = f"{base_id}-h{counter}"
                entries.append(TOCEntry(level=level, title=title, anchor=hid))
                counter += 1
                # Inject id attribute (avoid duplicating existing id)
                if "id=" not in attrs:
                    return f'<{tag} id="{hid}"{attrs}>{inner}</{tag}>'
                return m.group(0)

            modified = heading_re.sub(_replace, html_content)
            return modified, entries

        # Build lookup maps
        injections_by_node = self._group_injections_by_node(artifact)
        queries_by_round = self._group_queries_by_round(artifact)
        minority_by_turn = self._group_minority_by_turn(artifact)

        # --- Title (with Title tags) ---
        title_text = artifact.title or artifact.topic[:80]
        title_id = _make_id("title", section_idx)
        title_html = f'<h1 class="debate-title">{self._escape(title_text)}</h1>'
        toc.append(TOCEntry(level=1, title=title_text, anchor=title_id))
        sections.append(
            PrintSection(
                id=title_id,
                type=SectionType.TITLE,
                title=title_text,
                content=title_html,
                css_class="debate-title",
            )
        )
        section_idx += 1

        # --- Metadata (rounds, agent roles, LLM mapping) ---
        meta = self._build_metadata_block(artifact)
        meta_id = _make_id("meta", section_idx)
        sections.append(
            PrintSection(
                id=meta_id,
                type=SectionType.METADATA,
                title="Metadaten",
                content=meta,
                css_class="debate-metadata",
            )
        )
        section_idx += 1

        # --- Case description (full text, no Title tags) ---
        if artifact.topic:
            case_id = _make_id("case", section_idx)
            case_html = f'<h2>Fallbeschreibung</h2><div class="case-text">{self._escape(artifact.topic)}</div>'
            toc.append(TOCEntry(level=1, title="Fallbeschreibung", anchor=case_id))
            sections.append(
                PrintSection(
                    id=case_id,
                    type=SectionType.CASE_DESCRIPTION,
                    title="Fallbeschreibung",
                    content=case_html,
                    css_class="case-description",
                )
            )
            section_idx += 1

        # --- Executive Summary (Page 1) ---
        exec_sid = _make_id("exec", section_idx)
        exec_html = self._build_executive_summary(artifact)
        if exec_html:
            toc.append(TOCEntry(level=1, title="Executive Summary", anchor=exec_sid))
            sections.append(
                PrintSection(
                    id=exec_sid,
                    type=SectionType.EXECUTIVE_SUMMARY,
                    title="Executive Summary",
                    content=exec_html,
                    css_class="executive-summary",
                )
            )
            section_idx += 1

        # Collect all rounds from transcript
        rounds = sorted({t.round for t in artifact.transcript})

        for rnd in rounds:
            # Level 1 TOC: Round — anchor will be set to first turn's id
            # Insert a placeholder; we'll fix the anchor after seeing the first turn
            round_toc_idx = len(toc)  # remember position
            toc.append(TOCEntry(level=1, title=f"Runde {rnd}", anchor=""))

            # (c) UserQueries before this round
            queries = queries_by_round.get(rnd, [])
            for q in queries:
                sid = _make_id("query", section_idx)
                sections.append(
                    PrintSection(
                        id=sid,
                        type=SectionType.USER_QUERY_BLOCK,
                        title=f"Nutzerfrage (Runde {rnd})",
                        content=self._md_to_html(q.content),
                        timestamp=q.timestamp,
                        round=rnd,
                        css_class="user-query-block",
                    )
                )
                section_idx += 1

            # (a) Turns for this round
            round_turns = [t for t in artifact.transcript if t.round == rnd]
            for turn in round_turns:
                sid = _make_id("turn", section_idx)
                # Set round TOC anchor to first turn in this round
                if toc[round_toc_idx].anchor == "":
                    toc[round_toc_idx].anchor = sid
                # Level 2 TOC: Agent
                toc.append(
                    TOCEntry(
                        level=2,
                        title=f"{turn.agent_name} ({turn.role_type})",
                        anchor=sid,
                    )
                )

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

                # (b2) Attach provenance marginalia for builder turns
                if turn.role_type == "builder":
                    marginalia = _fmt_marginalia(turn.metadata)
                    if marginalia:
                        margin_notes.append(
                            MarginNote(
                                type=MarginNoteType.PROVENANCE,
                                content=self._md_to_html(marginalia),
                                reference_id=turn.id,
                            )
                        )

                content_html = self._md_to_html(turn.content)

                # Level 3 TOC: headings within content
                if include_toc:
                    content_html, heading_entries = _inject_heading_ids(content_html, sid)
                    toc.extend(heading_entries)

                sections.append(
                    PrintSection(
                        id=sid,
                        type=SectionType.TURN,
                        title=f"{turn.agent_name} ({turn.role_type})",
                        content=content_html,
                        agent_name=turn.agent_name,
                        timestamp=turn.timestamp,
                        round=turn.round,
                        margin_notes=margin_notes,
                        css_class="debate-turn",
                    )
                )
                section_idx += 1

                # (d) MinorityVotes for this turn
                if include_minority_votes:
                    votes = minority_by_turn.get(turn.id, [])
                    for vote in votes:
                        sections.append(
                            PrintSection(
                                id=_make_id("minority", section_idx),
                                type=SectionType.MINORITY_CALLOUT,
                                title=f"Minderheitsvotum: {vote.agent_name}",
                                content=self._md_to_html(vote.dissent_content),
                                agent_name=vote.agent_name,
                                timestamp=vote.timestamp,
                                round=turn.round,
                                css_class="minority-callout",
                            )
                        )
                        section_idx += 1

        # (e) Consensus summary
        if artifact.consensus_result:
            consensus_content = self._md_to_html(self._format_consensus(artifact.consensus_result))
            sid = _make_id("consensus", section_idx)
            toc.append(TOCEntry(level=1, title="Konsens-Zusammenfassung", anchor=sid))
            sections.append(
                PrintSection(
                    id=sid,
                    type=SectionType.CONSENSUS_SUMMARY,
                    title="Konsens-Zusammenfassung",
                    content=consensus_content,
                    css_class="consensus-summary",
                )
            )
            section_idx += 1

        # (f) Audit trail appendix
        if include_audit_trail:
            audit = self._build_audit_appendix(artifact)
            audit.id = _make_id("audit", section_idx)
            toc.append(TOCEntry(level=1, title="Audit-Trail", anchor=audit.id))
            sections.append(audit)
            section_idx += 1

        # Build metadata
        participants = list({t.agent_name for t in artifact.transcript if t.agent_name})
        total_tokens = sum(t.token_usage.get("total", 0) for t in artifact.transcript)
        metadata = self._build_metadata(artifact, participants, total_tokens)

        return PrintDocument(sections=sections, metadata=metadata, toc=toc)

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
    def build_transactional_sections(artifact: DebateArtifact) -> list[dict]:
        """Build clause-sections from a transactional-drafting artifact.

        Extracts builder turns from the transcript and groups them into
        clause-level sections with provenance metadata from Turn.metadata.

        Returns a list of dicts with keys: title, content, provenance.
        """
        sections: list[dict] = []
        for turn in artifact.transcript:
            if turn.role_type != "builder":
                continue
            prov = (turn.metadata or {}).get("provenance", {})
            # Derive title from critic_item_id or turn content
            cid = prov.get("critic_item_id", "")
            title = f"Klausel {cid}" if cid else turn.agent_name

            # Content: extract the recommended builder option from the turn
            # The turn content already has the formatted markdown
            content = turn.content

            sections.append(
                {
                    "title": title,
                    "content": content,
                    "provenance": {
                        "draft_version": prov.get("draft_version"),
                        "critic_item_id": prov.get("critic_item_id"),
                        "original_text": prov.get("original_text", ""),
                        "revision_type": prov.get("revision_type"),
                        "pragmatist_verdict": prov.get("pragmatist_verdict"),
                        "pragmatist_score": prov.get("pragmatist_score"),
                    },
                }
            )
        return sections

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
    def _escape(text: str) -> str:
        """Escape HTML special characters."""
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    @staticmethod
    def _build_metadata_block(artifact: DebateArtifact) -> str:
        """Build HTML for the metadata section."""
        parts: list[str] = []

        rounds = max((t.round for t in artifact.transcript), default=0)
        parts.append(f'<div class="meta-row"><span class="meta-label">Anzahl Runden:</span> <span class="meta-value">{rounds}</span></div>')

        roles = sorted({t.role_type for t in artifact.transcript if t.role_type})
        if roles:
            parts.append(
                f'<div class="meta-row"><span class="meta-label">Agenten-Rollen:</span> <span class="meta-value">{" · ".join(roles)}</span></div>'
            )

        mapping: dict[str, str] = {}
        for t in artifact.transcript:
            if t.role_type and t.llm_profile_id and t.role_type not in mapping:
                mapping[t.role_type] = t.llm_profile_id
        if mapping:
            mapping_lines = " · ".join(f"{role} → {pid}" for role, pid in mapping.items())
            parts.append(f'<div class="meta-row"><span class="meta-label">LLM-Mapping:</span> <span class="meta-value">{mapping_lines}</span></div>')

        participants = sorted({t.agent_name for t in artifact.transcript if t.agent_name})
        if participants:
            parts.append(
                f'<div class="meta-row"><span class="meta-label">Teilnehmer:</span> <span class="meta-value">{" · ".join(participants)}</span></div>'
            )

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
        if duration:
            parts.append(f'<div class="meta-row"><span class="meta-label">Dauer:</span> <span class="meta-value">{duration}</span></div>')

        total_tokens = sum(t.token_usage.get("total", 0) for t in artifact.transcript)
        parts.append(f'<div class="meta-row"><span class="meta-label">Tokens gesamt:</span> <span class="meta-value">{total_tokens:,}</span></div>')

        return '<div class="metadata-grid">' + "".join(parts) + "</div>"

    @staticmethod
    def _build_executive_summary(artifact: DebateArtifact) -> str:
        """Build HTML for the Executive Summary (page 1).

        Shows final assessment, usability score, and remaining blockers
        from the moderator's output.
        """
        parts: list[str] = []
        if artifact.final_assessment:
            parts.append(f'<div class="exec-assessment">{artifact.final_assessment}</div>')
        if artifact.usability_score is not None:
            pct = round(artifact.usability_score * 100, 1)
            color = "green" if pct >= 80 else "orange" if pct >= 50 else "red"
            parts.append(f'<div class="exec-score"><strong>Usability Score:</strong> <span class="score-{color}">{pct}%</span></div>')
        if artifact.remaining_blockers:
            blockers = "".join(f"<li>{b}</li>" for b in artifact.remaining_blockers)
            parts.append(f'<div class="exec-blockers"><strong>Verbleibende Blockierer:</strong><ul>{blockers}</ul></div>')
        return "".join(parts)

    @staticmethod
    def _format_consensus(consensus: dict) -> str:
        """Format consensus_result dict into readable text."""
        parts: list[str] = []
        if "score" in consensus:
            parts.append(f"Konsens-Score: {consensus['score']}")
        if "summary" in consensus:
            summary = consensus["summary"]
            # Defensive: don't dump the entire truncated draft as summary.
            # If it's longer than 2000 chars it's likely the full current_draft.
            if len(summary) > 2000:
                summary = summary[:1000] + "\n\n[…]\n\n" + summary[-500:]
            parts.append(summary)
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
            llm_display = turn.llm_profile_name or turn.llm_profile_id or "—"
            rows.append(f"{turn.agent_name} | {turn.role_type} | {llm_display} | {turn.latency_ms}ms | {tokens} tokens")
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

        agent_roles = sorted({t.role_type for t in artifact.transcript if t.role_type})
        llm_mapping: dict[str, str] = {}
        for t in artifact.transcript:
            if t.role_type and t.llm_profile_id and t.role_type not in llm_mapping:
                llm_mapping[t.role_type] = t.llm_profile_id

        return PrintMetadata(
            topic=artifact.topic,
            workflow_name=artifact.workflow_name,
            title=artifact.title,
            participants=sorted(participants),
            duration=duration,
            total_tokens=total_tokens,
            total_rounds=max((t.round for t in artifact.transcript), default=0),
            agent_roles=agent_roles,
            llm_mapping=llm_mapping,
        )
