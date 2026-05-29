"""Hybrid retriever — BM25 + vector search with optional cross-encoder re-ranking.

Migrated from src/dms/hybrid_retriever.py.
"""

import logging
import time
from typing import Any

from rank_bm25 import BM25Okapi

from backend.services.dms.metadata_index import MetadataIndex
from backend.services.dms.vector_store import DMSVectorStore

logger = logging.getLogger(__name__)

# BM25 corpus cache TTL in seconds
_CORPUS_CACHE_TTL = 300  # 5 minutes


class HybridRetriever:
    """Combines BM25 keyword search with vector similarity search using RRF."""

    def __init__(self, vector_store: DMSVectorStore, metadata_index: MetadataIndex | None = None):
        self.vector_store = vector_store
        self.metadata_index = metadata_index
        self.rrf_k = 60  # Standard RRF constant

        # BM25 corpus cache: (project_id, timestamp, chunks)
        self._corpus_cache: tuple[str, float, list[dict]] | None = None

        self.cross_encoder = None
        try:
            from sentence_transformers import CrossEncoder

            self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("CrossEncoder loaded for re-ranking")
        except ImportError:
            logger.warning("sentence_transformers not installed, re-ranking disabled")
        except Exception as e:
            logger.warning("Failed to load CrossEncoder: %s, re-ranking disabled", e)

    def retrieve(self, query: str, project_id: str | None = None, k: int = 5) -> list[dict[str, Any]]:
        chunks = self._fetch_chunks(project_id)
        bm25_results = self._bm25_retrieve(query, chunks, top_n=20)
        vector_results = self.vector_store.search(query, project_id=project_id, k=20)

        rrf_scores = self._rrf_combine(bm25_results, vector_results)
        if not rrf_scores:
            return []

        chunk_map: dict[str, dict] = {chunk["id"]: chunk for chunk in chunks}
        for vr in vector_results:
            meta = vr["metadata"]
            chunk_id = f"{meta['document_id']}_chunk_{meta['chunk_index']}"
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = {
                    "id": chunk_id,
                    "text": vr["text"],
                    "metadata": meta,
                }

        sorted_chunk_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        final_results = []
        for chunk_id, score in sorted_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if chunk:
                final_results.append(
                    {
                        "text": chunk["text"],
                        "metadata": chunk["metadata"],
                        "score": score,
                        "source": "hybrid",
                    }
                )

        if self.cross_encoder and final_results:
            pairs = [(query, res["text"]) for res in final_results]
            try:
                rerank_scores = self.cross_encoder.predict(pairs)
                for res, new_score in zip(final_results, rerank_scores):
                    res["score"] = float(new_score)
                final_results.sort(key=lambda x: x["score"], reverse=True)
            except Exception as e:
                logger.warning("Re-ranking failed: %s", e)

        return final_results[:k]

    def _fetch_chunks(self, project_id: str | None) -> list[dict[str, Any]]:
        """Fetch chunks with TTL-based caching to avoid reloading per query."""
        now = time.time()
        if (
            self._corpus_cache is not None
            and self._corpus_cache[0] == project_id
            and (now - self._corpus_cache[1]) < _CORPUS_CACHE_TTL
        ):
            return self._corpus_cache[2]

        chunks = self._fetch_chunks_uncached(project_id)
        self._corpus_cache = (project_id, now, chunks)
        return chunks

    def _fetch_chunks_uncached(self, project_id: str | None) -> list[dict[str, Any]]:
        if project_id and self.metadata_index:
            return self.metadata_index.get_chunks_by_project(project_id)
        try:
            where = {"project_id": project_id} if project_id else None
            results = self.vector_store.collection.get(where=where, include=["documents", "metadatas", "ids"])
            chunks = []
            for chunk_id, doc_text, meta in zip(
                results.get("ids", []),
                results.get("documents", []),
                results.get("metadatas", []),
            ):
                chunks.append(
                    {
                        "id": chunk_id,
                        "text": doc_text,
                        "metadata": meta,
                    }
                )
            return chunks
        except Exception as e:
            logger.error("Failed to fetch chunks: %s", e)
            return []

    def _bm25_retrieve(self, query: str, chunks: list[dict], top_n: int = 20) -> list[dict[str, Any]]:
        if not chunks:
            return []
        try:
            corpus = [chunk["text"] for chunk in chunks]
            tokenized_corpus = [self._tokenize(text) for text in corpus]
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = self._tokenize(query)
            scores = bm25.get_scores(tokenized_query)
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_n]
            results = []
            for idx in top_indices:
                chunk = chunks[idx]
                results.append(
                    {
                        "id": chunk["id"],
                        "text": chunk["text"],
                        "metadata": chunk["metadata"],
                        "bm25_score": scores[idx],
                    }
                )
            return results
        except Exception as e:
            logger.error("BM25 retrieval failed: %s", e)
            return []

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Tokenize text for BM25: lowercase, split, filter short tokens."""
        return [t.lower() for t in text.split() if len(t) > 1]

    def _rrf_combine(self, bm25_results: list[dict], vector_results: list[dict]) -> dict[str, float]:
        rrf_scores: dict[str, float] = {}
        for rank, result in enumerate(bm25_results, start=1):
            chunk_id = result["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (self.rrf_k + rank)
        for rank, result in enumerate(vector_results, start=1):
            meta = result["metadata"]
            chunk_id = f"{meta['document_id']}_chunk_{meta['chunk_index']}"
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (self.rrf_k + rank)
        return rrf_scores
