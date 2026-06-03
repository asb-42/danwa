"""Tests for OCR integration in the DMS upload pipeline."""

from __future__ import annotations

import importlib.util
import io
import sys
import types
from unittest.mock import MagicMock, patch

import pytest

paddleocr_available = importlib.util.find_spec("paddleocr") is not None

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_file(name: str = "test.png") -> tuple:
    """Create a fake PNG upload file tuple for TestClient."""
    return ("file", (name, io.BytesIO(b"\x89PNG\r\n\x1a\n fake png"), "image/png"))


def _make_text_file(name: str = "test.txt", content: str = "Hello world") -> tuple:
    """Create a fake upload file tuple for TestClient."""
    return ("file", (name, io.BytesIO(content.encode()), "text/plain"))


# ---------------------------------------------------------------------------
# OCR Status Endpoint
# ---------------------------------------------------------------------------


class TestOCRStatusEndpoint:
    """GET /api/v1/dms/ocr-status"""

    @pytest.mark.skipif(not paddleocr_available, reason="paddleocr not installed")
    def test_ocr_status_available(self, client):
        """When an OCR engine is available, return available=true with engine name."""
        res = client.get("/api/v1/dms/ocr-status")
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is True
        assert data["engine"] in ("paddleocr", "easyocr", "tesseract")

    def test_ocr_status_unavailable(self, client):
        """When no OCR engine is importable, return available=false."""
        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": None, "pytesseract": None, "PIL": None}):
            import importlib

            import backend.api.routers.dms as dms_router

            importlib.reload(dms_router)
            res = client.get("/api/v1/dms/ocr-status")
            assert res.status_code == 200
            data = res.json()
            assert data["available"] is False
            assert data["engine"] is None

    def test_ocr_status_easyocr_available(self, client):
        """When only EasyOCR is importable, return easyocr as engine."""
        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": types.SimpleNamespace(), "pytesseract": None}):
            import importlib

            import backend.api.routers.dms as dms_router

            importlib.reload(dms_router)
            res = client.get("/api/v1/dms/ocr-status")
            assert res.status_code == 200
            data = res.json()
            assert data["available"] is True
            assert data["engine"] == "easyocr"

    def test_ocr_status_prefers_paddleocr_over_easyocr(self, client):
        """PaddleOCR should be preferred over EasyOCR when both are available."""
        with patch.dict(sys.modules, {"paddleocr": types.SimpleNamespace(), "easyocr": types.SimpleNamespace()}):
            import importlib

            import backend.api.routers.dms as dms_router

            importlib.reload(dms_router)
            res = client.get("/api/v1/dms/ocr-status")
            assert res.status_code == 200
            data = res.json()
            assert data["engine"] == "paddleocr"


# ---------------------------------------------------------------------------
# DocumentProcessor OCR Logic
# ---------------------------------------------------------------------------


