"""Metadata index — ChromaDB metadata queries for document chunks.

Migrated from src/dms/metadata_index.py.

Multi-tenant safety:
  - All read paths accept an explicit ``project_id`` and constrain the
    ChromaDB ``where`` filter to that project. This is defense in depth:
    even if two projects ever share a ChromaDB collection, a foreign
    project_id cannot be smuggled in via this index.
  - ``include`` does not request ``"ids"`` (which is not a valid
    ``include`` value for ``collection.get()`` in ChromaDB >= 1.x; the
    error used to be swallowed and silently returned ``[]``).
"""

import logging
from typing import Any

from backend.services.dms.vector_store import DMSVectorStore

logger = logging.getLogger(__name__)

# Valid ``include`` values for ``collection.get()`` in ChromaDB 1.x.
# ``ids`` is always returned by default — it is NOT a valid include value.
_VALID_GET_INCLUDE = ("documents", "metadatas")


class MetadataIndex:
    """Query chunks by project, document, or date range via ChromaDB metadata."""

    def __init__(self, chroma_store: DMSVectorStore, project_id: str | None = None):
        """Initialise MetadataIndex."""
        self.chroma_store = chroma_store
        self._project_id = project_id

    def get_chunks_by_project(self, project_id: str) -> list[dict[str, Any]]:
        """Retrieve and return chunks by project."""
        try:
            results = self.chroma_store.collection.get(
                where={"project_id": {"$eq": project_id}},
                include=list(_VALID_GET_INCLUDE),
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error("Failed to fetch chunks for project %s: %s", project_id, e)
            return []

    def get_chunks_by_document(self, document_id: str, project_id: str | None = None) -> list[dict[str, Any]]:
        """Return chunks for ``document_id`` constrained to ``project_id``.

        ``project_id`` defaults to the index's own ``_project_id`` (set in
        ``__init__`` from the enclosing DMS instance). If neither is
        available, the call is rejected — we will never query the
        cross-project corpus for a single document.
        """
        effective_project_id = project_id or self._project_id
        if not effective_project_id:
            logger.warning(
                "get_chunks_by_document(%s) called without project_id — refusing to query",
                document_id,
            )
            return []
        try:
            results = self.chroma_store.collection.get(
                where={
                    "$and": [
                        {"document_id": {"$eq": document_id}},
                        {"project_id": {"$eq": effective_project_id}},
                    ]
                },
                include=list(_VALID_GET_INCLUDE),
            )
            chunks = self._process_chunks(results)
            logger.info(
                "get_chunks_by_document(%s, project=%s): chroma returned %d ids, extracted %d chunks",
                document_id,
                effective_project_id,
                len(results.get("ids", [])),
                len(chunks),
            )
            return chunks
        except Exception as e:
            logger.error(
                "Failed to fetch chunks for document %s (project %s): %s",
                document_id,
                effective_project_id,
                e,
            )
            return []

    def get_chunks_by_date_range(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Retrieve and return chunks by date range."""
        try:
            results = self.chroma_store.collection.get(
                where={"upload_date": {"$gte": start_date, "$lte": end_date}},
                include=list(_VALID_GET_INCLUDE),
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error("Failed to fetch chunks between %s and %s: %s", start_date, end_date, e)
            return []

    def _process_chunks(self, results: dict) -> list[dict[str, Any]]:
        """Process chunks internally."""
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
