import asyncio
import importlib
import logging
from pathlib import Path

from src.tools.doc_parser import DocumentParser

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class DocumentProcessor:
    def __init__(self, config: dict):
        self.config = config
        self._ocr = None
        self._parser = DocumentParser()

    async def process_file(self, file_path: str) -> dict:
        ext = Path(file_path).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            return await self._process_with_paddle(file_path)
        return await self._process_with_existing(file_path)

    async def _process_with_existing(self, file_path: str) -> dict:
        result = await self._parser.parse_file(file_path)
        text = result.get("text", "")
        metadata = self._build_metadata(
            file_path,
            text,
            result.get("metadata"),
            ocr_used=False,
        )
        return {"text": text, "metadata": metadata, "ocr_used": False}

    async def _process_with_paddle(self, file_path: str) -> dict:
        ocr = await asyncio.to_thread(self._get_ocr)
        if ocr is None or not hasattr(ocr, "predict"):
            return await self._process_with_existing(file_path)

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

    def _extract_ocr_text(self, results) -> str:
        blocks = []
        for result in results or []:
            json_payload = getattr(result, "json", None) or {}
            for block in json_payload.get("ocr_results", []):
                text = (block or {}).get("text", "")
                if text:
                    blocks.append(text)
        return "\n".join(blocks).strip()

    def _build_metadata(self, file_path: str, text: str, metadata: dict | None = None, ocr_used: bool = False) -> dict:
        path = Path(file_path)
        merged = dict(metadata or {})
        merged["source"] = path.name
        merged["extension"] = path.suffix.lower()
        merged["pages"] = int(merged.get("pages", 0) or 0)
        merged["word_count"] = len(text.split())
        merged["char_count"] = len(text)
        merged["ocr_used"] = ocr_used
        return merged
