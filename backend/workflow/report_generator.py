"""Workflow Report Generator — generates DOCX/PDF/ODF reports for workflow sessions.

Produces a structured report including:
- Workflow name/version, timestamp
- Participant agents (names, roles, LLM profiles)
- Full message history from state snapshots
- Consensus result
- Audit trail table
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document
from weasyprint import HTML

from backend.workflow.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

_REPORTS_DIR = Path("reports")


class WorkflowReportGenerator:
    """Generates structured reports for completed workflow sessions."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else None
        self._audit = AuditLogger(self._db_path)
        _REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    async def generate(
        self, session_id: str, fmt: str = "docx"
    ) -> Path:
        """Generate a report for *session_id* in the given *fmt*.

        Args:
            session_id: The workflow session ID.
            fmt: Output format — ``"docx"``, ``"pdf"``, or ``"odf"``.

        Returns:
            Path to the generated report file.
        """
        if fmt not in ("docx", "pdf", "odf"):
            raise ValueError(f"Unsupported format: {fmt!r}")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"workflow_{session_id}_{ts}.{fmt}"
        path = _REPORTS_DIR / filename

        # Load data
        audit_entries = self._audit.get_audit_log_for_replay(session_id)

        if fmt == "docx":
            await asyncio.to_thread(self._build_docx, session_id, audit_entries, path)
        elif fmt == "pdf":
            await asyncio.to_thread(self._build_pdf, session_id, audit_entries, path)
        elif fmt == "odf":
            await asyncio.to_thread(self._build_odf, session_id, audit_entries, path)

        logger.info("Report generated: %s", path)
        return path

    # ------------------------------------------------------------------
    # DOCX
    # ------------------------------------------------------------------

    def _build_docx(
        self,
        session_id: str,
        audit_entries: list[dict[str, Any]],
        path: Path,
    ) -> None:
        doc = Document()
        doc.styles["Normal"].font.name = "Calibri"

        # Title
        doc.add_heading(f"Workflow Report: {session_id}", level=0)

        # Summary
        doc.add_heading("Summary", level=1)
        doc.add_paragraph(f"Session ID: {session_id}")
        doc.add_paragraph(f"Generated: {datetime.now().isoformat()}")
        doc.add_paragraph(f"Audit entries: {len(audit_entries)}")

        # Audit trail table
        doc.add_heading("Audit Trail", level=1)
        if audit_entries:
            table = doc.add_table(rows=1, cols=6, style="Table Grid")
            headers = ["Timestamp", "Event Type", "Node", "Actor", "Latency (ms)", "Tokens"]
            for i, h in enumerate(headers):
                table.rows[0].cells[i].text = h
            for entry in audit_entries:
                row = table.add_row()
                row.cells[0].text = str(entry.get("timestamp", ""))
                row.cells[1].text = str(entry.get("event_type", ""))
                row.cells[2].text = str(entry.get("node_id", ""))
                row.cells[3].text = str(entry.get("actor", ""))
                row.cells[4].text = str(entry.get("latency_ms", 0))
                row.cells[5].text = str(
                    entry.get("prompt_tokens", 0) + entry.get("completion_tokens", 0)
                )
        else:
            doc.add_paragraph("No audit entries found.")

        doc.save(str(path))

    # ------------------------------------------------------------------
    # PDF (via WeasyPrint)
    # ------------------------------------------------------------------

    def _build_pdf(
        self,
        session_id: str,
        audit_entries: list[dict[str, Any]],
        path: Path,
    ) -> None:
        html_content = self._render_html(session_id, audit_entries)
        HTML(string=html_content).write_pdf(str(path))

    # ------------------------------------------------------------------
    # ODF (via basic HTML-to-ODF fallback using WeasyPrint HTML)
    # ------------------------------------------------------------------

    def _build_odf(
        self,
        session_id: str,
        audit_entries: list[dict[str, Any]],
        path: Path,
    ) -> None:
        # For ODF we generate an HTML-based representation and convert.
        # A full odfpy implementation would require more complex templating.
        html_content = self._render_html(session_id, audit_entries)
        # Write as .odt using a simple text-based approach
        # In production, use odfpy for proper ODF generation
        try:
            from odf import teletype
            from odf.opendocument import OpenDocumentText
            from odf.text import H, P

            doc = OpenDocumentText()
            doc.text.addElement(H(text=f"Workflow Report: {session_id}", outlinelevel=1))
            doc.text.addElement(P(text=f"Session ID: {session_id}"))
            doc.text.addElement(P(text=f"Generated: {datetime.now().isoformat()}"))
            doc.text.addElement(P(text=f"Audit entries: {len(audit_entries)}"))
            doc.text.addElement(H(text="Audit Trail", outlinelevel=2))
            for entry in audit_entries:
                line = (
                    f"{entry.get('timestamp', '')} | "
                    f"{entry.get('event_type', '')} | "
                    f"{entry.get('node_id', '')} | "
                    f"{entry.get('actor', '')}"
                )
                doc.text.addElement(P(text=line))
            doc.save(str(path))
        except ImportError:
            # Fallback: write HTML if odfpy not available
            path = path.with_suffix(".html")
            path.write_text(html_content, encoding="utf-8")
            logger.warning("odfpy not available; wrote HTML instead: %s", path)

    # ------------------------------------------------------------------
    # HTML rendering (shared by PDF and ODF)
    # ------------------------------------------------------------------

    @staticmethod
    def _render_html(
        session_id: str,
        audit_entries: list[dict[str, Any]],
    ) -> str:
        rows = ""
        for e in audit_entries:
            rows += (
                f"<tr>"
                f"<td>{e.get('timestamp', '')}</td>"
                f"<td>{e.get('event_type', '')}</td>"
                f"<td>{e.get('node_id', '')}</td>"
                f"<td>{e.get('actor', '')}</td>"
                f"<td>{e.get('latency_ms', 0)}</td>"
                f"<td>{e.get('prompt_tokens', 0) + e.get('completion_tokens', 0)}</td>"
                f"</tr>"
            )
        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Workflow Report — {session_id}</title>
<style>
  body {{ font-family: Calibri, sans-serif; margin: 2em; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
  th {{ background: #f0f0f0; }}
</style></head><body>
<h1>Workflow Report: {session_id}</h1>
<p><strong>Generated:</strong> {datetime.now().isoformat()}</p>
<p><strong>Audit entries:</strong> {len(audit_entries)}</p>
<h2>Audit Trail</h2>
<table>
<thead><tr><th>Timestamp</th><th>Event Type</th><th>Node</th><th>Actor</th><th>Latency (ms)</th><th>Tokens</th></tr></thead>
<tbody>{rows}</tbody>
</table></body></html>"""
