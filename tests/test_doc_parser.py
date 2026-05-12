import pytest
from src.tools.doc_parser import DocumentParser
import tempfile
from pathlib import Path
import os
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_plain_text_fallback():
    parser = DocumentParser()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Testinhalt\nZeile 2\n\n\n")
        f.flush()
        result = await parser.parse_file(f.name)
        assert "Testinhalt" in result["text"]
        assert result["metadata"]["char_count"] > 0


@pytest.mark.asyncio
async def test_parser_returns_metadata():
    parser = DocumentParser()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Content here")
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "metadata" in result
        assert "source" in result["metadata"]
        assert "extension" in result["metadata"]
        assert "char_count" in result["metadata"]
        assert "word_count" in result["metadata"]


@pytest.mark.asyncio
async def test_parser_missing_file():
    parser = DocumentParser()
    with pytest.raises(FileNotFoundError):
        await parser.parse_file("/nonexistent/file.txt")


@pytest.mark.asyncio
async def test_parser_truncates_long_text():
    parser = DocumentParser()
    
    long_text = "A" * 30000
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write(long_text)
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert result["metadata"]["truncated"] == True
        assert len(result["text"]) <= 26000


@pytest.mark.asyncio
async def test_parser_cleans_whitespace():
    parser = DocumentParser()
    
    text_with_extra = "Line 1\n\n\n\n\nLine 2    \n  Line 3"
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write(text_with_extra)
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "\n\n\n" not in result["text"]
        assert "  " not in result["text"]


@pytest.mark.asyncio
async def test_parser_unknown_extension():
    parser = DocumentParser()
    
    with tempfile.NamedTemporaryFile(suffix=".unknown", delete=False, mode="w") as f:
        f.write("Some content")
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "Some content" in result["text"]
        assert result["metadata"]["extension"] == ".unknown"
