from src.dms.rag_context_formatter import RAGContextFormatter


def test_empty_chunks_returns_empty_string():
    formatter = RAGContextFormatter()
    result = formatter.format([])
    assert result == ""


def test_single_chunk_with_metadata():
    chunk = {
        "text": "Sample argument text",
        "metadata": {
            "file_name": "debate_transcript.pdf",
            "chunk_index": 2,
            "project_id": "proj_123"
        },
        "score": 0.89
    }
    result = RAGContextFormatter().format([chunk])
    expected = "[Document 1 from debate_transcript.pdf]: Sample argument text\n\n"
    assert result == expected


def test_multiple_chunks_format_correctly():
    chunks = [
        {"text": "First point", "metadata": {"file_name": "doc1.pdf"}},
        {"text": "Second point", "metadata": {"file_name": "doc2.pdf"}},
        {"text": "Third point", "metadata": {"file_name": "doc3.pdf"}}
    ]
    result = RAGContextFormatter().format(chunks)
    expected = (
        "[Document 1 from doc1.pdf]: First point\n\n"
        "[Document 2 from doc2.pdf]: Second point\n\n"
        "[Document 3 from doc3.pdf]: Third point\n\n"
    )
    assert result == expected


def test_truncation_with_max_chars():
    long_text = "a" * 4000
    chunk = {"text": long_text, "metadata": {"file_name": "long_doc.pdf"}}
    result = RAGContextFormatter().format([chunk], max_chars=100)
    assert len(result) == 100
    assert result.endswith("...")


def test_missing_file_name_uses_unknown():
    chunk = {"text": "No file name here", "metadata": {"chunk_index": 5}}
    result = RAGContextFormatter().format([chunk])
    expected = "[Document 1 from Unknown]: No file name here\n\n"
    assert result == expected


def test_chunk_metadata_accessible():
    chunk = {
        "text": "Test",
        "metadata": {
            "file_name": "test.pdf",
            "chunk_index": 3,
            "project_id": "proj_456"
        }
    }
    formatter = RAGContextFormatter()
    result = formatter.format([chunk])
    assert "test.pdf" in result
