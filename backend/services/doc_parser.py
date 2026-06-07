"""Document parser — extracts text from PDF, DOCX, ODT, and plain text files.

Migrated from src/tools/doc_parser.py.
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
MAX_CONTEXT_CHARS = 25000  # Protection against context overflow


class DocumentParser:
    """Parse documents and extract text content."""

    async def parse_file(self, file_path: str) -> dict[str, Any]:
        """Parse file."""
        return await asyncio.to_thread(self._parse_sync, file_path)

    def _parse_sync(self, file_path: str) -> dict[str, Any]:
        """Parse sync the instance."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = path.suffix.lower()
        text = ""
        metadata: dict[str, Any] = {"source": path.name, "extension": ext, "pages": 0}

        try:
            if ext == ".pdf":
                try:
                    import pdfplumber

                    with pdfplumber.open(str(path)) as pdf:
                        metadata["pages"] = len(pdf.pages)
                        text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
                except ImportError:
                    import pypdf

                    reader = pypdf.PdfReader(str(path))
                    metadata["pages"] = len(reader.pages)
                    text = "\n\n".join(page.extract_text() or "" for page in reader.pages)

            elif ext in [".odt", ".ods", ".odp"]:
                from odf import teletype
                from odf.opendocument import load

                doc = load(str(path))
                text = teletype.extractText(doc)

            elif ext == ".docx":
                from docx import Document

                doc = Document(str(path))
                text = "\n\n".join(p.text for p in doc.paragraphs)

            else:
                text = path.read_text(encoding="utf-8", errors="ignore")

        except Exception as e:
            logger.warning("Parsing failed for %s: %s. Falling back to plain text.", path.name, e)
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e2:
                logger.error("Complete parse failure for %s: %s", path.name, e2)
                raise

        # Cleanup & context overflow protection
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text).strip()

        if len(text) > MAX_CONTEXT_CHARS:
            text = text[:MAX_CONTEXT_CHARS] + "\n\n⚠️ [Document truncated. Context length exceeded.]"
            metadata["truncated"] = True

        metadata["word_count"] = len(text.split())
        metadata["char_count"] = len(text)
        return {"text": text, "metadata": metadata}
