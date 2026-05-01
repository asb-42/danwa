import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import importlib

document_processor = importlib.import_module("src.dms.document_processor")


class TestPaddleOCRIntegration:
    @pytest.mark.asyncio
    async def test_process_image_with_paddleocr(self, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png content")

        ocr_instance = MagicMock()
        ocr_instance.predict.return_value = [
            types.SimpleNamespace(json={"ocr_results": [{"text": "Hello"}, {"text": "World"}]})
        ]
        paddle_cls = MagicMock(return_value=ocr_instance)
        paddle_module = types.SimpleNamespace(PaddleOCR=paddle_cls)

        with patch.dict(sys.modules, {"paddleocr": paddle_module}):
            with patch("src.dms.document_processor.DocumentParser") as parser_cls:
                parser = parser_cls.return_value
                parser.parse_file = AsyncMock()
                processor = document_processor.DocumentProcessor({"ocr_device": "cpu"})

                result = await processor.process_file(str(img_path))

        parser.parse_file.assert_not_awaited()
        paddle_cls.assert_called_once_with(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            device="cpu",
        )
        ocr_instance.predict.assert_called_once_with(str(img_path))
        assert result["ocr_used"] is True
        assert result["text"] == "Hello\nWorld"
        assert result["metadata"]["ocr_used"] is True

    @pytest.mark.asyncio
    async def test_process_pdf_with_paddleocr(self, tmp_path):
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")

        paddle_module = types.SimpleNamespace(PaddleOCR=MagicMock())
        with patch.dict(sys.modules, {"paddleocr": paddle_module}):
            with patch("src.dms.document_processor.DocumentParser") as parser_cls:
                parser = parser_cls.return_value
                parser.parse_file = AsyncMock(
                    return_value={"text": "pdf content", "metadata": {"pages": 1}}
                )
                processor = document_processor.DocumentProcessor({})

                result = await processor.process_file(str(pdf_path))

        paddle_module.PaddleOCR.assert_not_called()
        parser.parse_file.assert_awaited_once_with(str(pdf_path))
        assert result["ocr_used"] is False
        assert result["text"] == "pdf content"

    @pytest.mark.asyncio
    async def test_fallback_to_existing_parser_when_paddleocr_unavailable(self, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png")

        with patch.dict(sys.modules, {"paddleocr": None}):
            with patch("src.dms.document_processor.DocumentParser") as parser_cls:
                parser = parser_cls.return_value
                parser.parse_file = AsyncMock(
                    return_value={"text": "fallback text", "metadata": {"pages": 0}}
                )
                processor = document_processor.DocumentProcessor({})

                result = await processor.process_file(str(img_path))

        parser.parse_file.assert_awaited_once_with(str(img_path))
        assert result["ocr_used"] is False
        assert result["text"] == "fallback text"

    @pytest.mark.asyncio
    async def test_paddleocr_initialization_failure(self, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"fake png")

        paddle_cls = MagicMock(return_value=None)
        paddle_module = types.SimpleNamespace(PaddleOCR=paddle_cls)

        with patch.dict(sys.modules, {"paddleocr": paddle_module}):
            with patch("src.dms.document_processor.DocumentParser") as parser_cls:
                parser = parser_cls.return_value
                parser.parse_file = AsyncMock(
                    return_value={"text": "fallback text", "metadata": {"pages": 0}}
                )
                processor = document_processor.DocumentProcessor({})

                result = await processor.process_file(str(img_path))

        parser.parse_file.assert_awaited_once_with(str(img_path))
        assert result["ocr_used"] is False
        assert result["text"] == "fallback text"
