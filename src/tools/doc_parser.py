import re
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)
MAX_CONTEXT_CHARS = 25000  # Schutz vor Context-Overflow

class DocumentParser:
    async def parse_file(self, file_path: str) -> Dict[str, Any]:
        return await asyncio.to_thread(self._parse_sync, file_path)

    def _parse_sync(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {file_path}")

        ext = path.suffix.lower()
        text = ""
        metadata = {"source": path.name, "extension": ext, "pages": 0}

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
            logger.warning(f"Parsing fehlgeschlagen für {path.name}: {e}. Fallback zu Plain-Text.")
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e2:
                logger.error(f"Vollständiger Parse-Fehler für {path.name}: {e2}")
                raise

        # Bereinigung & Schutz vor Context-Overflow
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text).strip()
        
        if len(text) > MAX_CONTEXT_CHARS:
            text = text[:MAX_CONTEXT_CHARS] + "\n\n⚠️ [Dokument gekürzt. Kontextlänge überschritten.]"
            metadata["truncated"] = True

        metadata["word_count"] = len(text.split())
        metadata["char_count"] = len(text)
        return {"text": text, "metadata": metadata}