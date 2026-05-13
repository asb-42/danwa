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
        # Initialize OCR first — version check's `import paddle` can
        # conflict with paddlex's assertion that paddle not be pre-loaded.
        if self.config.get("ocr_enabled", False):
            self._initialize_ocr_sync()

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

    def _initialize_ocr_sync(self):
        """Initialize PaddleOCR synchronously in main thread to avoid threading issues."""
        if self._ocr is None:
            try:
                paddle_module = importlib.import_module("paddleocr")
                paddle_ocr = getattr(paddle_module, "PaddleOCR")
                self._ocr = paddle_ocr(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    device=self.config.get("ocr_device", "cpu"),
                    ocr_version="PP-OCRv4",
                )
            except ImportError:
                self._ocr = False
            except RuntimeError as e:
                if "PDX has already been initialized" in str(e) or "paddle is unexpectedly loaded" in str(e):
                    try:
                        paddle_module = importlib.import_module("paddleocr")
                        paddle_ocr = getattr(paddle_module, "PaddleOCR")
                        self._ocr = paddle_ocr(
                            use_doc_orientation_classify=False,
                            use_doc_unwarping=False,
                            device=self.config.get("ocr_device", "cpu"),
                            ocr_version="PP-OCRv4",
                        )
                    except (RuntimeError, AssertionError):
                        logger.error("Cannot create PaddleOCR instance due to PaddleX initialization conflict")
                        self._ocr = False
                else:
                    logger.error("PaddleOCR initialization failed: %s", e)
                    self._ocr = False
            except AssertionError:
                logger.warning("PaddleOCR init AssertionError — possible paddlex conflict, OCR may not be available")
            except Exception as e:
                logger.error("Unexpected error initializing PaddleOCR: %s", e)
                self._ocr = False

    def _get_ocr(self):
        """Get the OCR instance, initializing if needed (fallback for async contexts)."""
        if self._ocr is None:
            self._initialize_ocr_sync()
        return self._ocr if self._ocr is not False else None

    def _extract_ocr_text(self, results) -> str:
        blocks = []
        for result in results or []:
            if isinstance(result, dict):
                # PaddleOCR 3.5.0+ format: dict with 'rec_texts' (list of strings)
                rec_texts = result.get("rec_texts")
                if isinstance(rec_texts, list):
                    blocks.extend(t for t in rec_texts if t)
                    continue
                # Old dict format: 'ocr_results' containing {'text': ...} blocks
                for block in result.get("ocr_results", []):
                    if isinstance(block, dict):
                        text = block.get("text", "")
                        if text:
                            blocks.append(text)
            elif hasattr(result, "json"):
                json_attr = result.json
                # json may be a callable method or already a dict
                if callable(json_attr):
                    json_payload = json_attr()
                else:
                    json_payload = json_attr
                if isinstance(json_payload, dict):
                    for block in json_payload.get("ocr_results", []):
                        if isinstance(block, dict):
                            text = block.get("text", "")
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
