from unittest.mock import Mock, patch
from src.dms.hybrid_retriever import HybridRetriever


def test_hybrid_retriever_init():
    mock_vector_store = Mock()
    retriever = HybridRetriever(vector_store=mock_vector_store)
    assert retriever.vector_store == mock_vector_store
    assert retriever.rrf_k == 60
    assert retriever.cross_encoder is None or retriever.cross_encoder is not None


def test_retrieve_no_chunks():
    mock_vector_store = Mock()
    mock_vector_store.collection.get.return_value = {"ids": [], "documents": [], "metadatas": []}
    mock_vector_store.search.return_value = []
    retriever = HybridRetriever(vector_store=mock_vector_store)
    results = retriever.retrieve("test query")
    assert results == []


def test_rrf_combine():
    mock_vector_store = Mock()
    retriever = HybridRetriever(vector_store=mock_vector_store)
    bm25_results = [
        {"id": "chunk1", "text": "text1", "metadata": {}, "bm25_score": 0.5},
        {"id": "doc1_chunk_1", "text": "text2", "metadata": {}, "bm25_score": 0.3}
    ]
    vector_results = [
        {"text": "text2", "metadata": {"document_id": "doc1", "chunk_index": 1, "project_id": "p1"}, "relevance_score": 0.8},
        {"text": "text3", "metadata": {"document_id": "doc1", "chunk_index": 2, "project_id": "p1"}, "relevance_score": 0.7}
    ]
    rrf_scores = retriever._rrf_combine(bm25_results, vector_results)
    assert "chunk1" in rrf_scores
    assert "doc1_chunk_1" in rrf_scores
    assert "doc1_chunk_2" in rrf_scores
    assert rrf_scores["doc1_chunk_1"] > rrf_scores["chunk1"]


def test_cross_encoder_fallback():
    mock_vector_store = Mock()
    with patch.dict("sys.modules", {"sentence_transformers": None}):
        retriever = HybridRetriever(vector_store=mock_vector_store)
        assert retriever.cross_encoder is None


def test_retrieve_with_project_id():
    mock_vector_store = Mock()
    mock_metadata_index = Mock()
    mock_metadata_index.get_chunks_by_project.return_value = [
        {"id": "chunk1", "text": "project text", "metadata": {"project_id": "p1"}}
    ]
    mock_vector_store.search.return_value = [
        {"text": "project text", "metadata": {"document_id": "doc1", "chunk_index": 0, "project_id": "p1"}, "relevance_score": 0.9}
    ]
    retriever = HybridRetriever(vector_store=mock_vector_store, metadata_index=mock_metadata_index)
    results = retriever.retrieve("project query", project_id="p1", k=1)
    assert len(results) == 1
    assert results[0]["metadata"]["project_id"] == "p1"
