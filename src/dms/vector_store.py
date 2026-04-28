import logging
from pathlib import Path

import chromadb

logger = logging.getLogger(__name__)
MEMORY_DIR = Path("memory")
MEMORY_DIR.mkdir(exist_ok=True)


class DMSVectorStore:
    def __init__(self, config: dict):
        self.client = chromadb.PersistentClient(path=str(MEMORY_DIR / "chroma_db"))
        collection_name = config.get("chroma_collection", "document_chunks")
        self.collection = self.client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"DMS VectorStore geladen: {self.collection.count()} Chunks in '{collection_name}'")

    def add_chunks(self, document_id: str, chunks: list[dict], project_id: str = "") -> None:
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
            metadatas.append({
                "document_id": document_id,
                "project_id": project_id,
                "chunk_index": chunk_index,
                "page": chunk.get("page", 0),
            })
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"Added {len(chunks)} chunks for document {document_id}")

    def search(self, query: str, project_id: str | None = None, k: int = 5) -> list[dict]:
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
                output.append({
                    "text": doc,
                    "metadata": meta,
                    "relevance_score": max(0.0, 1.0 - dist),
                })
            return sorted(output, key=lambda x: x["relevance_score"], reverse=True)
        except Exception as e:
            logger.warning(f"DMS search failed: {e}")
            return []

    def delete_document_chunks(self, document_id: str) -> None:
        self.collection.delete(where={"document_id": {"$eq": document_id}})
        logger.info(f"Deleted chunks for document {document_id}")

    def count(self) -> int:
        return self.collection.count()
