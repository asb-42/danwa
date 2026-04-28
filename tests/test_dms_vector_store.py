from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_collection():
    collection = MagicMock()
    collection.count.return_value = 10
    return collection


@pytest.fixture
def mock_client(mock_collection):
    client = MagicMock()
    client.get_or_create_collection.return_value = mock_collection
    return client


@pytest.fixture
def store(mock_client):
    with patch("src.dms.vector_store.chromadb") as mock_chromadb:
        mock_chromadb.PersistentClient.return_value = mock_client
        from src.dms.vector_store import DMSVectorStore

        s = DMSVectorStore(config={"chroma_collection": "document_chunks"})
    return s


def test_add_chunks(store, mock_collection):
    chunks = [
        {"text": "chunk one", "chunk_index": 0, "page": 1, "metadata_json": "{}"},
        {"text": "chunk two", "chunk_index": 1, "page": 1, "metadata_json": "{}"},
    ]
    store.add_chunks("doc_001", chunks, project_id="proj_a")

    mock_collection.add.assert_called_once_with(
        ids=["doc_001_chunk_0", "doc_001_chunk_1"],
        documents=["chunk one", "chunk two"],
        metadatas=[
            {"document_id": "doc_001", "project_id": "proj_a", "chunk_index": 0, "page": 1},
            {"document_id": "doc_001", "project_id": "proj_a", "chunk_index": 1, "page": 1},
        ],
    )


def test_search_no_filter(store, mock_collection):
    mock_collection.query.return_value = {
        "documents": [["result text"]],
        "metadatas": [[{"document_id": "doc_001", "project_id": "", "chunk_index": 0, "page": 1}]],
        "distances": [[0.3]],
    }
    results = store.search("test query", k=5)

    mock_collection.query.assert_called_once_with(
        query_texts=["test query"],
        n_results=5,
        where=None,
        include=["documents", "metadatas", "distances"],
    )
    assert len(results) == 1
    assert results[0]["text"] == "result text"
    assert results[0]["relevance_score"] == pytest.approx(0.7)


def test_search_with_project_filter(store, mock_collection):
    mock_collection.query.return_value = {
        "documents": [["filtered result"]],
        "metadatas": [[{"document_id": "doc_002", "project_id": "proj_b", "chunk_index": 0, "page": 2}]],
        "distances": [[0.1]],
    }
    results = store.search("test query", project_id="proj_b", k=3)

    mock_collection.query.assert_called_once_with(
        query_texts=["test query"],
        n_results=3,
        where={"project_id": {"$eq": "proj_b"}},
        include=["documents", "metadatas", "distances"],
    )
    assert len(results) == 1
    assert results[0]["relevance_score"] == pytest.approx(0.9)


def test_search_empty_collection(store, mock_collection):
    mock_collection.count.return_value = 0
    results = store.search("test query")

    mock_collection.query.assert_not_called()
    assert results == []


def test_delete_document_chunks(store, mock_collection):
    store.delete_document_chunks("doc_001")

    mock_collection.delete.assert_called_once_with(
        where={"document_id": {"$eq": "doc_001"}}
    )


def test_count(store, mock_collection):
    mock_collection.count.return_value = 42
    assert store.count() == 42
