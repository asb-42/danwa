"""PrintOutputPlugin — renders DebateArtifact as PDF / DOCX via Jinja2 + WeasyPrint."""

from __future__ import annotations

import asyncio
import json
import logging
from enum import StrEnum
from pathlib import Path
from typing import ClassVar

import jinja2
from pydantic import BaseModel, Field

from backend.models.artifact import DebateArtifact
from backend.services.output.base import OutputPlugin
from backend.services.output.plugins.print_layout_engine import PrintLayoutEngine
from backend.services.output.registry import register_plugin

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "print"


# ---------------------------------------------------------------------------
# Config Schema
# ---------------------------------------------------------------------------


class PrintTemplate(StrEnum):
    ACADEMIC_DEBATE = "academic_debate"
    MINIMAL = "minimal"


class PrintFormat(StrEnum):
    PDF = "pdf"
    DOCX = "docx"
    ODT = "odt"
    ALL = "all"


class PageSize(StrEnum):
    A4 = "a4"
    LETTER = "letter"


class PrintPluginConfig(BaseModel):
    """Configuration schema for the Print output plugin."""

    template_name: PrintTemplate = PrintTemplate.ACADEMIC_DEBATE
    include_audit_trail: bool = True
    include_minority_votes: bool = True
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
    plugin_name: ClassVar[str] = "Print / PDF / DOCX / ODT"
    supported_formats: ClassVar[list[str]] = ["pdf", "docx", "odt"]
    config_schema: ClassVar[type[BaseModel]] = PrintPluginConfig

    async def render(
        self,
        artifact: DebateArtifact,
        config: BaseModel,
        job_id: str,
        output_dir: Path,
    ) -> list[Path]:
        """Render artifact to PDF and/or DOCX.

        Args:
            artifact: The debate artifact.
            config: Validated ``PrintPluginConfig``.
            job_id: Render job ID.
            output_dir: Root output directory.

        Returns:
            List of generated file paths.
        """
        assert isinstance(config, PrintPluginConfig)
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        # 1. Transform artifact → PrintDocument
        engine = PrintLayoutEngine()
        doc = engine.transform(
            artifact,
            include_audit_trail=config.include_audit_trail,
            include_minority_votes=config.include_minority_votes,
        )

        # 2. Load i18n
        i18n = self._load_i18n(config.language)

        # 3. Render HTML via Jinja2
        template_name = f"{config.template_name.value}.html"
        html = await asyncio.to_thread(
            self._render_html, template_name, doc.model_dump(), i18n, config
        )

        # 4. Generate output files
        output_files: list[Path] = []
        fmt = config.primary_format

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

        logger.info(
            "PrintOutputPlugin rendered %d file(s) for job %s",
            len(output_files),
            job_id,
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
    ) -> str:
        """Render Jinja2 template to HTML string."""
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=True,
        )
        template = env.get_template(template_name)
        return template.render(
            doc=doc_data,
            i18n=i18n,
            config=config.model_dump(),
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

            pypandoc.convert_text(
                html, "odt", format="html", outputfile=str(output_path)
            )
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
            from odf.text import H, P

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
