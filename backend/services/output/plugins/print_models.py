"""Print data structures — semantic layout models for the Print plugin.

These models represent the intermediate document structure between
``DebateArtifact`` and the final HTML/PDF/DOCX output.  The
``PrintLayoutEngine`` transforms an artifact into a ``PrintDocument``,
which is then rendered by Jinja2 templates.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class MarginNoteType(StrEnum):
    """Type of margin note in the print layout."""

    INJECTION = "injection"
    META = "meta"
    DISSENT = "dissent"
    PROVENANCE = "provenance"


class MarginNote(BaseModel):
    """A note displayed in the margin column."""

    type: MarginNoteType
    content: str
    reference_id: str


class SectionType(StrEnum):
    """Semantic type of a print section."""

    HEADER = "header"
    TITLE = "title"
    METADATA = "metadata"
    CASE_DESCRIPTION = "case_description"
    TABLE_OF_CONTENTS = "table_of_contents"
    TURN = "turn"
    INJECTION_SIDEBAR = "injection_sidebar"
    MINORITY_CALLOUT = "minority_callout"
    USER_QUERY_BLOCK = "user_query_block"
    CONSENSUS_SUMMARY = "consensus_summary"
    EXECUTIVE_SUMMARY = "executive_summary"
    AUDIT_APPENDIX = "audit_appendix"


class TOCEntry(BaseModel):
    """A single entry in the Table of Contents."""

    level: int = 1  # 1=round, 2=agent, 3=heading within content
    title: str = ""
    anchor: str = ""  # HTML id for linking


class PrintSection(BaseModel):
    """A single section in the print document layout."""

    id: str = ""  # HTML id attribute for TOC anchoring
    type: SectionType
    title: str = ""
    content: str = ""
    agent_name: str = ""
    timestamp: datetime | None = None
    round: int | None = None
    margin_notes: list[MarginNote] = Field(default_factory=list)
    css_class: str = ""


class PrintMetadata(BaseModel):
    """Metadata displayed in the document header."""

    topic: str
    workflow_name: str
    title: str = ""
    participants: list[str] = Field(default_factory=list)
    duration: str = ""
    total_tokens: int = 0
    total_rounds: int = 0
    agent_roles: list[str] = Field(default_factory=list)
    llm_mapping: dict[str, str] = Field(default_factory=dict)


class PrintDocument(BaseModel):
    """Semantic layout representation before HTML rendering.

    Produced by :class:`PrintLayoutEngine` and consumed by the
    Jinja2 template renderer.
    """

    sections: list[PrintSection] = Field(default_factory=list)
    metadata: PrintMetadata
    toc: list[TOCEntry] = Field(default_factory=list)
