"""Metadata index — ChromaDB metadata queries for document chunks.

Migrated from src/dms/metadata_index.py.
"""

import logging
from typing import Any

from backend.services.dms.vector_store import DMSVectorStore

logger = logging.getLogger(__name__)


class MetadataIndex:
    """Query chunks by project, document, or date range via ChromaDB metadata."""

    def __init__(self, chroma_store: DMSVectorStore):
        self.chroma_store = chroma_store

    def get_chunks_by_project(self, project_id: str) -> list[dict[str, Any]]:
        try:
            results = self.chroma_store.collection.get(
                where={"project_id": project_id},
                include=["metadatas", "documents", "ids"],
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error("Failed to fetch chunks for project %s: %s", project_id, e)
            return []

    def get_chunks_by_document(self, document_id: str) -> list[dict[str, Any]]:
        try:
            results = self.chroma_store.collection.get(
                where={"document_id": document_id},
                include=["metadatas", "documents", "ids"],
                limit=10_000,
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error("Failed to fetch chunks for document %s: %s", document_id, e)
            return []

    def get_chunks_by_date_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        try:
            results = self.chroma_store.collection.get(
                where={"upload_date": {"$gte": start_date, "$lte": end_date}},
                include=["metadatas", "documents", "ids"],
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error("Failed to fetch chunks between %s and %s: %s", start_date, end_date, e)
            return []

    def _process_chunks(self, results: dict) -> list[dict[str, Any]]:
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
                    "metadata": {
                        "project_id": meta.get("project_id"),
                        "document_id": meta.get("document_id"),
                        "chunk_index": meta.get("chunk_index"),
                        "file_name": meta.get("file_name"),
                        "upload_date": meta.get("upload_date"),
                    },
                }
            )
        chunks.sort(key=lambda c: (c["metadata"].get("chunk_index") is None, c["metadata"].get("chunk_index", 0)))
        return chunks
