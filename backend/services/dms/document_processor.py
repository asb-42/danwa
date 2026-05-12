"""Document processor — file parsing with optional PaddleOCR for images.

Migrated from src/dms/document_processor.py.
"""

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any

from backend.services.doc_parser import DocumentParser

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class DocumentProcessor:
    """Processes documents: text extraction for text files, PaddleOCR for images."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._ocr = None
        self._parser = DocumentParser()

    async def process_file(self, file_path: str) -> dict[str, Any]:
        """Process a file and extract text. Uses OCR for images.

        Raises:
            ValueError: If the file is an image and OCR is not available.
        """
        ext = Path(file_path).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            if not self.config.get("ocr_enabled", False):
                raise ValueError(
                    f"Image file '{Path(file_path).name}' requires OCR but "
                    "ocr_enabled is false. Enable OCR in config/settings.yaml "
                    "under dms.ocr_enabled: true"
                )
            return await self._process_with_paddle(file_path)
        return await self._process_with_existing(file_path)

    async def _process_with_existing(self, file_path: str) -> dict[str, Any]:
        result = await self._parser.parse_file(file_path)
        text = result.get("text", "")
        metadata = self._build_metadata(
            file_path,
            text,
            result.get("metadata"),
            ocr_used=False,
        )
        return {"text": text, "metadata": metadata, "ocr_used": False}

    async def _process_with_paddle(self, file_path: str) -> dict[str, Any]:
        """Process an image file with PaddleOCR.

        Raises:
            ValueError: If PaddleOCR is not installed or cannot be initialized.
        """
        ocr = await asyncio.to_thread(self._get_ocr)
        if ocr is None or not hasattr(ocr, "predict"):
            raise ValueError(
                f"Cannot process image '{Path(file_path).name}': "
                "PaddleOCR is not installed. Install with: pip install paddlepaddle paddleocr"
            )

        try:
            predict = getattr(ocr, "predict")
            results = await asyncio.to_thread(predict, file_path)
            text = self._extract_ocr_text(results)
            metadata = self._build_metadata(file_path, text, ocr_used=True)
            return {"text": text, "metadata": metadata, "ocr_used": True}
        except Exception as exc:
            logger.warning("PaddleOCR failed for %s: %s", file_path, exc)
            return await self._process_with_existing(file_path)

    def _get_ocr(self):
        if self._ocr is None:
            try:
                paddle_module = importlib.import_module("paddleocr")
                paddle_ocr = getattr(paddle_module, "PaddleOCR")

                self._ocr = paddle_ocr(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    device=self.config.get("ocr_device", "cpu"),
                )
            except ImportError:
                self._ocr = False
        return self._ocr if self._ocr is not False else None

    def _extract_ocr_text(self, results: Any) -> str:
        blocks = []
        for result in results or []:
            json_payload = getattr(result, "json", None) or {}
            for block in json_payload.get("ocr_results", []):
                text = (block or {}).get("text", "")
                if text:
                    blocks.append(text)
        return "\n".join(blocks).strip()

    def _build_metadata(
        self,
        file_path: str,
        text: str,
        metadata: dict | None = None,
        ocr_used: bool = False,
    ) -> dict[str, Any]:
        path = Path(file_path)
        merged = dict(metadata or {})
        merged["source"] = path.name
        merged["extension"] = path.suffix.lower()
        merged["pages"] = int(merged.get("pages", 0) or 0)
        merged["word_count"] = len(text.split())
        merged["char_count"] = len(text)
        merged["ocr_used"] = ocr_used
        return merged