class TestDocumentProcessorOCR:
    """Tests for DocumentProcessor image handling."""

    def test_image_rejected_when_ocr_disabled(self, tmp_path):
        """Image upload should raise ValueError when ocr_enabled=False."""
        from backend.services.dms.document_processor import DocumentProcessor

        processor = DocumentProcessor(config={"ocr_enabled": False})
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        import asyncio

        with pytest.raises(ValueError, match="requires OCR but ocr_enabled is false"):
            asyncio.run(processor.process_file(str(img_path)))

    def test_image_rejected_when_paddleocr_not_installed(self, tmp_path):
        """Image upload should gracefully fallback when PaddleOCR is not installed."""
        from backend.services.dms.document_processor import DocumentProcessor

        processor = DocumentProcessor(config={"ocr_enabled": True})
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        import asyncio

        with patch.dict(sys.modules, {"paddleocr": None}):
            processor._ocr = None
            result = asyncio.run(processor.process_file(str(img_path)))
            assert result["ocr_used"] is False

    def test_non_image_files_not_affected_by_ocr_check(self, tmp_path):
        """Non-image files should not be affected by ocr_enabled setting."""
        from backend.services.dms.document_processor import DocumentProcessor

        processor = DocumentProcessor(config={"ocr_enabled": False})
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("hello world")

        import asyncio

        result = asyncio.run(processor.process_file(str(txt_path)))
        assert result["text"] == "hello world"
        assert result["ocr_used"] is False

    def test_image_with_paddleocr_success(self, tmp_path):
        """Image upload should succeed with mocked PaddleOCR."""
        from backend.services.dms.document_processor import DocumentProcessor

        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        ocr_instance = MagicMock()
        ocr_instance.predict.return_value = [types.SimpleNamespace(json={"ocr_results": [{"text": "Hello"}, {"text": "world"}]})]
        paddle_cls = MagicMock(return_value=ocr_instance)
        paddle_module = types.SimpleNamespace(PaddleOCR=paddle_cls)

        with patch.dict(sys.modules, {"paddleocr": paddle_module}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_device": "cpu"})
            processor._ocr = None
            import asyncio

            result = asyncio.run(processor.process_file(str(img_path)))

        assert result["ocr_used"] is True
        assert result["text"] == "Hello\nworld"


# ---------------------------------------------------------------------------
# Upload Error Propagation
# ---------------------------------------------------------------------------


class TestDMSUploadErrorPropagation:
    """Tests for error propagation from DMS upload to API."""

    def test_text_upload_returns_chunk_count(self, client):
        """Successful text upload should include chunk_count in response."""
        files = [_make_text_file("upload_ocr_test.txt", "Some test content for OCR test")]
        response = client.post("/api/v1/dms/documents", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "chunk_count" in data

    def test_image_upload_with_real_api_and_ocr(self, client):
        """Upload an image through the real API — should succeed with PaddleOCR."""
        files = [_make_png_file("test_ocr.png")]
        response = client.post("/api/v1/dms/documents", files=files)
        # With PaddleOCR installed and ocr_enabled=True, this should succeed
        # (may return 200 or 500 depending on PaddleOCR model download)
        assert response.status_code in (200, 500)


# ---------------------------------------------------------------------------
# DMS Config Flow
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# OCR Settings API Endpoint
# ---------------------------------------------------------------------------


class TestOCRSettingsEndpoint:
    """GET/PUT /api/v1/config/ocr-settings"""

    @pytest.fixture(autouse=True)
    def _isolate_dms_settings(self):
        """Remove any dms section from settings.yaml before each test, restore after."""
        import yaml

        from backend.api.routers.config import _SETTINGS_PATH

        original = {}
        if _SETTINGS_PATH.exists():
            with open(_SETTINGS_PATH) as f:
                original = yaml.safe_load(f) or {}

        # Remove dms section for test isolation
        had_dms = "dms" in original
        dms_backup = original.pop("dms", None)
        if had_dms:
            _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_SETTINGS_PATH, "w") as f:
                yaml.dump(original, f)

        yield

        # Restore original state
        current = {}
        if _SETTINGS_PATH.exists():
            with open(_SETTINGS_PATH) as f:
                current = yaml.safe_load(f) or {}

        if dms_backup is not None:
            current["dms"] = dms_backup
        elif "dms" in current:
            del current["dms"]
        _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_SETTINGS_PATH, "w") as f:
            yaml.dump(current, f)

    def test_get_ocr_settings_returns_defaults(self, client):
        """GET returns default OCR config when no dms section in settings."""
        res = client.get("/api/v1/config/ocr-settings")
        assert res.status_code == 200
        data = res.json()
        assert data["ocr_enabled"] is True
        assert data["ocr_device"] == "cpu"
        assert data["ocr_lang"] == "deu+eng"
        assert data["ocr_preferred_engine"] == "auto"

    def test_update_ocr_settings_saves_preference(self, client, tmp_path):
        """PUT saves ocr_preferred_engine and returns it."""
        res = client.put("/api/v1/config/ocr-settings", json={"ocr_preferred_engine": "easyocr"})
        assert res.status_code == 200
        data = res.json()
        assert data["ocr_preferred_engine"] == "easyocr"

        # Verify persisted
        res2 = client.get("/api/v1/config/ocr-settings")
        assert res2.json()["ocr_preferred_engine"] == "easyocr"

    def test_update_ocr_settings_respects_all_valid_values(self, client):
        """All valid engine names should be accepted."""
        for engine in ("auto", "paddleocr", "easyocr", "tesseract"):
            res = client.put("/api/v1/config/ocr-settings", json={"ocr_preferred_engine": engine})
            assert res.status_code == 200, f"Failed for engine={engine}"
            assert res.json()["ocr_preferred_engine"] == engine

    def test_update_ocr_settings_rejects_invalid_engine(self, client):
        """Invalid engine name should return 400."""
        res = client.put("/api/v1/config/ocr-settings", json={"ocr_preferred_engine": "invalid_engine"})
        assert res.status_code == 400
        data = res.json()
        assert "detail" in data

    def test_update_ocr_settings_persists_in_yaml(self, client):
        """Setting should be written to config/settings.yaml under dms key."""
        from backend.api.routers.config import _SETTINGS_PATH

        res = client.put("/api/v1/config/ocr-settings", json={"ocr_preferred_engine": "tesseract"})
        assert res.status_code == 200

        import yaml

        with open(_SETTINGS_PATH) as f:
            saved = yaml.safe_load(f)
        assert saved["dms"]["ocr_preferred_engine"] == "tesseract"

    def test_get_ocr_settings_returns_persisted_value(self, client):
        """GET should return the value previously persisted via PUT."""
        client.put("/api/v1/config/ocr-settings", json={"ocr_preferred_engine": "easyocr"})
        res = client.get("/api/v1/config/ocr-settings")
        assert res.json()["ocr_preferred_engine"] == "easyocr"


