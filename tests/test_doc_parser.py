import pytest
from src.tools.doc_parser import DocumentParser
import tempfile
from pathlib import Path
import os


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
async def test_parser_pdf_plumber(monkeypatch):
    parser = DocumentParser()
    
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "PDF content here"
    mock_pdf.open.return_value.__enter__.return_value.pages = [mock_page] * 3
    mock_pdf.open.return_value.__enter__.return_value.__len__.return_value = 3
    
    import src.tools.doc_parser as mod
    monkeypatch.setattr(mod, "pdfplumber", mock_pdf)
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"fake pdf")
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "PDF content" in result["text"]
        assert result["metadata"]["pages"] == 3


@pytest.mark.asyncio
async def test_parser_pdf_fallback_to_pypdf(monkeypatch):
    parser = DocumentParser()
    
    import src.tools.doc_parser as mod
    
    mock_pdfplumber = MagicMock(side_effect=ImportError("Not found"))
    monkeypatch.setattr(mod, "pdfplumber", mock_pdfplumber)
    
    mock_pypdf = MagicMock()
    mock_reader = MagicMock()
    mock_reader.pages = [MagicMock(extract_text=MagicMock(return_value="PyPDF content"))]
    mock_pypdf.PdfReader.return_value = mock_reader
    monkeypatch.setattr(mod, "pypdf", mock_pypdf)
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"fake pdf")
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "PyPDF content" in result["text"]


@pytest.mark.asyncio
async def test_parser_docx(monkeypatch):
    parser = DocumentParser()
    
    mock_docx = MagicMock()
    mock_para = MagicMock()
    mock_para.text = "DOCX content"
    mock_doc = MagicMock()
    mock_doc.paragraphs = [mock_para]
    mock_docx.Document.return_value = mock_doc
    
    import src.tools.doc_parser as mod
    monkeypatch.setattr(mod, "docx", mock_docx)
    
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(b"fake docx")
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "DOCX content" in result["text"]


@pytest.mark.asyncio
async def test_parser_odt(monkeypatch):
    parser = DocumentParser()
    
    mock_odf = MagicMock()
    mock_teletype = MagicMock()
    mock_teletype.extractText.return_value = "ODT content here"
    mock_odf.teletype = mock_teletype
    mock_odf.opendocument = MagicMock()
    mock_odf.opendocument.load.return_value = MagicMock()
    
    import src.tools.doc_parser as mod
    monkeypatch.setattr(mod, "odf", mock_odf)
    
    with tempfile.NamedTemporaryFile(suffix=".odt", delete=False) as f:
        f.write(b"fake odt")
        f.flush()
        result = await parser.parse_file(f.name)
        
        assert "ODT content" in result["text"]


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
