import pytest
from src.tools.doc_parser import DocumentParser
import tempfile
from pathlib import Path

@pytest.mark.asyncio
async def test_plain_text_fallback():
    parser = DocumentParser()
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w") as f:
        f.write("Testinhalt\nZeile 2\n\n\n")
        f.flush()
        result = await parser.parse_file(f.name)
        assert "Testinhalt" in result["text"]
        assert result["metadata"]["char_count"] > 0