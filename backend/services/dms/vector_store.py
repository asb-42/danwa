"""ChromaDB vector store for document chunks.

Migrated from src/dms/vector_store.py. Now accepts explicit paths.
"""

import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)


class DMSVectorStore:
    """Persistent vector store backed by ChromaDB."""

    def __init__(self, chroma_path: str | Path, collection_name: str = "document_chunks"):
        """Initialise DMSVectorStore."""
        chroma_dir = Path(chroma_path)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(chroma_dir))
        self.collection = self.client.get_or_create_collection(name=collection_name, metadata={"hnsw:space": "cosine"})
        logger.info("DMS VectorStore loaded: %d chunks in '%s'", self.collection.count(), collection_name)

    def add_chunks(self, document_id: str, chunks: list[dict], project_id: str = "") -> None:
        """Add chunks."""
        if not chunks:
            return
        ids = []
        documents = []
        metadatas = []
        for chunk in chunks:
            chunk_index = chunk.get("chunk_index", 0)
            chunk_id = f"{document_id}_chunk_{chunk_index}"
            ids.append(chunk_id)
            documents.append(chunk["text"])
            metadatas.append(
                {
                    "document_id": document_id,
                    "project_id": project_id,
                    "chunk_index": chunk_index,
                    "page": chunk.get("page", 0),
                    "file_name": chunk.get("file_name", ""),
                }
            )
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info("Added %d chunks for document %s", len(chunks), document_id)

    def search(self, query: str, project_id: str | None = None, k: int = 5) -> list[dict]:
        """Search the instance."""
        if self.collection.count() == 0:
            return []
        where = None
        if project_id is not None:
            where = {"project_id": {"$eq": project_id}}
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
            output = []
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                output.append(
                    {
                        "text": doc,
                        "metadata": meta,
                        "relevance_score": max(0.0, 1.0 - dist),
                    }
                )
            return sorted(output, key=lambda x: x["relevance_score"], reverse=True)
        except Exception as e:
            logger.warning("DMS search failed: %s", e)
            return []

    def delete_document_chunks(self, document_id: str) -> None:
        """Delete document chunks."""
        self.collection.delete(where={"document_id": {"$eq": document_id}})
        logger.info("Deleted chunks for document %s", document_id)

    def count(self) -> int:
        """Count the instance."""
        return self.collection.count()