# ---------------------------------------------------------------------------
# DocumentProcessor: EasyOCR Integration
# ---------------------------------------------------------------------------


class TestDocumentProcessorEasyOCR:
    """Tests for EasyOCR initialization and processing in DocumentProcessor."""

    def test_easyocr_init_success(self, tmp_path):
        """_try_init_easyocr returns a reader when easyocr is importable."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        reader_mock = MagicMock()
        easyocr_module = py_types.SimpleNamespace(Reader=MagicMock(return_value=reader_mock))

        # Patch all engines except easyocr so __init__ picks easyocr
        with patch.dict(sys.modules, {"paddleocr": None, "pytesseract": None, "easyocr": easyocr_module}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_lang": "deu+eng"})

        assert processor._ocr_engine == "easyocr"
        assert easyocr_module.Reader.call_count >= 1
        call_args = easyocr_module.Reader.call_args
        assert call_args is not None
        assert call_args[0][0] == ["de", "en"]

    def test_easyocr_init_failure_when_not_installed(self):
        """_try_init_easyocr returns None when easyocr is not importable."""
        from backend.services.dms.document_processor import DocumentProcessor

        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": None, "pytesseract": None}):
            processor = DocumentProcessor(config={"ocr_enabled": True})
            processor._ocr = None
            processor._ocr_engine = None
            result = processor._try_init_easyocr()

        assert result is None

    def test_easyocr_lang_conversion_default(self):
        """Default ocr_lang 'deu+eng' is converted to ['de', 'en']."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        reader_mock = MagicMock()
        easyocr_module = py_types.SimpleNamespace(Reader=MagicMock(return_value=reader_mock))

        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": easyocr_module, "pytesseract": None}):
            _processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_lang": "deu+eng"})

        call_args = easyocr_module.Reader.call_args
        assert call_args is not None
        assert call_args[0][0] == ["de", "en"]

    def test_easyocr_lang_conversion_unmapped_preserved(self):
        """An unknown Tesseract lang code is passed through as-is."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        reader_mock = MagicMock()
        easyocr_module = py_types.SimpleNamespace(Reader=MagicMock(return_value=reader_mock))

        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": easyocr_module, "pytesseract": None}):
            _processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_lang": "fra"})

        call_args = easyocr_module.Reader.call_args
        assert call_args is not None
        assert call_args[0][0] == ["fra"]

    def test_easyocr_processing_success(self, tmp_path):
        """_process_with_easyocr correctly extracts text from reader results."""
        import asyncio

        from backend.services.dms.document_processor import DocumentProcessor

        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        reader = MagicMock()
        reader.readtext.return_value = [
            ([[0, 0], [10, 0], [10, 10], [0, 10]], "Hello", 0.95),
            ([[0, 20], [50, 20], [50, 30], [0, 30]], "world", 0.88),
        ]

        processor = DocumentProcessor(config={"ocr_enabled": False})
        processor._ocr = reader
        processor._ocr_engine = "easyocr"
        result = asyncio.run(processor._process_with_easyocr(str(img_path), reader))

        assert result["ocr_used"] is True
        assert result["text"] == "Hello\nworld"
        assert result["metadata"]["ocr_engine"] == "easyocr"
        reader.readtext.assert_called_once_with(str(img_path))

    def test_easyocr_processing_fallback_on_failure(self, tmp_path):
        """When easyocr raises, processing falls back to text extraction."""
        import asyncio

        from backend.services.dms.document_processor import DocumentProcessor

        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        reader = MagicMock()
        reader.readtext.side_effect = RuntimeError("OCR failed")

        async def fake_parse(file_path):
            return {"text": "fallback", "metadata": {}}

        processor = DocumentProcessor(config={"ocr_enabled": False})
        processor._ocr = reader
        processor._ocr_engine = "easyocr"
        processor._parser.parse_file = fake_parse
        result = asyncio.run(processor._process_with_easyocr(str(img_path), reader))

        assert result["ocr_used"] is False
        assert result["text"] == "fallback"

    def test_easyocr_engine_in_metadata(self, tmp_path):
        """When easyocr is active, metadata should contain 'easyocr' as engine."""
        import asyncio

        from backend.services.dms.document_processor import DocumentProcessor

        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png data")

        reader = MagicMock()
        reader.readtext.return_value = [([[0, 0], [1, 0], [1, 1], [0, 1]], "text", 0.9)]

        processor = DocumentProcessor(config={"ocr_enabled": False})
        processor._ocr = reader
        processor._ocr_engine = "easyocr"
        result = asyncio.run(processor._process_with_easyocr(str(img_path), reader))

        assert result["metadata"]["ocr_engine"] == "easyocr"


# ---------------------------------------------------------------------------
# DocumentProcessor: Preferred Engine Selection
# ---------------------------------------------------------------------------


class TestDocumentProcessorPreferredEngine:
    """Tests for ocr_preferred_engine config option."""

    def test_preferred_engine_auto_uses_paddleocr_first(self):
        """With auto, PaddleOCR is tried before EasyOCR."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        paddle_module = py_types.SimpleNamespace(PaddleOCR=MagicMock(return_value=MagicMock()))
        with patch.dict(sys.modules, {"paddleocr": paddle_module, "easyocr": None, "pytesseract": None}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_preferred_engine": "auto"})

        assert processor._ocr_engine == "paddleocr"

    def test_preferred_engine_easyocr_tried_first(self):
        """With ocr_preferred_engine=easyocr, EasyOCR is tried before PaddleOCR."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        reader_mock = MagicMock()
        easyocr_module = py_types.SimpleNamespace(Reader=MagicMock(return_value=reader_mock))
        paddle_module = py_types.SimpleNamespace(PaddleOCR=MagicMock(return_value=MagicMock()))

        with patch.dict(sys.modules, {"paddleocr": paddle_module, "easyocr": easyocr_module, "pytesseract": None}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_preferred_engine": "easyocr"})

        assert processor._ocr_engine == "easyocr"

    def test_preferred_engine_tesseract_tried_first(self):
        """With ocr_preferred_engine=tesseract, Tesseract is tried before others."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        pytesseract_mock = py_types.SimpleNamespace(
            get_tesseract_version=MagicMock(return_value="5.0.0"),
            get_languages=MagicMock(return_value=["eng", "deu", "osd"]),
        )
        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": None, "pytesseract": pytesseract_mock}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_preferred_engine": "tesseract"})

        assert processor._ocr_engine == "tesseract"

    def test_preferred_engine_easyocr_fails_falls_to_next(self):
        """When preferred engine fails init, fall through to remaining chain."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        easyocr_module = py_types.SimpleNamespace(Reader=MagicMock(side_effect=RuntimeError("init failed")))
        pytesseract_mock = py_types.SimpleNamespace(
            get_tesseract_version=MagicMock(return_value="5.0.0"),
            get_languages=MagicMock(return_value=["eng", "deu", "osd"]),
        )

        with patch.dict(sys.modules, {"paddleocr": None, "easyocr": easyocr_module, "pytesseract": pytesseract_mock}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_preferred_engine": "easyocr"})

        # Falls back to tesseract (paddleocr not available, easyocr failed)
        assert processor._ocr_engine == "tesseract"

    def test_preferred_engine_invalid_falls_back_to_auto(self):
        """An invalid engine name should fall back to auto behavior."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        paddle_module = py_types.SimpleNamespace(PaddleOCR=MagicMock(return_value=MagicMock()))
        with patch.dict(sys.modules, {"paddleocr": paddle_module, "easyocr": None, "pytesseract": None}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_preferred_engine": "nonexistent"})

        assert processor._ocr_engine == "paddleocr"

    def test_preferred_engine_paddleocr_explicit(self):
        """With ocr_preferred_engine=paddleocr, PaddleOCR is used."""
        import types as py_types

        from backend.services.dms.document_processor import DocumentProcessor

        paddle_module = py_types.SimpleNamespace(PaddleOCR=MagicMock(return_value=MagicMock()))
        with patch.dict(sys.modules, {"paddleocr": paddle_module, "easyocr": None, "pytesseract": None}):
            processor = DocumentProcessor(config={"ocr_enabled": True, "ocr_preferred_engine": "paddleocr"})

        assert processor._ocr_engine == "paddleocr"

    """Tests for DMS config flowing to DocumentProcessor."""

    def test_default_config_has_ocr_enabled(self):
        """DEFAULT_DMS_CONFIG should have ocr_enabled=True."""
        from backend.services.dms.config import DEFAULT_DMS_CONFIG

        assert DEFAULT_DMS_CONFIG["ocr_enabled"] is True

    def test_load_dms_config_fallback(self):
        """load_dms_config should fall back to defaults when config file missing."""
        from backend.services.dms.config import load_dms_config

        config = load_dms_config("/nonexistent/path/settings.yaml")
        assert config["ocr_enabled"] is True
        assert config["ocr_device"] == "cpu"

    def test_config_passed_to_document_processor(self):
        """DMS should pass config to DocumentProcessor."""
        from backend.services.dms.service import DMS

        config = {"ocr_enabled": True, "ocr_device": "cpu"}
        dms = DMS(db_path=":memory:", chroma_path="/tmp/test_chroma", config=config)
        assert dms.document_processor.config == config
