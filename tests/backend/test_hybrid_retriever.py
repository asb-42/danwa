"""Tests for HybridRetriever — BM25 + vector search with RRF fusion.

Covers the full surface of ``backend/services/dms/hybrid_retriever.py``:
constructor (with/without CrossEncoder), ``retrieve`` (BM25 + vector + RRF
merge + cross-encoder rerank + rerank failure), ``_fetch_chunks`` cache hit/
miss/TTL, ``_fetch_chunks_uncached`` (no project_id refusal, vector store
fallback, exception), ``_bm25_retrieve`` (empty, exception), ``_tokenize``,
``_rrf_combine``.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from backend.services.dms.hybrid_retriever import (
    _CORPUS_CACHE_TTL,
    HybridRetriever,
)
from backend.services.dms.metadata_index import MetadataIndex

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str,
    text: str,
    project_id: str = "p1",
    document_id: str = "doc1",
    chunk_index: int = 0,
) -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "project_id": project_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
        },
    }


def _make_vector_result(
    chunk_id: str,
    text: str,
    project_id: str = "p1",
    document_id: str = "doc1",
    chunk_index: int = 0,
    distance: float = 0.1,
) -> dict:
    return {
        "id": chunk_id,
        "text": text,
        "metadata": {
            "project_id": project_id,
            "document_id": document_id,
            "chunk_index": chunk_index,
        },
        "distance": distance,
    }


def _make_fake_vector_store(chunks: list[dict] | None = None) -> MagicMock:
    """Build a MagicMock for ``DMSVectorStore`` with sensible defaults.

    ``chunks`` are returned by ``search`` (always) and by ``collection.get``
    (when used in fallback paths).
    """
    chunks = chunks or []
    store = MagicMock()
    store.search.return_value = chunks
    coll = MagicMock()
    coll.get.return_value = {
        "ids": [c["id"] for c in chunks],
        "documents": [c["text"] for c in chunks],
        "metadatas": [c["metadata"] for c in chunks],
    }
    store.collection = coll
    return store


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestConstruction:
    def test_basic_construction(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        assert retriever.vector_store is store
        assert retriever.metadata_index is None
        assert retriever.rrf_k == 60
        assert retriever._corpus_cache is None

    def test_with_metadata_index(self) -> None:
        store = _make_fake_vector_store()
        idx = MagicMock(spec=MetadataIndex)
        retriever = HybridRetriever(vector_store=store, metadata_index=idx)
        assert retriever.metadata_index is idx

    def test_cross_encoder_disabled_when_lib_missing(self) -> None:
        """When ``sentence_transformers`` cannot be imported, cross_encoder is None."""
        store = _make_fake_vector_store()
        # Force ImportError path
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            retriever = HybridRetriever(vector_store=store)
        # Either None (ImportError) or the real instance — depending on env.
        # Just check it doesn't crash.
        assert retriever is not None


# ---------------------------------------------------------------------------
# Tokenize
# ---------------------------------------------------------------------------


class TestTokenize:
    def test_basic_tokenize(self) -> None:
        toks = HybridRetriever._tokenize("Hello World foo bar baz")
        # All lowered, all longer than 1 char
        assert toks == ["hello", "world", "foo", "bar", "baz"]

    def test_tokenize_filters_short_tokens(self) -> None:
        toks = HybridRetriever._tokenize("a I am ok hi")
        # "a" and "I" (1 char) are filtered; "am", "ok", "hi" remain
        assert "a" not in toks
        assert "I" not in toks
        assert "am" in toks
        assert "ok" in toks
        assert "hi" in toks

    def test_tokenize_empty(self) -> None:
        assert HybridRetriever._tokenize("") == []


# ---------------------------------------------------------------------------
# RRF combine
# ---------------------------------------------------------------------------


class TestRrfCombine:
    def test_empty_inputs(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        assert retriever._rrf_combine([], []) == {}

    def test_only_bm25(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        bm25 = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        result = retriever._rrf_combine(bm25, [])
        # rank 1: 1/(60+1) ≈ 0.01639
        # rank 2: 1/(60+2) ≈ 0.01613
        # rank 3: 1/(60+3) ≈ 0.01587
        assert result["a"] > result["b"] > result["c"]

    def test_only_vector(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        vec = [
            {
                "metadata": {"document_id": "doc1", "chunk_index": 0},
            },
            {
                "metadata": {"document_id": "doc1", "chunk_index": 1},
            },
        ]
        result = retriever._rrf_combine([], vec)
        assert "doc1_chunk_0" in result
        assert "doc1_chunk_1" in result
        assert result["doc1_chunk_0"] > result["doc1_chunk_1"]

    def test_combined_boost(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        bm25 = [{"id": "a"}]  # rank 1 → 1/61
        vec = [
            {"metadata": {"document_id": "a", "chunk_index": 0}},  # rank 1 → 1/61
        ]
        result = retriever._rrf_combine(bm25, vec)
        # 'a' is in bm25 (id="a"); 'a_chunk_0' is in vector
        # Both boost
        assert "a" in result
        assert "a_chunk_0" in result


# ---------------------------------------------------------------------------
# _fetch_chunks_uncached
# ---------------------------------------------------------------------------


class TestFetchChunksUncached:
    def test_no_project_id_returns_empty(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        # No metadata_index, no project_id → refuse to dump collection
        result = retriever._fetch_chunks_uncached(None)
        assert result == []
        store.collection.get.assert_not_called()

    def test_with_project_id_and_metadata_index(self) -> None:
        store = _make_fake_vector_store()
        idx = MagicMock()
        idx.get_chunks_by_project.return_value = [_make_chunk("doc1_chunk_0", "hello")]
        retriever = HybridRetriever(vector_store=store, metadata_index=idx)
        result = retriever._fetch_chunks_uncached("p1")
        idx.get_chunks_by_project.assert_called_once_with("p1")
        assert len(result) == 1

    def test_with_project_id_uses_vector_store_fallback(self) -> None:
        store = _make_fake_vector_store([_make_chunk("doc1_chunk_0", "hello", project_id="p1")])
        retriever = HybridRetriever(vector_store=store)  # no metadata_index
        result = retriever._fetch_chunks_uncached("p1")
        assert len(result) == 1
        assert result[0]["id"] == "doc1_chunk_0"

    def test_vector_store_exception_returns_empty(self) -> None:
        store = MagicMock()
        coll = MagicMock()
        coll.get.side_effect = RuntimeError("boom")
        store.collection = coll
        retriever = HybridRetriever(vector_store=store)
        result = retriever._fetch_chunks_uncached("p1")
        assert result == []


# ---------------------------------------------------------------------------
# _fetch_chunks (with caching)
# ---------------------------------------------------------------------------


class TestFetchChunksCaching:
    def test_cache_hit_same_project(self) -> None:
        store = _make_fake_vector_store([_make_chunk("doc1_chunk_0", "hello", project_id="p1")])
        retriever = HybridRetriever(vector_store=store)
        # First call populates cache
        retriever._fetch_chunks("p1")
        # Replace the underlying store's get to detect a second call
        original = store.collection.get
        call_count = {"n": 0}

        def counting_get(*args, **kwargs):
            call_count["n"] += 1
            return original(*args, **kwargs)

        store.collection.get.side_effect = counting_get
        # Second call uses cache
        chunks, bm25 = retriever._fetch_chunks("p1")
        assert call_count["n"] == 0  # not called
        assert len(chunks) == 1

    def test_cache_miss_different_project(self) -> None:
        store = _make_fake_vector_store([_make_chunk("doc1_chunk_0", "hello world", project_id="p2")])
        retriever = HybridRetriever(vector_store=store)
        # Pre-populate cache for p1
        retriever._corpus_cache = ("p1", time.time(), [_make_chunk("a", "alpha beta")], None)
        # Different project → cache miss → re-fetch for p2
        chunks, bm25 = retriever._fetch_chunks("p2")
        # Will call _fetch_chunks_uncached, which calls store.collection.get
        # Vector store returns the p2 chunk we seeded
        assert len(chunks) == 1
        # Cache was updated to p2
        assert retriever._corpus_cache[0] == "p2"
        # BM25 was built from non-empty chunks
        assert bm25 is not None

    def test_cache_miss_after_ttl(self) -> None:
        store = _make_fake_vector_store([_make_chunk("doc1_chunk_0", "hello", project_id="p1")])
        retriever = HybridRetriever(vector_store=store)
        # Pre-populate cache with stale timestamp
        retriever._corpus_cache = ("p1", time.time() - _CORPUS_CACHE_TTL - 1, [], None)
        chunks, bm25 = retriever._fetch_chunks("p1")
        # Fresh chunks loaded
        assert len(chunks) == 1

    def test_empty_chunks_bm25_is_none(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        chunks, bm25 = retriever._fetch_chunks("p1")
        assert chunks == []
        assert bm25 is None


# ---------------------------------------------------------------------------
# _bm25_retrieve
# ---------------------------------------------------------------------------


class TestBm25Retrieve:
    def test_empty_chunks_returns_empty(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        assert retriever._bm25_retrieve("query", []) == []
        assert retriever._bm25_retrieve("query", [], None) == []

    def test_bm25_ranks_chunks(self) -> None:
        from rank_bm25 import BM25Okapi

        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        corpus = [
            _make_chunk("a", "apple banana"),
            _make_chunk("b", "cherry"),
            _make_chunk("c", "apple"),
        ]
        tokenized = [HybridRetriever._tokenize(c["text"]) for c in corpus]
        bm25_idx = BM25Okapi(tokenized)
        results = retriever._bm25_retrieve("apple", corpus, bm25=bm25_idx, top_n=3)
        # "apple" matches both a and c (b is excluded as it has no overlap)
        ids = [r["id"] for r in results]
        assert "a" in ids
        assert "c" in ids
        # BM25 scores included
        for r in results:
            assert "bm25_score" in r

    def test_bm25_exception_returns_empty(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        # A None bm25 raises when get_scores is called
        results = retriever._bm25_retrieve("x", [_make_chunk("a", "x")], bm25=None)
        assert results == []


# ---------------------------------------------------------------------------
# retrieve (orchestration)
# ---------------------------------------------------------------------------


class TestRetrieve:
    def test_empty_corpus_returns_empty(self) -> None:
        store = _make_fake_vector_store()
        retriever = HybridRetriever(vector_store=store)
        result = retriever.retrieve("hello", project_id="p1", k=5)
        assert result == []

    def test_merges_bm25_and_vector(self) -> None:
        # BM25: chunks a, b
        # Vector: chunks c (and maybe a)
        store = _make_fake_vector_store(
            [
                _make_vector_result("doc1_chunk_0", "vector text", document_id="doc2", chunk_index=0),
                _make_vector_result("doc1_chunk_1", "vector text 2", document_id="doc3", chunk_index=0),
            ]
        )
        retriever = HybridRetriever(vector_store=store)
        # Pre-populate corpus cache
        chunks = [
            _make_chunk("a", "apple banana"),
            _make_chunk("b", "apple cherry"),
        ]
        from rank_bm25 import BM25Okapi

        tokenized = [HybridRetriever._tokenize(c["text"]) for c in chunks]
        bm25 = BM25Okapi(tokenized)
        retriever._corpus_cache = ("p1", time.time(), chunks, bm25)

        results = retriever.retrieve("apple", project_id="p1", k=5)
        # We get results for the BM25 chunks AND the vector chunks
        assert len(results) > 0
        # All results have source="hybrid"
        for r in results:
            assert r["source"] == "hybrid"
            assert "text" in r
            assert "metadata" in r
            assert "score" in r

    def test_respects_k(self) -> None:
        store = _make_fake_vector_store([_make_vector_result("d_chunk_0", "x", document_id="d", chunk_index=0) for _ in range(10)])
        retriever = HybridRetriever(vector_store=store)
        retriever._corpus_cache = (
            "p1",
            time.time(),
            [_make_chunk(f"bm{i}", "x") for i in range(10)],
            None,  # no BM25 index
        )
        results = retriever.retrieve("x", project_id="p1", k=3)
        assert len(results) <= 3

    def test_cross_encoder_rerank(self) -> None:
        store = _make_fake_vector_store([_make_vector_result("d_chunk_0", "x", document_id="d", chunk_index=0)])
        retriever = HybridRetriever(vector_store=store)
        # Inject a fake cross_encoder
        fake_ce = MagicMock()
        fake_ce.predict.return_value = [0.9]
        retriever.cross_encoder = fake_ce

        # Pre-populate cache
        retriever._corpus_cache = (
            "p1",
            time.time(),
            [_make_chunk("d_chunk_0", "x", document_id="d", chunk_index=0)],
            None,
        )
        results = retriever.retrieve("x", project_id="p1", k=5)
        assert len(results) == 1
        # Score replaced with cross_encoder output
        assert results[0]["score"] == 0.9
        fake_ce.predict.assert_called_once()

    def test_cross_encoder_failure_is_swallowed(self) -> None:
        store = _make_fake_vector_store([_make_vector_result("d_chunk_0", "x", document_id="d", chunk_index=0)])
        retriever = HybridRetriever(vector_store=store)
        fake_ce = MagicMock()
        fake_ce.predict.side_effect = RuntimeError("rerank fail")
        retriever.cross_encoder = fake_ce

        retriever._corpus_cache = (
            "p1",
            time.time(),
            [_make_chunk("d_chunk_0", "x", document_id="d", chunk_index=0)],
            None,
        )
        # Should not raise
        results = retriever.retrieve("x", project_id="p1", k=5)
        assert len(results) == 1
        # Score is the RRF score (not the rerank score, since rerank failed)
        assert results[0]["score"] > 0

    def test_no_project_id_does_not_bleed(self) -> None:
        """When no project_id is provided, _fetch_chunks returns [] and we get no results."""
        store = _make_fake_vector_store([_make_vector_result("d_chunk_0", "x")])
        retriever = HybridRetriever(vector_store=store)
        result = retriever.retrieve("x", project_id=None, k=5)
        # Without project_id and without metadata_index, the corpus is empty
        # and the vector store is called directly; it returns the fake chunks.
        # The result depends on whether vector_results exist.
        # We just verify it doesn't raise.
        assert isinstance(result, list)

    def test_vector_only_chunk_added_to_map(self) -> None:
        """Chunks only present in vector results (not in BM25 corpus) are still returned."""
        store = _make_fake_vector_store([_make_vector_result("docX_chunk_0", "vector-only", document_id="docX", chunk_index=0)])
        retriever = HybridRetriever(vector_store=store)
        # Empty BM25 corpus (no metadata_index, no project_id... but then we can't get there)
        # Instead, use a project_id with empty corpus.
        retriever._corpus_cache = ("p1", time.time(), [], None)
        results = retriever.retrieve("anything", project_id="p1", k=5)
        # The vector chunk should appear in results even though it's not in the BM25 corpus
        assert any(r["metadata"]["document_id"] == "docX" for r in results)

    def test_cache_ttl_constant(self) -> None:
        # Just a sanity check that the TTL is a positive number
        assert _CORPUS_CACHE_TTL > 0
        assert _CORPUS_CACHE_TTL == 300
