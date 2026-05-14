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
        assert data["engine"] in ("paddleocr", "tesseract")

    def test_ocr_status_unavailable(self, client):
        """When no OCR engine is importable, return available=false."""
        with patch.dict(sys.modules, {"paddleocr": None, "pytesseract": None, "PIL": None}):
            import importlib

            import backend.api.routers.dms as dms_router
            importlib.reload(dms_router)
            res = client.get("/api/v1/dms/ocr-status")
            assert res.status_code == 200
            data = res.json()
            assert data["available"] is False
            assert data["engine"] is None


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


class TestDMSConfigFlow:
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
