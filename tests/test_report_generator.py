import pytest
from src.tools.report_generator import ReportGenerator
from src.core.debate_engine import DebateState
from datetime import datetime
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock


@pytest.fixture
def generator(tmp_path):
    with patch("src.tools.report_generator.Path") as mock_path:
        mock_path.return_value.mkdir = MagicMock()
        mock_path.return_value.__truediv__ = lambda s, o: tmp_path / "reports" / o
        gen = ReportGenerator()
        gen.output_dir = tmp_path / "reports"
        gen.output_dir.mkdir(exist_ok=True)
        return gen


@pytest.fixture
def sample_state():
    state = DebateState()
    state.context = "This is a test topic about AI in education."
    state.final_consensus = 0.85
    state.output = "Final argumentation here.\n- Point 1\n- Point 2"
    state.validation_report = [
        {
            "claim": "AI improves learning",
            "evidence": [{"title": "Study 1", "snippet": "Evidence 1"}]
        }
    ]
    state.precedents_retrieved = [{"document": "Precedent 1"}]
    return state


def test_generator_initialization(generator):
    assert generator.output_dir is not None
    assert generator.output_dir.exists()


@pytest.mark.asyncio
async def test_generate_docx(generator, sample_state):
    with patch("src.tools.report_generator.Document") as mock_doc_cls:
        mock_doc = MagicMock()
        mock_doc_cls.return_value = mock_doc
        
        path = await generator.generate(sample_state, fmt="docx")
        
        assert path is not None
        mock_doc.save.assert_called_once()


@pytest.mark.asyncio
async def test_generate_pdf(generator, sample_state):
    with patch("src.tools.report_generator.HTML") as mock_html_cls:
        mock_html = MagicMock()
        mock_html.write_pdf = MagicMock()
        mock_html_cls.return_value = mock_html
        
        with patch("src.tools.report_generator.html") as mock_html_module:
            mock_html_module.escape = lambda s: s
            
            path = await generator.generate(sample_state, fmt="pdf")
            
            assert path is not None
            mock_html.write_pdf.assert_called_once()


@pytest.mark.asyncio
async def test_generate_invalid_format(generator, sample_state):
    with pytest.raises(ValueError):
        await generator.generate(sample_state, fmt="invalid")


def test_build_docx_content(generator, sample_state):
    mock_doc = MagicMock()
    mock_doc.add_heading = MagicMock(return_value=MagicMock())
    mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
    mock_doc.add_table = MagicMock(return_value=MagicMock())
    
    with patch("src.tools.report_generator.Document", return_value=mock_doc):
        generator._build_docx(sample_state, generator.output_dir / "test.docx")
        
        mock_doc.add_heading.assert_called()
        mock_doc.add_paragraph.assert_called()
        mock_doc.save.assert_called_once()


def test_build_pdf_content(generator, sample_state):
    with patch("src.tools.report_generator.HTML") as mock_html_cls, \
         patch("src.tools.report_generator.html") as mock_html_module:
        
        mock_html_module.escape = lambda s: s.replace('"', '&quote;')
        
        mock_html = MagicMock()
        mock_html.write_pdf = MagicMock()
        mock_html_cls.return_value = mock_html
        
        generator._build_pdf(sample_state, generator.output_dir / "test.pdf")
        
        mock_html.write_pdf.assert_called_once()
        call_args = mock_html.write_pdf.call_args[0]
        assert len(call_args) > 0


@pytest.mark.asyncio
async def test_generate_creates_unique_filenames(generator, sample_state):
    with patch("src.tools.report_generator.Document") as mock_doc_cls:
        mock_doc = MagicMock()
        mock_doc_cls.return_value = mock_doc
        
        path1 = await generator.generate(sample_state, fmt="docx")
        path2 = await generator.generate(sample_state, fmt="docx")
        
        assert path1 != path2


def test_docx_includes_validation(generator, sample_state):
    mock_doc = MagicMock()
    mock_doc.add_heading = MagicMock(return_value=MagicMock())
    mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
    mock_doc.add_table = MagicMock(return_value=MagicMock())
    
    with patch("src.tools.report_generator.Document", return_value=mock_doc):
        generator._build_docx(sample_state, generator.output_dir / "test.docx")
        
        assert mock_doc.add_heading.call_count >= 3
        headings = [str(call) for call in mock_doc.add_heading.call_args_list]
        has_validation_heading = any("Fakten" in str(call) or "Valid" in str(call) for call in mock_doc.add_heading.call_args_list)
        assert has_validation_heading


def test_docx_truncates_long_context(generator):
    state = DebateState()
    state.context = "A" * 1500
    state.final_consensus = 0.5
    state.output = "Short output"
    
    mock_doc = MagicMock()
    mock_doc.add_heading = MagicMock(return_value=MagicMock())
    mock_doc.add_paragraph = MagicMock(return_value=MagicMock())
    mock_doc.add_table = MagicMock(return_value=MagicMock())
    
    with patch("src.tools.report_generator.Document", return_value=mock_doc):
        generator._build_docx(state, generator.output_dir / "test.docx")
        
        para_calls = mock_doc.add_paragraph.call_args_list
        for call in para_calls:
            args = call[0]
            if args and "A" in str(args[0]):
                assert "[gekürzt]" in str(args[0]) or len(args[0]) < 1500
