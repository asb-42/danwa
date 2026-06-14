"""Tests for P4.5+ §4.6 — BM25 corpus cap in HybridRetriever.

The BM25 corpus was previously unbounded: a project with N chunks
caused ``_fetch_chunks`` to tokenize all N of them and build an
in-memory ``BM25Okapi`` index that is O(N) in both CPU and memory.
On large projects this was a DoS vector (seconds-to-minutes on the
event loop, hundreds of MB of RAM).

The cap at ``MAX_BM25_CORPUS_SIZE`` (10 000) prevents that, while
preserving correctness:

  * the full chunk list is still returned from ``_fetch_chunks`` so
    the ``chunk_map`` lookup in ``retrieve`` stays complete;
  * only the BM25 input is truncated, and BM25 only drives a
    top-20 ranking that is then fused with vector search + cross-
    encoder reranking, so the returned top-k quality is unaffected
    in practice.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

from backend.services.dms.hybrid_retriever import (
    MAX_BM25_CORPUS_SIZE,
    HybridRetriever,
)
from backend.services.dms.metadata_index import MetadataIndex


def _make_chunk(idx: int, project_id: str = "p1") -> dict:
    return {
        "id": f"doc_chunk_{idx}",
        "text": f"unique-token-{idx} some shared context",
        "metadata": {
            "project_id": project_id,
            "document_id": "doc",
            "chunk_index": idx,
        },
    }


def _make_fake_vector_store_with_n_chunks(n: int) -> MagicMock:
    """Fake vector store that yields n chunks from ``collection.get``."""
    chunks = [_make_chunk(i) for i in range(n)]
    store = MagicMock()
    store.search.return_value = []
    coll = MagicMock()
    coll.get.return_value = {
        "ids": [c["id"] for c in chunks],
        "documents": [c["text"] for c in chunks],
        "metadatas": [c["metadata"] for c in chunks],
    }
    store.collection = coll
    return store


class TestBM25CorpusCap:
    """P4.5+ §4.6 — BM25 corpus is capped at MAX_BM25_CORPUS_SIZE."""

    def test_cap_constant_is_a_positive_int(self) -> None:
        """Sanity check: the cap is a positive integer."""
        assert isinstance(MAX_BM25_CORPUS_SIZE, int)
        assert MAX_BM25_CORPUS_SIZE > 0

    def test_small_corpus_is_not_truncated(self) -> None:
        """A corpus smaller than the cap is fed to BM25 in full."""
        n = 5
        store = _make_fake_vector_store_with_n_chunks(n)
        retriever = HybridRetriever(vector_store=store)
        chunks, bm25 = retriever._fetch_chunks("p1")
        # All chunks returned, BM25 index built.
        assert len(chunks) == n
        assert bm25 is not None
        # And the BM25 index actually has n documents.
        assert len(bm25.doc_freqs) == n

    def test_corpus_exactly_at_cap_is_not_truncated(self) -> None:
        """The cap is inclusive: a corpus of exactly N is not truncated."""
        n = MAX_BM25_CORPUS_SIZE
        store = _make_fake_vector_store_with_n_chunks(n)
        retriever = HybridRetriever(vector_store=store)
        chunks, bm25 = retriever._fetch_chunks("p1")
        assert len(chunks) == n
        assert bm25 is not None
        assert len(bm25.doc_freqs) == n

    def test_oversized_corpus_is_truncated_to_cap(self, caplog: logging.LogRecord) -> None:
        """A corpus larger than the cap is truncated before BM25 indexing.

        We use the metadata_index path so we don't have to materialise
        10 001 fake chunks into the vector-store mock.
        """
        n = MAX_BM25_CORPUS_SIZE + 1
        idx = MagicMock(spec=MetadataIndex)
        idx.get_chunks_by_project.return_value = [_make_chunk(i) for i in range(n)]
        store = MagicMock()
        retriever = HybridRetriever(vector_store=store, metadata_index=idx)
        with caplog.at_level(logging.WARNING, logger="backend.services.dms.hybrid_retriever"):
            chunks, bm25 = retriever._fetch_chunks("p1")
        # Full chunk list is still returned.
        assert len(chunks) == n
        # But BM25 was indexed over only MAX_BM25_CORPUS_SIZE docs.
        assert bm25 is not None
        assert len(bm25.doc_freqs) == MAX_BM25_CORPUS_SIZE
        # And a warning was logged.
        assert any("BM25 corpus truncated" in rec.getMessage() for rec in caplog.records), caplog.records

    def test_oversized_corpus_warning_includes_counts(self) -> None:
        """The truncation warning reports both the original and capped counts."""
        n = MAX_BM25_CORPUS_SIZE + 50
        idx = MagicMock(spec=MetadataIndex)
        idx.get_chunks_by_project.return_value = [_make_chunk(i) for i in range(n)]
        store = MagicMock()
        retriever = HybridRetriever(vector_store=store, metadata_index=idx)
        with patch.object(
            logging.getLogger("backend.services.dms.hybrid_retriever"),
            "warning",
        ) as mock_warn:
            retriever._fetch_chunks("p1")
        assert mock_warn.called
        # The message is a printf-style format string; check the
        # format args (call_args[0][1:]) rather than the literal msg,
        # which would never contain the substituted numbers.
        fmt_args = mock_warn.call_args[0][1:]
        assert len(fmt_args) == 2
        assert fmt_args[0] == n
        assert fmt_args[1] == MAX_BM25_CORPUS_SIZE

    def test_oversized_corpus_does_not_silently_lose_chunks(self) -> None:
        """The full chunk list is still returned so ``chunk_map`` in
        ``retrieve`` stays complete — chunks beyond the cap are merely
        not *indexed* by BM25, not lost.
        """
        n = MAX_BM25_CORPUS_SIZE + 100
        idx = MagicMock(spec=MetadataIndex)
        idx.get_chunks_by_project.return_value = [_make_chunk(i) for i in range(n)]
        store = MagicMock()
        retriever = HybridRetriever(vector_store=store, metadata_index=idx)
        chunks, _ = retriever._fetch_chunks("p1")
        # Every original chunk id is still in the returned list.
        returned_ids = {c["id"] for c in chunks}
        expected_ids = {f"doc_chunk_{i}" for i in range(n)}
        assert returned_ids == expected_ids
