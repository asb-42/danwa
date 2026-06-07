"""PrintOutputPlugin — renders DebateArtifact as PDF / DOCX via Jinja2 + WeasyPrint."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

import jinja2
from pydantic import BaseModel, Field

from backend.models.artifact import DebateArtifact
from backend.services.output.base import OutputPlugin, ProgressCallback, _noop_progress
from backend.services.output.plugins.print_layout_engine import PrintLayoutEngine
from backend.services.output.plugins.print_models import PrintDocument
from backend.services.output.registry import register_plugin
from backend.workflow.workflow_state import WorkflowTemplate

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "templates" / "print"


# ---------------------------------------------------------------------------
# Config Schema
# ---------------------------------------------------------------------------


class PrintTemplate(StrEnum):
    """PrintTemplate class."""

    ACADEMIC_DEBATE = "academic_debate"
    MINIMAL = "minimal"
    TRANSACTIONAL_DRAFTING = "transactional_drafting"


class PrintFormat(StrEnum):
    """PrintFormat class."""

    PDF = "pdf"
    DOCX = "docx"
    ODT = "odt"
    MD = "md"
    ALL = "all"


class PageSize(StrEnum):
    """PageSize class."""

    A4 = "a4"
    LETTER = "letter"


class PrintPluginConfig(BaseModel):
    """Configuration schema for the Print output plugin."""

    template_name: PrintTemplate = PrintTemplate.ACADEMIC_DEBATE
    include_audit_trail: bool = True
    include_minority_votes: bool = True
    include_toc: bool = Field(default=True, description="Include Table of Contents")
    primary_format: PrintFormat = PrintFormat.PDF
    page_size: PageSize = PageSize.A4
    language: str = Field(default="de", description="Locale: 'de' or 'en'")


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


@register_plugin
class PrintOutputPlugin(OutputPlugin):
    """Renders a DebateArtifact as PDF, DOCX, or ODT (LibreOffice Writer).

    Uses Jinja2 templates to produce HTML, then converts via
    WeasyPrint (PDF) or pypandoc (DOCX/ODT).
    """

    plugin_key: ClassVar[str] = "print"
    plugin_name: ClassVar[str] = "Print / PDF / DOCX / ODT / MD"
    supported_formats: ClassVar[list[str]] = ["pdf", "docx", "odt", "md"]
    config_schema: ClassVar[type[BaseModel]] = PrintPluginConfig

    async def render(
        self,
        artifact: DebateArtifact,
        config: BaseModel,
        job_id: str,
        output_dir: Path,
        *,
        progress_callback: ProgressCallback = _noop_progress,
    ) -> list[Path]:
        """Render artifact to PDF, DOCX, ODT, and/or Markdown.

        Args:
            artifact: The debate artifact.
            config: Validated ``PrintPluginConfig``.
            job_id: Render job ID.
            output_dir: Root output directory.
            progress_callback: Async callback ``(current, total)`` for
                tracking render progress.

        Returns:
            List of generated file paths.
        """
        assert isinstance(config, PrintPluginConfig)
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # Auto-detect transactional drafting from artifact metadata
        wf_template = (artifact.metadata or {}).get("workflow_template", "")
        is_td = wf_template == WorkflowTemplate.TRANSACTIONAL_DRAFTING
        if is_td and config.template_name == PrintTemplate.ACADEMIC_DEBATE:
            config.template_name = PrintTemplate.TRANSACTIONAL_DRAFTING

        # 1. Transform artifact → PrintDocument
        engine = PrintLayoutEngine()
        doc = engine.transform(
            artifact,
            include_audit_trail=config.include_audit_trail,
            include_minority_votes=config.include_minority_votes,
            include_toc=config.include_toc,
        )

        # 2. Build sections for transactional drafting
        sections = []
        if config.template_name == PrintTemplate.TRANSACTIONAL_DRAFTING:
            sections = engine.build_transactional_sections(artifact)

        # 3. Load i18n
        i18n = self._load_i18n(config.language)

        # 4. Render HTML via Jinja2 (needed for PDF, DOCX, ODT)
        template_name = f"{config.template_name.value}.html"
        html = await asyncio.to_thread(
            self._render_html,
            template_name,
            doc.model_dump(),
            i18n,
            config,
            artifact=artifact,
            sections=sections,
        )

        # 4. Generate output files based on primary_format
        output_files: list[Path] = []
        fmt = config.primary_format
        logger.debug(
            "PrintOutputPlugin rendering format=%s (type=%s) for job %s",
            fmt.value,
            type(fmt).__name__,
            job_id,
        )

        if fmt in (PrintFormat.PDF, PrintFormat.ALL):
            pdf_path = job_dir / "debate.pdf"
            await asyncio.to_thread(self._generate_pdf, html, pdf_path)
            output_files.append(pdf_path)

        if fmt in (PrintFormat.DOCX, PrintFormat.ALL):
            docx_path = job_dir / "debate.docx"
            await asyncio.to_thread(self._generate_docx, html, docx_path)
            output_files.append(docx_path)

        if fmt in (PrintFormat.ODT, PrintFormat.ALL):
            odt_path = job_dir / "debate.odt"
            await asyncio.to_thread(self._generate_odt, html, odt_path)
            output_files.append(odt_path)

        if fmt in (PrintFormat.MD, PrintFormat.ALL):
            md_path = job_dir / "debate.md"
            md_content = await asyncio.to_thread(self._generate_md, doc, i18n, config)
            md_path.write_text(md_content, encoding="utf-8")
            output_files.append(md_path)

        logger.info(
            "PrintOutputPlugin rendered %d file(s) for job %s: %s",
            len(output_files),
            job_id,
            [str(p.name) for p in output_files],
        )
        return output_files

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_i18n(language: str) -> dict:
        """Load i18n labels from templates/print/i18n/{language}.json."""
        i18n_file = _TEMPLATES_DIR / "i18n" / f"{language}.json"
        if not i18n_file.exists():
            i18n_file = _TEMPLATES_DIR / "i18n" / "de.json"
        if i18n_file.exists():
            return json.loads(i18n_file.read_text(encoding="utf-8"))
        return {}

    @staticmethod
    def _render_html(
        template_name: str,
        doc_data: dict,
        i18n: dict,
        config: PrintPluginConfig,
        **extra: dict,
    ) -> str:
        """Render Jinja2 template to HTML string.

        Keyword arguments in *extra* (e.g. *artifact*, *sections*) are
        forwarded to the template context for templates that need
        direct access to the DebateArtifact.
        """

        def _format_number(value):
            """Format a number with thousands separator."""
            try:
                return f"{int(value):,}"
            except (ValueError, TypeError):
                return str(value)

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        env.filters["format_number"] = _format_number
        template = env.get_template(template_name)
        return template.render(
            doc=doc_data,
            i18n=i18n,
            config=config.model_dump(),
            **extra,
        )

    @staticmethod
    def _generate_pdf(html: str, output_path: Path) -> None:
        """Generate PDF from HTML via WeasyPrint."""
        from weasyprint import HTML

        HTML(string=html).write_pdf(str(output_path))
        logger.info("PDF generated: %s", output_path)

    @staticmethod
    def _generate_docx(html: str, output_path: Path) -> None:
        """Generate DOCX from HTML.

        Tries pypandoc first, falls back to python-docx.
        """
        try:
            import pypandoc

            pypandoc.convert_text(html, "docx", format="html", outputfile=str(output_path))
            logger.info("DOCX generated via pypandoc: %s", output_path)
        except ImportError:
            logger.warning("pypandoc not available, falling back to python-docx")
            PrintOutputPlugin._generate_docx_fallback(html, output_path)

    @staticmethod
    def _generate_docx_fallback(html: str, output_path: Path) -> None:
        """Fallback DOCX generation using python-docx."""
        from docx import Document
        from docx.shared import Pt

        doc = Document()
        doc.styles["Normal"].font.name = "Calibri"
        doc.styles["Normal"].font.size = Pt(11)

        # Simple HTML → DOCX: strip tags and add as paragraphs
        import re

        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()

        for paragraph in text.split("\n"):
            paragraph = paragraph.strip()
            if paragraph:
                doc.add_paragraph(paragraph)

        doc.save(str(output_path))
        logger.info("DOCX generated via python-docx fallback: %s", output_path)

    @staticmethod
    def _generate_odt(html: str, output_path: Path) -> None:
        """Generate ODT (LibreOffice Writer) from HTML.

        Tries pypandoc first, falls back to odfpy.
        """
        try:
            import pypandoc

            pypandoc.convert_text(html, "odt", format="html", outputfile=str(output_path))
            logger.info("ODT generated via pypandoc: %s", output_path)
        except ImportError:
            logger.warning("pypandoc not available, falling back to odfpy")
            PrintOutputPlugin._generate_odt_fallback(html, output_path)

    @staticmethod
    def _generate_odt_fallback(html: str, output_path: Path) -> None:
        """Fallback ODT generation using odfpy."""
        try:
            import re

            from odf.opendocument import OpenDocumentText
            from odf.text import P

            doc = OpenDocumentText()
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text).strip()
            for paragraph in text.split("\n"):
                paragraph = paragraph.strip()
                if paragraph:
                    doc.text.addElement(P(text=paragraph))
            doc.save(str(output_path))
            logger.info("ODT generated via odfpy fallback: %s", output_path)
        except ImportError:
            logger.warning("odfpy not available, writing HTML as .odt")
            output_path.write_text(html, encoding="utf-8")

    @staticmethod
    def _generate_md(
        doc: PrintDocument,
        i18n: dict,
        config: PrintPluginConfig,
    ) -> str:
        """Generate Markdown from a PrintDocument.

        Renders the structured document as clean Markdown using html2text
        for proper HTML→MD conversion (headings, lists, emphasis, links,
        code blocks, tables).
        """
        from backend.services.output.html_to_md import html_to_markdown

        assert isinstance(doc, PrintDocument)
        lines: list[str] = []

        # Sections (process semantic sections for special positioning)
        title_section = next((s for s in doc.sections if s.type.value == "title"), None)
        metadata_section = next((s for s in doc.sections if s.type.value == "metadata"), None)
        case_section = next((s for s in doc.sections if s.type.value == "case_description"), None)

        # Title
        if title_section:
            plain_title = html_to_markdown(title_section.content).strip().lstrip("#").strip()
            lines.append(f"# {plain_title}")
        else:
            lines.append(f"# {doc.metadata.topic}")
        lines.append("")

        # Metadata
        if metadata_section:
            meta_md = html_to_markdown(metadata_section.content)
            for meta_line in meta_md.split("\n"):
                meta_line = meta_line.strip()
                if meta_line:
                    lines.append(meta_line)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Case description
        if case_section:
            case_md = html_to_markdown(case_section.content).strip()
            lines.append(case_md)
            lines.append("")
            lines.append("---")
            lines.append("")

        # Table of Contents
        if doc.toc:
            lines.append(f"## {i18n.get('toc_label', 'Table of Contents')}")
            lines.append("")
            for entry in doc.toc:
                indent = "  " * (entry.level - 1)
                lines.append(f"{indent}- {entry.title}")
            lines.append("")
            lines.append("---")
            lines.append("")

        # Sections (skip semantic types already rendered above)
        skip_types = {"title", "metadata", "case_description", "table_of_contents"}
        for section in doc.sections:
            if section.type.value in skip_types:
                continue

            # Convert HTML content to proper Markdown
            content_md = html_to_markdown(section.content)
            content_md = re.sub(r"\n{3,}", "\n\n", content_md).strip()

            if section.type.value == "turn":
                round_str = f" ({i18n.get('round_label', 'Round')} {section.round})" if section.round is not None else ""
                lines.append(f"## {section.agent_name} — {i18n.get('turn_label', 'Turn')}{round_str}")
                lines.append("")
                if section.timestamp:
                    lines.append(f"*{i18n.get('timestamp_label', 'Timestamp')}: {section.timestamp}*")
                    lines.append("")
                lines.append(content_md)
                lines.append("")

                # Margin notes
                for note in section.margin_notes:
                    note_md = html_to_markdown(note.content).strip()
                    icon = "⚡" if note.type.value == "injection" else "ℹ"
                    lines.append(f"> {icon} {note_md}")
                    lines.append("")

            elif section.type.value == "minority_callout":
                lines.append(f"### ⚠ {i18n.get('minority_vote_label', 'Minority Vote')}: {section.agent_name}")
                lines.append("")
                lines.append(content_md)
                lines.append("")

            elif section.type.value == "user_query_block":
                lines.append(f"### ❓ {i18n.get('user_query_label', 'User Question')}")
                lines.append("")
                lines.append(content_md)
                lines.append("")

            elif section.type.value == "consensus_summary":
                lines.append(f"## {i18n.get('consensus_label', 'Consensus')}")
                lines.append("")
                lines.append(content_md)
                lines.append("")

            elif section.type.value == "audit_appendix":
                lines.append(f"## {i18n.get('audit_trail_label', 'Audit Trail')}")
                lines.append("")
                # Parse the pipe-delimited content into a Markdown table
                audit_lines = section.content.strip().split("\n")
                for i, aline in enumerate(audit_lines):
                    parts = [p.strip() for p in aline.split(" | ")]
                    if i == 0:
                        lines.append("| " + " | ".join(parts) + " |")
                        lines.append("| " + " | ".join(["---"] * len(parts)) + " |")
                    else:
                        lines.append("| " + " | ".join(parts) + " |")
                lines.append("")

        # Footer
        lines.append("---")
        lines.append(f"*{i18n.get('generated_label', 'Generated')}: {doc.metadata.topic}*")

        return "\n".join(lines) + "\n"
