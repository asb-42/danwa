from unittest.mock import Mock, patch
from src.dms.metadata_index import MetadataIndex
from src.dms.vector_store import DMSVectorStore


def test_init_metadata_index():
    mock_chroma = Mock(spec=DMSVectorStore)
    idx = MetadataIndex(mock_chroma)
    assert idx.chroma_store == mock_chroma


def test_get_chunks_by_project_no_chunks():
    mock_chroma = Mock(spec=DMSVectorStore)
    mock_coll = Mock()
    mock_coll.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    mock_chroma.collection = mock_coll

    idx = MetadataIndex(mock_chroma)
    result = idx.get_chunks_by_project("proj1")
    assert result == []


def test_get_chunks_by_project_with_chunks():
    mock_chroma = Mock(spec=DMSVectorStore)
    mock_coll = Mock()
    mock_coll.get.return_value = {
        "ids": ["doc1_chunk_0"],
        "documents": ["Sample chunk text"],
        "metadatas": [{"project_id": "proj1", "document_id": "doc1", "chunk_index": 0}]
    }
    mock_chroma.collection = mock_coll

    with patch("src.dms.metadata_index.DMSDB") as MockDB:
        mock_db = Mock()
        mock_db.get_document.return_value = {
            "filename": "test.pdf",
            "uploaded_at": "2026-04-28T12:00:00"
        }
        MockDB.return_value = mock_db

        idx = MetadataIndex(mock_chroma)
        result = idx.get_chunks_by_project("proj1")

        assert len(result) == 1
        chunk = result[0]
        assert chunk["id"] == "doc1_chunk_0"
        assert chunk["text"] == "Sample chunk text"
        assert chunk["metadata"]["project_id"] == "proj1"
        assert chunk["metadata"]["document_id"] == "doc1"
        assert chunk["metadata"]["chunk_index"] == 0
        assert chunk["metadata"]["file_name"] == "test.pdf"
        assert chunk["metadata"]["upload_date"] == "2026-04-28T12:00:00"


def test_get_chunks_by_document():
    mock_chroma = Mock(spec=DMSVectorStore)
    mock_coll = Mock()
    mock_coll.get.return_value = {
        "ids": ["doc2_chunk_0", "doc2_chunk_1"],
        "documents": ["Chunk 0", "Chunk 1"],
        "metadatas": [
            {"project_id": "proj2", "document_id": "doc2", "chunk_index": 0},
            {"project_id": "proj2", "document_id": "doc2", "chunk_index": 1}
        ]
    }
    mock_chroma.collection = mock_coll

    with patch("src.dms.metadata_index.DMSDB") as MockDB:
        mock_db = Mock()
        mock_db.get_document.return_value = {
            "filename": "report.docx",
            "uploaded_at": "2026-04-27T10:00:00"
        }
        MockDB.return_value = mock_db

        idx = MetadataIndex(mock_chroma)
        result = idx.get_chunks_by_document("doc2")

        assert len(result) == 2
        assert all(c["metadata"]["document_id"] == "doc2" for c in result)
        assert result[0]["metadata"]["chunk_index"] == 0
        assert result[1]["metadata"]["chunk_index"] == 1


def test_get_chunks_by_date_range():
    mock_chroma = Mock(spec=DMSVectorStore)
    mock_coll = Mock()
    mock_coll.get.return_value = {
        "ids": ["doc3_chunk_0"],
        "documents": ["Date range chunk"],
        "metadatas": [{
            "project_id": "proj3",
            "document_id": "doc3",
            "chunk_index": 0,
            "upload_date": "2026-04-25"
        }]
    }
    mock_chroma.collection = mock_coll

    with patch("src.dms.metadata_index.DMSDB") as MockDB:
        mock_db = Mock()
        mock_db.get_document.return_value = {
            "filename": "data.csv",
            "uploaded_at": "2026-04-25T09:00:00"
        }
        MockDB.return_value = mock_db

        idx = MetadataIndex(mock_chroma)
        result = idx.get_chunks_by_date_range("2026-04-24", "2026-04-26")

        assert len(result) == 1
        assert result[0]["metadata"]["upload_date"] == "2026-04-25T09:00:00"
