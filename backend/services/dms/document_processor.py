"""Document processor — file parsing with optional OCR (PaddleOCR, EasyOCR, Tesseract)."""

import asyncio
import importlib
import logging
from pathlib import Path
from typing import Any

from backend.services.doc_parser import DocumentParser

logger = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


class DocumentProcessor:
    """Processes documents: file parsing with optional OCR for images.

    Supports multiple OCR engines with fallback chain:
    1. PaddleOCR (if available, recommended)
    2. EasyOCR (if available, fallback to PaddleOCR)
    3. Tesseract via pytesseract (if available, tertiary fallback)
    """

    def __init__(self, config: dict | None = None):
        """Initialise DocumentProcessor."""
        self.config = config or {}
        self._ocr = None
        self._ocr_engine = None  # "paddleocr", "easyocr", "tesseract", or None
        self._parser = DocumentParser()
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
            return await self._process_with_ocr(file_path)
        logger.info("Processing as text file")
        return await self._process_with_existing(file_path)

    async def _process_with_existing(self, file_path: str) -> dict[str, Any]:
        """Process with existing internally."""
        result = await self._parser.parse_file(file_path)
        text = result.get("text", "")
        metadata = self._build_metadata(
            file_path,
            text,
            result.get("metadata"),
            ocr_used=False,
        )
        return {"text": text, "metadata": metadata, "ocr_used": False}

    async def _process_with_ocr(self, file_path: str) -> dict[str, Any]:
        """Process an image file with available OCR engine.

        Falls back to text extraction if no OCR engine is available.
        """
        ocr = await asyncio.to_thread(self._get_ocr)
        if ocr is None:
            logger.warning(
                "No OCR engine available for %s. Falling back to text extraction.",
                file_path,
            )
            return await self._process_with_existing(file_path)

        try:
            if self._ocr_engine == "paddleocr":
                return await self._process_with_paddle(file_path, ocr)
            elif self._ocr_engine == "easyocr":
                return await self._process_with_easyocr(file_path, ocr)
            elif self._ocr_engine == "tesseract":
                return await self._process_with_tesseract(file_path, ocr)
            else:
                return await self._process_with_existing(file_path)
        except Exception as exc:
            logger.warning("OCR failed for %s: %s", file_path, exc)
            return await self._process_with_existing(file_path)

    async def _process_with_paddle(self, file_path: str, ocr) -> dict[str, Any]:
        """Process with PaddleOCR."""
        try:
            predict = getattr(ocr, "predict")
            results = await asyncio.to_thread(predict, file_path)
            text = self._extract_paddle_text(results)
            metadata = self._build_metadata(file_path, text, ocr_used=True)
            return {"text": text, "metadata": metadata, "ocr_used": True}
        except Exception as exc:
            logger.warning("PaddleOCR failed for %s: %s", file_path, exc)
            return await self._process_with_existing(file_path)

    async def _process_with_tesseract(self, file_path: str, ocr) -> dict[str, Any]:
        """Process with Tesseract via pytesseract."""
        import pytesseract
        from PIL import Image

        try:
            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang=self.config.get("ocr_lang", "deu+eng"))
            metadata = self._build_metadata(file_path, text, ocr_used=True)
            return {"text": text, "metadata": metadata, "ocr_used": True}
        except Exception as exc:
            logger.warning("Tesseract OCR failed for %s: %s", file_path, exc)
            return await self._process_with_existing(file_path)

    def _initialize_ocr_sync(self):
        """Initialize OCR engine synchronously.

        Fallback chain respects ``ocr_preferred_engine`` config:
        - ``"auto"`` (default): PaddleOCR → EasyOCR → Tesseract
        - specific engine: try it first, then fallback to the rest
        """
        preferred = self.config.get("ocr_preferred_engine", "auto")

        if preferred == "auto":
            engines = ["paddleocr", "easyocr", "tesseract"]
        elif preferred == "paddleocr":
            engines = ["paddleocr", "easyocr", "tesseract"]
        elif preferred == "easyocr":
            engines = ["easyocr", "paddleocr", "tesseract"]
        elif preferred == "tesseract":
            engines = ["tesseract", "paddleocr", "easyocr"]
        else:
            engines = ["paddleocr", "easyocr", "tesseract"]

        init_map = {
            "paddleocr": self._try_init_paddleocr,
            "easyocr": self._try_init_easyocr,
            "tesseract": self._try_init_tesseract,
        }

        for engine in engines:
            ocr = init_map[engine]()
            if ocr is not None:
                self._ocr = ocr
                self._ocr_engine = engine
                return

        self._ocr = None
        self._ocr_engine = None
        logger.warning(
            "No OCR engine available. Install paddleocr (recommended), "
            "easyocr, or ensure tesseract is installed with pytesseract "
            "Python package for OCR support."
        )

    def _try_init_paddleocr(self):
        """Attempt to initialize PaddleOCR."""
        if self._ocr is False:
            return None
        try:
            logger.info("Initializing PaddleOCR synchronously in main thread")
            logger.info("Importing paddleocr module")
            paddle_module = importlib.import_module("paddleocr")
            paddle_ocr = getattr(paddle_module, "PaddleOCR")
            logger.info("PaddleOCR class found, initializing with device: %s", self.config.get("ocr_device", "cpu"))

            ocr = paddle_ocr(
                use_angle_cls=True,
                lang="en",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                device=self.config.get("ocr_device", "cpu"),
                ocr_version="PP-OCRv4",
            )
            logger.info("PaddleOCR initialized successfully")
            return ocr
        except ImportError as e:
            logger.error("Failed to import PaddleOCR: %s", e)
            return None
        except (RuntimeError, AssertionError) as e:
            logger.warning("PaddleOCR init error (type=%s): %s", type(e).__name__, e)
            if "PDX has already been initialized" in str(e) or "paddle is unexpectedly loaded" in str(e):
                logger.warning("PaddleX/paddlex conflict - attempting to reuse existing instance")
                try:
                    paddle_module = importlib.import_module("paddleocr")
                    paddle_ocr = getattr(paddle_module, "PaddleOCR")
                    ocr = paddle_ocr(
                        use_angle_cls=True,
                        lang="en",
                        use_doc_orientation_classify=False,
                        use_doc_unwarping=False,
                        device=self.config.get("ocr_device", "cpu"),
                        ocr_version="PP-OCRv4",
                    )
                    logger.info("PaddleOCR reinitialized successfully after PDX conflict")
                    return ocr
                except (RuntimeError, AssertionError):
                    logger.error("Cannot create PaddleOCR instance due to PaddleX initialization conflict")
                    return None
            else:
                logger.error("PaddleOCR initialization failed: %s", e)
                return None
        except Exception as e:
            logger.error("Unexpected error initializing PaddleOCR: %s", e)
            return None

    def _try_init_tesseract(self):
        """Attempt to initialize Tesseract via pytesseract."""
        try:
            import pytesseract

            pytesseract.get_tesseract_version()
            logger.info("Tesseract OCR available via pytesseract: %s", pytesseract.get_tesseract_version())

            ocr_lang = self.config.get("ocr_lang", "deu+eng")
            available = pytesseract.get_languages()
            requested = [lang.strip() for part in ocr_lang.split("+") for lang in part.split(",") if lang.strip()]
            missing = [lang for lang in requested if lang not in available]
            if missing:
                logger.warning(
                    "Tesseract language pack(s) not installed: %s. "
                    "Install with: sudo apt install tesseract-ocr-%s  "
                    "(or the equivalent package for your distribution). "
                    "Configured ocr_lang='%s', available: %s",
                    ", ".join(missing),
                    " ".join(missing),
                    ocr_lang,
                    available,
                )
            return True
        except Exception as e:
            logger.warning("Tesseract OCR not available: %s", e)
            return None

    def _try_init_easyocr(self):
        """Attempt to initialize EasyOCR.

        EasyOCR is tried as the secondary fallback (after PaddleOCR). It
        pulls in PyTorch so it is not a lightweight dependency.
        """
        try:
            import easyocr

            lang = self.config.get("ocr_lang", "deu+eng")
            langs = [lang_code.replace("deu", "de").replace("eng", "en") for lang_code in lang.replace("+", " ").split()]
            reader = easyocr.Reader(langs, gpu=("gpu" in self.config.get("ocr_device", "cpu")))
            logger.info("EasyOCR initialized (langs=%s, gpu=%s)", langs, "gpu" in self.config.get("ocr_device", "cpu"))
            return reader
        except ImportError:
            logger.info("EasyOCR not installed — skipping")
            return None
        except Exception as e:
            logger.warning("EasyOCR initialization failed: %s", e)
            return None

    async def _process_with_easyocr(self, file_path: str, reader) -> dict[str, Any]:
        """Process with EasyOCR."""
        try:
            results = await asyncio.to_thread(reader.readtext, file_path)
            text = "\n".join(r[1] for r in results).strip()
            metadata = self._build_metadata(file_path, text, ocr_used=True)
            return {"text": text, "metadata": metadata, "ocr_used": True}
        except Exception as exc:
            logger.warning("EasyOCR failed for %s: %s", file_path, exc)
            return await self._process_with_existing(file_path)

    def _get_ocr(self):
        """Get the OCR instance, initializing if needed (fallback for async contexts)."""
        if self._ocr is None:
            logger.warning("OCR not initialized synchronously, falling back to async initialization")
            self._initialize_ocr_sync()
        if self._ocr_engine in ("tesseract",):
            return True
        return self._ocr if self._ocr is not False and self._ocr is not None else None

    def _extract_paddle_text(self, results: Any) -> str:
        """Extract paddle text the instance."""
        blocks = []
        for result in results or []:
            if isinstance(result, dict):
                rec_texts = result.get("rec_texts")
                if isinstance(rec_texts, list):
                    blocks.extend(t for t in rec_texts if t)
                    continue
                for block in result.get("ocr_results", []):
                    if isinstance(block, dict):
                        text = block.get("text", "")
                        if text:
                            blocks.append(text)
            elif hasattr(result, "json"):
                json_attr = result.json
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
        """Build metadata internally."""
        path = Path(file_path)
        merged = dict(metadata or {})
        merged["source"] = path.name
        merged["extension"] = path.suffix.lower()
        merged["pages"] = int(merged.get("pages", 0) or 0)
        merged["word_count"] = len(text.split())
        merged["char_count"] = len(text)
        merged["ocr_used"] = ocr_used
        merged["ocr_engine"] = self._ocr_engine
        return merged

    def _check_version_compatibility(self):
        """Check for known PaddlePaddle version compatibility issues."""
        try:
            import paddle

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
            pass
        except AssertionError:
            logger.debug("Skipping version compatibility check due to paddlex import conflict")
        except Exception as e:
            logger.warning("Failed to check PaddlePaddle version compatibility: %s", e)

    @property
    def ocr_engine(self) -> str | None:
        """Return the currently active OCR engine name, or None."""
        return self._ocr_engine
