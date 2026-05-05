"""DMS service facade — orchestrates all DMS operations.

Migrated from src/dms/dms.py. Project management removed (handled by ProjectStore).
Factory function get_dms_for_project() provides project-scoped instances.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from backend.services.dms.chunker import TextChunker
from backend.services.dms.database import DMSDB
from backend.services.dms.document_processor import DocumentProcessor
from backend.services.dms.hybrid_retriever import HybridRetriever
from backend.services.dms.metadata_index import MetadataIndex
from backend.services.dms.rag_context_formatter import RAGContextFormatter
from backend.services.dms.rag_pipeline import RAGPipeline
from backend.services.dms.vector_store import DMSVectorStore

logger = logging.getLogger(__name__)

# Cache DMS instances per project directory
_dms_cache: dict[str, "DMS"] = {}


class DMS:
    """Document Management System facade.

    Orchestrates document processing, chunking, vector storage, and RAG retrieval.
    Each instance is scoped to a specific project directory.
    """

    def __init__(self, db_path: str | Path, chroma_path: str | Path):
        self.db_path = str(db_path)
        self.chroma_path = str(chroma_path)

        self.db = DMSDB(db_path=self.db_path)

        self.document_processor = DocumentProcessor()
        self.text_chunker = TextChunker()

        self.vector_store = DMSVectorStore(chroma_path=self.chroma_path)
        self.metadata_index = MetadataIndex(self.vector_store)

        self.rag_pipeline = RAGPipeline(
            document_processor=self.document_processor,
            text_chunker=self.text_chunker,
            vector_store=self.vector_store,
            db=self.db,
        )
        self.hybrid_retriever = HybridRetriever(
            vector_store=self.vector_store,
            metadata_index=self.metadata_index,
        )
        self.rag_formatter = RAGContextFormatter()
        self._manual_rag_docs: set[str] = set()

        logger.info("DMS initialized (db: %s, chroma: %s)", self.db_path, self.chroma_path)

    # --- Document operations ---

    def upload_document(
        self,
        project_id: str,
        file_path: str,
        original_filename: str = "",
    ) -> str:
        """Upload a document: create DB entry, process file, index chunks.

        Args:
            project_id: The project to upload to.
            file_path: Path to the temporary uploaded file.
            original_filename: The original filename from the user's upload.
        """
        file_p = Path(file_path)
        if not file_p.exists():
            logger.error("File not found: %s", file_path)
            return ""

        if not original_filename:
            original_filename = file_p.name

        file_size = file_p.stat().st_size
        file_type = file_p.suffix.lstrip(".")

        try:
            doc = self.db.add_document(
                project_id=project_id,
                filename=original_filename,
                file_path=str(file_p.resolve()),
                file_type=file_type,
                file_size=file_size,
                original_filename=original_filename,
            )
            doc_id = doc["id"]
            logger.info("Created document entry %s for project %s", doc_id, project_id)
        except Exception as e:
            logger.error("Failed to create document entry for %s: %s", file_path, e)
            return ""

        try:
            loop = asyncio.get_running_loop()
            # We're inside an async context (FastAPI) — run in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.rag_pipeline.process_file(doc_id, file_path))
                future.result(timeout=120)
        except RuntimeError:
            # No running loop — safe to call asyncio.run directly
            try:
                asyncio.run(self.rag_pipeline.process_file(doc_id, file_path))
            except Exception as e:
                logger.error("Failed to process document %s: %s", doc_id, e)
        except Exception as e:
            logger.error("Failed to process document %s: %s", doc_id, e)

        return doc_id

    def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks from DB and vector store."""
        try:
            self.db.delete_document(document_id)
            self.vector_store.delete_document_chunks(document_id)
            logger.info("Deleted document %s", document_id)
            return True
        except Exception as e:
            logger.error("Failed to delete document %s: %s", document_id, e)
            return False

    def list_documents(self, project_id: str) -> list[dict[str, Any]]:
        """List all documents for a project, enriched with RAG status."""
        try:
            docs = self.db.list_documents(project_id)
            rag_doc_ids = set(self._manual_rag_docs)
            for doc in docs:
                doc["in_rag"] = doc["id"] in rag_doc_ids
            return docs
        except Exception as e:
            logger.error("Failed to list documents (project %s): %s", project_id, e)
            return []

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        """Get a single document by ID."""
        return self.db.get_document(document_id)

    def get_document_content(self, document_id: str) -> dict[str, Any] | None:
        """Get document metadata and its text chunks for viewing."""
        doc = self.db.get_document(document_id)
        if not doc:
            return None
        chunks = self.db.list_chunks(document_id)
        text = "\n\n".join(c.get("text", "") for c in chunks)
        return {
            **doc,
            "in_rag": document_id in self._manual_rag_docs,
            "text_content": text,
            "chunk_count": len(chunks),
        }

    # --- RAG operations ---

    def get_rag_context(self, query: str, project_id: str | None = None, k: int = 5) -> list[dict[str, Any]]:
        """Search RAG context using hybrid retrieval."""
        try:
            return self.hybrid_retriever.retrieve(query, project_id=project_id, k=k)
        except Exception as e:
            logger.error("Failed to get RAG context for query '%s': %s", query, e)
            return []

    def add_to_rag_context(self, document_id: str) -> bool:
        """Add a document to manual RAG context."""
        try:
            if document_id in self._manual_rag_docs:
                logger.info("Document %s already in manual RAG context", document_id)
                return False
            self._manual_rag_docs.add(document_id)
            logger.info("Added document %s to manual RAG context", document_id)
            return True
        except Exception as e:
            logger.error("Failed to add document %s to manual RAG context: %s", document_id, e)
            return False

    def remove_from_rag_context(self, document_id: str) -> bool:
        """Remove a document from manual RAG context."""
        try:
            if document_id not in self._manual_rag_docs:
                logger.info("Document %s not in manual RAG context", document_id)
                return False
            self._manual_rag_docs.remove(document_id)
            logger.info("Removed document %s from manual RAG context", document_id)
            return True
        except Exception as e:
            logger.error("Failed to remove document %s from manual RAG context: %s", document_id, e)
            return False

    def list_manual_rag_documents(self) -> list[str]:
        """List document IDs in manual RAG context."""
        try:
            return list(self._manual_rag_docs)
        except Exception as e:
            logger.error("Failed to list manual RAG documents: %s", e)
            return []

    def get_manual_rag_context(self, k: int = 5) -> list[dict[str, Any]]:
        """Get chunks from manually selected RAG documents."""
        try:
            all_chunks = []
            for doc_id in self._manual_rag_docs:
                chunks = self.metadata_index.get_chunks_by_document(doc_id)
                all_chunks.extend(chunks)
            return all_chunks[:k]
        except Exception as e:
            logger.error("Failed to get manual RAG context: %s", e)
            return []

    def auto_retrieve_for_topic(
        self, topic: str, project_id: str | None = None, k: int = 5
    ) -> list[dict[str, Any]]:
        """Auto-retrieve relevant chunks for a topic."""
        try:
            raw_results = self.get_rag_context(topic, project_id, k)
            formatted_results = []
            for chunk in raw_results:
                meta = chunk.get("metadata", {})
                formatted_results.append({
                    "text": chunk.get("text", ""),
                    "source": meta.get("file_name", "unknown"),
                    "chunk_index": meta.get("chunk_index", -1),
                    "project_id": meta.get("project_id", project_id or "unknown"),
                })
            logger.info("Auto-retrieved %d chunks for topic '%s'", len(formatted_results), topic)
            return formatted_results
        except Exception as e:
            logger.error("Failed to auto-retrieve for topic '%s': %s", topic, e)
            return []

    def format_rag_context(
        self, chunks: list[dict[str, Any]], max_chars: int | None = None
    ) -> str:
        """Format RAG chunks into a context string for LLM prompts."""
        return self.rag_formatter.format(chunks, max_chars=max_chars)


def get_dms_for_project(project_id: str, project_store: Any = None) -> DMS:
    """Get or create a DMS instance for a specific project.

    Factory function used by both the DMS router and the debate router.
    """
    if project_id in _dms_cache:
        return _dms_cache[project_id]

    if project_store is None:
        from backend.api.deps import get_project_store
        project_store = get_project_store()

    project = project_store.get(project_id)
    if not project:
        raise ValueError(f"Project not found: {project_id}")

    project_dir = project_store.get_project_dir(project_id)
    dms_dir = project_dir / "dms"
    dms_dir.mkdir(parents=True, exist_ok=True)

    dms = DMS(db_path=str(dms_dir / "dms.db"), chroma_path=str(dms_dir / "chroma_db"))

    # Ensure the project exists in the DMS database (required for FK constraint)
    if not dms.db.get_project(project_id):
        from datetime import datetime
        dms.db.conn.execute(
            "INSERT OR IGNORE INTO projects (id, name, description, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
            (project_id, project.name, "", datetime.now().isoformat(), ""),
        )
        dms.db.conn.commit()

    _dms_cache[project_id] = dms
    return dms
