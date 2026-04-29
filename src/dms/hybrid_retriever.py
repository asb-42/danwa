import logging
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi

from .vector_store import DMSVectorStore
from .metadata_index import MetadataIndex

logger = logging.getLogger(__name__)


class HybridRetriever:
    def __init__(self, vector_store: DMSVectorStore, metadata_index: Optional[MetadataIndex] = None):
        self.vector_store = vector_store
        self.metadata_index = metadata_index
        self.rrf_k = 60  # Standard RRF constant

        self.cross_encoder = None
        try:
            from sentence_transformers import CrossEncoder
            self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            logger.info("CrossEncoder loaded for re-ranking")
        except ImportError:
            logger.warning("sentence_transformers not installed, re-ranking disabled")
        except Exception as e:
            logger.warning(f"Failed to load CrossEncoder: {e}, re-ranking disabled")

    def retrieve(self, query: str, project_id: Optional[str] = None, k: int = 5) -> List[Dict]:
        chunks = self._fetch_chunks(project_id)
        bm25_results = self._bm25_retrieve(query, chunks, top_n=20)
        vector_results = self.vector_store.search(query, project_id=project_id, k=20)

        rrf_scores = self._rrf_combine(bm25_results, vector_results)
        if not rrf_scores:
            return []

        chunk_map = {chunk["id"]: chunk for chunk in chunks}
        for vr in vector_results:
            meta = vr["metadata"]
            chunk_id = f"{meta['document_id']}_chunk_{meta['chunk_index']}"
            if chunk_id not in chunk_map:
                chunk_map[chunk_id] = {
                    "id": chunk_id,
                    "text": vr["text"],
                    "metadata": meta
                }

        sorted_chunk_ids = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        final_results = []
        for chunk_id, score in sorted_chunk_ids:
            chunk = chunk_map.get(chunk_id)
            if chunk:
                final_results.append({
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "score": score,
                    "source": "hybrid"
                })

        if self.cross_encoder and final_results:
            pairs = [(query, res["text"]) for res in final_results]
            try:
                rerank_scores = self.cross_encoder.predict(pairs)
                for res, new_score in zip(final_results, rerank_scores):
                    res["score"] = float(new_score)
                final_results.sort(key=lambda x: x["score"], reverse=True)
            except Exception as e:
                logger.warning(f"Re-ranking failed: {e}")

        return final_results[:k]

    def _fetch_chunks(self, project_id: Optional[str]) -> List[Dict]:
        if project_id and self.metadata_index:
            return self.metadata_index.get_chunks_by_project(project_id)
        try:
            where = {"project_id": project_id} if project_id else None
            results = self.vector_store.collection.get(
                where=where, include=["documents", "metadatas", "ids"]
            )
            chunks = []
            for chunk_id, doc_text, meta in zip(
                results.get("ids", []),
                results.get("documents", []),
                results.get("metadatas", [])
            ):
                chunks.append({
                    "id": chunk_id,
                    "text": doc_text,
                    "metadata": meta
                })
            return chunks
        except Exception as e:
            logger.error(f"Failed to fetch chunks: {e}")
            return []

    def _bm25_retrieve(self, query: str, chunks: List[Dict], top_n: int = 20) -> List[Dict]:
        if not chunks:
            return []
        try:
            corpus = [chunk["text"] for chunk in chunks]
            tokenized_corpus = [text.split() for text in corpus]
            bm25 = BM25Okapi(tokenized_corpus)
            tokenized_query = query.split()
            scores = bm25.get_scores(tokenized_query)
            top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_n]
            results = []
            for idx in top_indices:
                chunk = chunks[idx]
                results.append({
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "metadata": chunk["metadata"],
                    "bm25_score": scores[idx]
                })
            return results
        except Exception as e:
            logger.error(f"BM25 retrieval failed: {e}")
            return []

    def _rrf_combine(self, bm25_results: List[Dict], vector_results: List[Dict]) -> Dict[str, float]:
        rrf_scores = {}
        for rank, result in enumerate(bm25_results, start=1):
            chunk_id = result["id"]
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (self.rrf_k + rank)
        for rank, result in enumerate(vector_results, start=1):
            meta = result["metadata"]
            chunk_id = f"{meta['document_id']}_chunk_{meta['chunk_index']}"
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (self.rrf_k + rank)
        return rrf_scores
