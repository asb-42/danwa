import pytest
from unittest.mock import Mock, AsyncMock
from src.dms.rag_pipeline import RAGPipeline
from src.dms.document_processor import DocumentProcessor
from src.dms.chunker import TextChunker
from src.dms.vector_store import DMSVectorStore
from src.dms.database import DMSDB


@pytest.fixture
def mock_doc_processor():
    return Mock(spec=DocumentProcessor)


@pytest.fixture
def mock_chunker():
    chunker = Mock(spec=TextChunker)
    chunker.chunk.return_value = ["chunk1", "chunk2", "chunk3"]
    return chunker


@pytest.fixture
def mock_vector_store():
    return Mock(spec=DMSVectorStore)


@pytest.fixture
def mock_db():
    db = Mock(spec=DMSDB)
    db.get_document.return_value = {
        "id": "doc1",
        "project_id": "proj1",
        "filename": "test.txt",
        "uploaded_at": "2026-04-28T12:00:00",
    }
    return db


@pytest.fixture
def rag_pipeline(mock_doc_processor, mock_chunker, mock_vector_store, mock_db):
    return RAGPipeline(
        document_processor=mock_doc_processor,
        text_chunker=mock_chunker,
        vector_store=mock_vector_store,
        db=mock_db,
    )


def test_process_document_returns_chunk_ids_for_valid_text(rag_pipeline, mock_chunker, mock_db, mock_vector_store):
    mock_chunker.chunk.return_value = ["chunk1", "chunk2"]
    mock_db.get_document.return_value = {
        "project_id": "proj1",
        "filename": "test.txt",
        "uploaded_at": "2026-04-28",
    }
    result = rag_pipeline.process_document("doc1", "sample text")
    assert result == ["doc1_chunk_0", "doc1_chunk_1"]
    mock_vector_store.add_chunks.assert_called_once()
    assert mock_db.add_chunk.call_count == 2


def test_process_document_returns_empty_list_for_empty_text(rag_pipeline):
    result = rag_pipeline.process_document("doc1", "")
    assert result == []


def test_process_document_returns_empty_list_for_missing_document(rag_pipeline, mock_db):
    mock_db.get_document.return_value = None
    result = rag_pipeline.process_document("doc1", "sample text")
    assert result == []


def test_process_document_handles_chunking_error(rag_pipeline, mock_chunker):
    mock_chunker.chunk.side_effect = Exception("Chunking failed")
    result = rag_pipeline.process_document("doc1", "sample text")
    assert result == []


def test_process_document_handles_vector_store_add_error(rag_pipeline, mock_vector_store):
    mock_vector_store.add_chunks.side_effect = Exception("Vector store failed")
    result = rag_pipeline.process_document("doc1", "sample text")
    assert result == []


@pytest.mark.asyncio
async def test_process_file_uses_document_processor(rag_pipeline, mock_doc_processor, mock_chunker):
    mock_doc_processor.process_file = AsyncMock(return_value={"text": "extracted text"})
    mock_chunker.chunk.return_value = ["chunk1", "chunk2"]
    result = await rag_pipeline.process_file("doc1", "file.txt")
    mock_doc_processor.process_file.assert_called_once_with("file.txt")
    assert result == ["doc1_chunk_0", "doc1_chunk_1"]


def test_process_document_stores_correct_metadata_in_db(rag_pipeline, mock_db):
    rag_pipeline.process_document("doc1", "sample text")
    mock_db.add_chunk.assert_called()
    call_args = mock_db.add_chunk.call_args_list[0][1]
    assert call_args["document_id"] == "doc1"
    assert call_args["chunk_index"] == 0
    assert "file_name" in call_args["metadata_json"]
    assert "upload_date" in call_args["metadata_json"]
