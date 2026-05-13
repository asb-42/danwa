"""Document processor — file parsing with optional PaddleOCR for images."""

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any

from backend.services.doc_parser import DocumentParser

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class DocumentProcessor:
    """Processes documents: file parsing with optional PaddleOCR for images."""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._ocr = None
        self._parser = DocumentParser()
        # Initialize OCR first — version check's `import paddle` can
        # conflict with paddlex's assertion that paddle not be pre-loaded.
        if self.config.get("ocr_enabled", False):
            self._initialize_ocr_sync()
        self._check_version_compatibility()

    async def process_file(self, file_path: str) -> dict[str, Any]:
        """Process a file and extract text. Uses OCR for images.

        Raises:
            ValueError: If the file is an image and OCR is not available.
        """
        logger.info("Processing file: %s, config: %s", file_path, self.config)
        ext = Path(file_path).suffix.lower()
        if ext in IMAGE_EXTENSIONS:
            logger.info("File is image extension: %s", ext)
            if not self.config.get("ocr_enabled", False):
                logger.error("OCR disabled in config: %s", self.config)
                raise ValueError(
                    f"Image file '{Path(file_path).name}' requires OCR but "
                    "ocr_enabled is false. Enable OCR in config/settings.yaml "
                    "under dms.ocr_enabled: true"
                )
            logger.info("Calling _process_with_paddle for image")
            return await self._process_with_paddle(file_path)
        logger.info("Processing as text file")
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

        Falls back to text extraction if OCR is unavailable.
        """
        ocr = await asyncio.to_thread(self._get_ocr)
        if ocr is None or not hasattr(ocr, "predict"):
            logger.warning(
                "OCR engine unavailable for %s (ocr: %s, has_predict: %s). "
                "Falling back to text extraction. Check OCR configuration and dependencies.",
                file_path,
                ocr,
                hasattr(ocr, "predict") if ocr else False,
            )
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
            logger.info("Initializing PaddleOCR synchronously in main thread")
            try:
                logger.info("Importing paddleocr module")
                paddle_module = importlib.import_module("paddleocr")
                paddle_ocr = getattr(paddle_module, "PaddleOCR")
                logger.info("PaddleOCR class found, initializing with device: %s", self.config.get("ocr_device", "cpu"))

                self._ocr = paddle_ocr(
                    use_angle_cls=True,
                    lang="en",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    device=self.config.get("ocr_device", "cpu"),
                    ocr_version="PP-OCRv4",
                )
                logger.info("PaddleOCR initialized successfully")
            except ImportError as e:
                logger.error("Failed to import PaddleOCR: %s", e)
                self._ocr = False
            except (RuntimeError, AssertionError) as e:
                logger.warning("PaddleOCR init error (type=%s): %s", type(e).__name__, e)
                if "PDX has already been initialized" in str(e) or "paddle is unexpectedly loaded" in str(e):
                    logger.warning("PaddleX/paddlex conflict - attempting to reuse existing instance")
                    try:
                        paddle_module = importlib.import_module("paddleocr")
                        paddle_ocr = getattr(paddle_module, "PaddleOCR")
                        self._ocr = paddle_ocr(
                            use_angle_cls=True,
                            lang="en",
                            use_doc_orientation_classify=False,
                            use_doc_unwarping=False,
                            device=self.config.get("ocr_device", "cpu"),
                            ocr_version="PP-OCRv4",
                        )
                        logger.info("PaddleOCR reinitialized successfully after PDX conflict")
                    except (RuntimeError, AssertionError):
                        logger.error("Cannot create PaddleOCR instance due to PaddleX initialization conflict")
                        self._ocr = False
                else:
                    logger.error("PaddleOCR initialization failed: %s", e)
                    self._ocr = False
            except Exception as e:
                logger.error("Unexpected error initializing PaddleOCR: %s", e)
                self._ocr = False

    def _get_ocr(self):
        """Get the OCR instance, initializing if needed (fallback for async contexts)."""
        if self._ocr is None:
            logger.warning("OCR not initialized synchronously, falling back to async initialization")
            self._initialize_ocr_sync()
        return self._ocr if self._ocr is not False else None

    def _extract_ocr_text(self, results: Any) -> str:
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

    def _check_version_compatibility(self):
        """Check for known PaddlePaddle version compatibility issues."""
        try:
            import paddle

            # Use getattr to avoid lint issues with __version__
            version_str = getattr(paddle, "__version__", "0.0.0")
            parts = version_str.split(".")
            major = parts[0]
            minor = parts[1] if len(parts) > 1 else "0"

            if major == "3" and int(minor) >= 3:
                logger.warning(
                    "PaddlePaddle 3.3+ has known PIR compatibility issues with OneDNN "
                    "that cause OCR crashes. Consider downgrading to PaddlePaddle 3.2.x "
                    "for stable OCR operations. See ADR-2024-05-12 for details."
                )
        except ImportError:
            # PaddlePaddle not installed - no compatibility check needed
            pass
        except AssertionError:
            # PaddleX/paddlex assertion about paddle being loaded - skip check
            logger.debug("Skipping version compatibility check due to paddlex import conflict")
        except Exception as e:
            logger.warning("Failed to check PaddlePaddle version compatibility: %s", e)
