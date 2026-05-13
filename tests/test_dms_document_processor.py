import sys
import types
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

document_processor = importlib.import_module("src.dms.document_processor")


@pytest.mark.asyncio
async def test_process_txt_uses_existing_parser(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text("hello")

    with patch("src.dms.document_processor.DocumentParser") as parser_cls:
        parser = parser_cls.return_value
        parser.parse_file = AsyncMock(return_value={"text": "plain text", "metadata": {"pages": 0, "extra": "value"}})
        processor = document_processor.DocumentProcessor({})

        result = await processor.process_file(str(file_path))

    parser.parse_file.assert_awaited_once_with(str(file_path))
    assert result["text"] == "plain text"
    assert result["ocr_used"] is False
    assert result["metadata"]["source"] == "notes.txt"
    assert result["metadata"]["extension"] == ".txt"
    assert result["metadata"]["ocr_used"] is False
    assert result["metadata"]["extra"] == "value"


@pytest.mark.asyncio
async def test_process_pdf_uses_existing_parser(tmp_path):
    file_path = tmp_path / "report.pdf"
    file_path.write_bytes(b"%PDF-1.4")

    with patch("src.dms.document_processor.DocumentParser") as parser_cls:
        parser = parser_cls.return_value
        parser.parse_file = AsyncMock(return_value={"text": "pdf body", "metadata": {"pages": 3}})
        processor = document_processor.DocumentProcessor({})

        result = await processor.process_file(str(file_path))

    parser.parse_file.assert_awaited_once_with(str(file_path))
    assert result["text"] == "pdf body"
    assert result["ocr_used"] is False
    assert result["metadata"]["pages"] == 3
    assert result["metadata"]["extension"] == ".pdf"


@pytest.mark.asyncio
async def test_process_image_uses_paddle(tmp_path):
    file_path = tmp_path / "scan.png"
    file_path.write_bytes(b"png")
    ocr_instance = MagicMock()
    ocr_instance.predict.return_value = [types.SimpleNamespace(json={"ocr_results": [{"text": "Hello"}, {"text": "world"}]})]
    paddle_cls = MagicMock(return_value=ocr_instance)
    paddle_module = types.SimpleNamespace(PaddleOCR=paddle_cls)

    with patch.dict(sys.modules, {"paddleocr": paddle_module}):
        with patch("src.dms.document_processor.DocumentParser") as parser_cls:
            parser = parser_cls.return_value
            parser.parse_file = AsyncMock()
            processor = document_processor.DocumentProcessor({"ocr_device": "cpu"})

            result = await processor.process_file(str(file_path))

    parser.parse_file.assert_not_awaited()
    paddle_cls.assert_called_once_with(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        device="cpu",
        ocr_version="PP-OCRv4",
    )
    ocr_instance.predict.assert_called_once_with(str(file_path))
    assert result == {
        "text": "Hello\nworld",
        "metadata": {
            "source": "scan.png",
            "extension": ".png",
            "pages": 0,
            "word_count": 2,
            "char_count": 11,
            "ocr_used": True,
        },
        "ocr_used": True,
    }


@pytest.mark.asyncio
async def test_process_image_fallback_no_paddle(tmp_path):
    file_path = tmp_path / "scan.png"
    file_path.write_bytes(b"png")

    with patch.dict(sys.modules, {"paddleocr": None}):
        with patch("src.dms.document_processor.DocumentParser") as parser_cls:
            parser = parser_cls.return_value
            parser.parse_file = AsyncMock(return_value={"text": "fallback text", "metadata": {"pages": 0}})
            processor = document_processor.DocumentProcessor({})

            result = await processor.process_file(str(file_path))

    parser.parse_file.assert_awaited_once_with(str(file_path))
    assert result["text"] == "fallback text"
    assert result["ocr_used"] is False
    assert result["metadata"]["ocr_used"] is False


@pytest.mark.asyncio
async def test_process_image_fallback_paddle_error(tmp_path):
    file_path = tmp_path / "scan.png"
    file_path.write_bytes(b"png")
    ocr_instance = MagicMock()
    ocr_instance.predict.side_effect = RuntimeError("ocr failure")
    paddle_module = types.SimpleNamespace(PaddleOCR=MagicMock(return_value=ocr_instance))

    with patch.dict(sys.modules, {"paddleocr": paddle_module}):
        with patch("src.dms.document_processor.DocumentParser") as parser_cls:
            parser = parser_cls.return_value
            parser.parse_file = AsyncMock(return_value={"text": "fallback text", "metadata": {"pages": 0}})
            processor = document_processor.DocumentProcessor({})

            result = await processor.process_file(str(file_path))

    parser.parse_file.assert_awaited_once_with(str(file_path))
    assert result["text"] == "fallback text"
    assert result["ocr_used"] is False
    assert result["metadata"]["ocr_used"] is False


@pytest.mark.asyncio
async def test_metadata_returned(tmp_path):
    file_path = tmp_path / "meta.txt"
    file_path.write_text("hello")

    with patch("src.dms.document_processor.DocumentParser") as parser_cls:
        parser = parser_cls.return_value
        parser.parse_file = AsyncMock(return_value={"text": "two words", "metadata": {"pages": 7, "truncated": True}})
        processor = document_processor.DocumentProcessor({})

        result = await processor.process_file(str(file_path))

    metadata = result["metadata"]
    assert set(["source", "extension", "pages", "word_count", "char_count", "ocr_used"]).issubset(metadata)
    assert metadata["source"] == "meta.txt"
    assert metadata["extension"] == ".txt"
    assert metadata["pages"] == 7
    assert metadata["word_count"] == 2
    assert metadata["char_count"] == len("two words")
    assert metadata["ocr_used"] is False
    assert metadata["truncated"] is True
