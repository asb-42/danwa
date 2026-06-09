"""DMS service facade — orchestrates all DMS operations.

Migrated from src/dms/dms.py. Project management removed (handled by ProjectStore).
Factory function get_dms_for_project() provides project-scoped instances.
"""

import asyncio
import logging
import threading
import uuid
from datetime import datetime
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
_dms_cache_lock = threading.Lock()


class DMS:
    """Document Management System facade.

    Orchestrates document processing, chunking, vector storage, and RAG retrieval.
    Each instance is scoped to a specific project directory.
    """

    def __init__(
        self,
        db_path: str | Path,
        chroma_path: str | Path,
        config: dict | None = None,
        project_id: str | None = None,
    ):
        """Initialise DMS."""
        self.db_path = str(db_path)
        self.chroma_path = str(chroma_path)
        self.config = config or {}
        self._project_id = project_id

        self.db = DMSDB(db_path=self.db_path)

        logger.info("DMS config: %s", self.config)
        self.document_processor = DocumentProcessor(config=self.config)
        self.text_chunker = TextChunker()

        self.vector_store = DMSVectorStore(chroma_path=self.chroma_path)
        self.metadata_index = MetadataIndex(self.vector_store, project_id=project_id)

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

        # Load persisted RAG selections from DB
        self._manual_rag_docs: set[str] = set()
        if project_id:
            try:
                rows = self.db.list_rag_context(project_id)
                self._manual_rag_docs = {r["document_id"] for r in rows}
                logger.info("Loaded %d persisted RAG docs for project %s", len(self._manual_rag_docs), project_id)
            except Exception as e:
                logger.warning("Failed to load RAG context from DB: %s", e)

        logger.info("DMS initialized (db: %s, chroma: %s)", self.db_path, self.chroma_path)

    # --- Document operations ---

    def add_document(
        self,
        file_path: str,
        filename: str = "",
    ) -> dict[str, Any]:
        """Thin alias of :meth:`upload_document` used by tenant/case routers.

        Resolves ``project_id`` from ``self._project_id`` and forwards to
        the canonical upload path. Raises ``ValueError`` if the DMS has
        no project binding (which would mean the upload is unscoped and
        therefore unsafe in a multi-tenant deployment).
        """
        if not self._project_id:
            raise ValueError("DMS instance is not bound to a project — cannot accept uploads")
        if not filename:
            filename = Path(file_path).name
        return self.upload_document(
            project_id=self._project_id,
            file_path=file_path,
            original_filename=filename,
        )

    def upload_document(
        self,
        project_id: str,
        file_path: str,
        original_filename: str = "",
    ) -> dict[str, Any]:
        """Upload a document: create DB entry, process file, index chunks.

        Args:
            project_id: The project to upload to.
            file_path: Path to the temporary uploaded file.
            original_filename: The original filename from the user's upload.

        Returns:
            Dict with keys: ``doc_id``, ``error`` (str or None), ``chunk_count``.
        """
        file_p = Path(file_path)
        if not file_p.exists():
            logger.error("File not found: %s", file_path)
            return {"doc_id": "", "error": f"File not found: {file_path}", "chunk_count": 0}

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
            return {"doc_id": "", "error": f"Database error: {e}", "chunk_count": 0}

        # Process file (extract text, chunk, index)
        proc_result: dict[str, Any] = {}
        processing_error: str | None = None
        try:
            asyncio.get_running_loop()
            # We're inside an async context (FastAPI) — run in a thread
            import concurrent.futures

            try:
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.rag_pipeline.process_file(doc_id, file_path))
                    proc_result = future.result(timeout=300)
            except concurrent.futures.TimeoutError:
                processing_error = "Document processing timed out (5 minutes). OCR model download may be in progress."
                logger.error("Timeout processing document %s", doc_id)
            except concurrent.futures.BrokenExecutor:
                processing_error = "Processing failed: worker process crashed"
                logger.error("BrokenProcessPool for document %s", doc_id)
            except ValueError as e:
                processing_error = str(e)
                logger.warning("Processing error for document %s: %s", doc_id, e)
            except Exception as e:
                processing_error = f"Processing failed: {e}"
                logger.error("Failed to process document %s: %s", doc_id, e)
        except RuntimeError:
            # No running loop — safe to call asyncio.run directly
            try:
                proc_result = asyncio.run(self.rag_pipeline.process_file(doc_id, file_path))
            except ValueError as e:
                processing_error = str(e)
                logger.warning("Processing error for document %s: %s", doc_id, e)
            except Exception as e:
                processing_error = f"Processing failed: {e}"
                logger.error("Failed to process document %s: %s", doc_id, e)

        return {
            "doc_id": doc_id,
            "error": processing_error,
            "chunk_count": len(proc_result.get("chunk_ids", [])),
            "ocr_used": proc_result.get("ocr_used", False),
            "ocr_engine": proc_result.get("ocr_engine"),
            "char_count": proc_result.get("char_count", 0),
            "word_count": proc_result.get("word_count", 0),
        }

    def move_document_to(self, document_id: str, target_dms: "DMS", target_project_id: str) -> bool:
        """Move a document to another project's DMS.

        Reads the document and its chunks from this DMS, inserts them into
        the target DMS (with a new document ID), re-indexes in the target
        vector store, then deletes from this DMS.

        Returns True on success. If the target insert fails, the source
        document is left unchanged. If the source delete fails after a
        successful target insert, a warning is logged (document exists in
        both projects).
        """
        doc = self.db.get_document(document_id)
        if not doc:
            logger.error("Document %s not found in source DMS", document_id)
            return False

        chunks = self.db.list_chunks(document_id)
        chunk_texts = [c["text"] for c in chunks]

        # 1. Insert into target DMS DB (new doc_id is auto-generated by add_document)
        try:
            new_doc = target_dms.db.add_document(
                project_id=target_project_id,
                filename=doc.get("filename", "unknown"),
                file_path="",
                file_type=doc.get("file_type", ""),
                file_size=doc.get("file_size", 0),
                original_filename=doc.get("original_filename", ""),
                page_count=doc.get("page_count", 0),
                word_count=doc.get("word_count", 0),
                char_count=doc.get("char_count", 0),
                ocr_used=bool(doc.get("ocr_used", 0)),
            )
            new_doc_id = new_doc["id"]
            logger.info("Created document entry %s in target project %s", new_doc_id, target_project_id)
        except Exception as e:
            logger.error("Failed to create document in target DMS: %s", e)
            return False

        # 2. Re-index chunks in target DMS
        try:
            if chunk_texts:
                chunk_dicts = [{"text": t, "chunk_index": i, "page": 0} for i, t in enumerate(chunk_texts)]
                target_dms.vector_store.add_chunks(
                    document_id=new_doc_id,
                    chunks=chunk_dicts,
                    project_id=target_project_id,
                )
                metadata = str(
                    {
                        "file_name": doc["filename"],
                        "upload_date": doc.get("uploaded_at", ""),
                        "project_id": target_project_id,
                    }
                )
                target_dms.db.conn.executemany(
                    """INSERT INTO document_chunks
                    (id, document_id, chunk_index, text, embedding_id, page, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [(str(uuid.uuid4())[:8], new_doc_id, i, ct, "", 0, metadata) for i, ct in enumerate(chunk_texts)],
                )
                target_dms.db.conn.commit()
                logger.info("Indexed %d chunks for document %s in target project", len(chunk_texts), new_doc_id)
        except Exception as e:
            logger.error("Failed to index chunks in target DMS, cleaning up target document %s: %s", new_doc_id, e)
            target_dms.delete_document(new_doc_id)
            return False

        # 3. Delete from source DMS
        try:
            self.delete_document(document_id)
        except Exception as e:
            logger.warning(
                "Document %s copied to target as %s but source deletion failed: %s. Document exists in both projects.",
                document_id,
                new_doc_id,
                e,
            )
            return True

        logger.info(
            "Moved document %s (%s) from project %s to project %s as %s",
            document_id,
            doc.get("filename"),
            doc["project_id"],
            target_project_id,
            new_doc_id,
        )
        return True

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

    def update_document_text(self, document_id: str, text: str) -> dict[str, Any] | None:
        """Replace document text: re-chunks and re-indexes. Returns updated content or None if not found."""
        doc = self.db.get_document(document_id)
        if not doc:
            return None

        # Delete old chunks from DB and vector store
        self.db.delete_document_chunks(document_id)
        self.vector_store.delete_document_chunks(document_id)

        # Re-chunk and re-index
        chunk_ids = self.rag_pipeline.process_document(document_id, text)

        # Update timestamps
        now = datetime.now().isoformat()
        self.db.update_document_metadata(
            document_id,
            updated_at=now,
            word_count=len(text.split()),
            char_count=len(text),
        )

        return {
            "document_id": document_id,
            "chunk_count": len(chunk_ids),
            "char_count": len(text),
            "word_count": len(text.split()),
            "updated_at": now,
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
        """Add a document to manual RAG context.

        Returns False (and does NOT add) if the document does not belong to
        the active project — prevents cross-tenant injection of foreign
        document_ids into the RAG selection set.
        """
        try:
            if not self._document_belongs_to_project(document_id):
                logger.warning(
                    "Refused to add foreign document %s to manual RAG context of project %s",
                    document_id,
                    self._project_id,
                )
                return False
            if document_id in self._manual_rag_docs:
                logger.info("Document %s already in manual RAG context", document_id)
                return False
            self._manual_rag_docs.add(document_id)
            if self._project_id:
                self.db.add_rag_context(self._project_id, document_id)
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
            if self._project_id:
                self.db.remove_rag_context(self._project_id, document_id)
            logger.info("Removed document %s from manual RAG context", document_id)
            return True
        except Exception as e:
            logger.error("Failed to remove document %s from manual RAG context: %s", document_id, e)
            return False

    def _document_belongs_to_project(self, document_id: str) -> bool:
        """Return True if ``document_id`` is owned by the active project.

        Used to validate manual RAG selection and any other path that
        accepts a ``document_id`` from the caller. The check is
        intentionally cheap: a single primary-key lookup against the
        per-project SQLite ``documents`` table. If the project is not
        known (no ``_project_id``), ownership cannot be verified and the
        call is rejected.
        """
        if not self._project_id:
            logger.warning(
                "Cannot verify document ownership — DMS has no project_id (doc %s)",
                document_id,
            )
            return False
        if not self.db.get_document(document_id):
            return False
        return self.db.get_document(document_id).get("project_id") == self._project_id

    def list_manual_rag_documents(self) -> list[str]:
        """List document IDs in manual RAG context."""
        try:
            return list(self._manual_rag_docs)
        except Exception as e:
            logger.error("Failed to list manual RAG documents: %s", e)
            return []

    def get_manual_rag_context(self, k: int = 5) -> list[dict[str, Any]]:
        """Get chunks from manually selected RAG documents.

        Uses round-robin sampling across documents to avoid biasing
        toward the first document when multiple are selected.

        Multi-tenant safety: the per-document lookup is constrained to
        the active project via ``MetadataIndex.get_chunks_by_document``;
        a document_id that was smuggled in from another project returns
        no chunks and is silently skipped (its presence in
        ``_manual_rag_docs`` was already rejected by
        ``add_to_rag_context``).
        """
        try:
            doc_chunks: list[list[dict]] = []
            for doc_id in self._manual_rag_docs:
                chunks = self.metadata_index.get_chunks_by_document(doc_id, project_id=self._project_id)
                if chunks:
                    doc_chunks.append(chunks)

            if not doc_chunks:
                return []

            # Round-robin: take one chunk from each document in turn
            result: list[dict] = []
            max_len = max(len(c) for c in doc_chunks)
            for i in range(max_len):
                for dc in doc_chunks:
                    if i < len(dc) and len(result) < k:
                        result.append(dc[i])
                if len(result) >= k:
                    break

            return result
        except Exception as e:
            logger.error("Failed to get manual RAG context: %s", e)
            return []

    def auto_retrieve_for_topic(self, topic: str, project_id: str | None = None, k: int = 5) -> list[dict[str, Any]]:
        """Auto-retrieve relevant chunks for a topic."""
        try:
            raw_results = self.get_rag_context(topic, project_id, k)
            formatted_results = []
            for chunk in raw_results:
                meta = chunk.get("metadata", {})
                formatted_results.append(
                    {
                        "text": chunk.get("text", ""),
                        "metadata": {
                            "file_name": meta.get("file_name", "Unknown"),
                            "chunk_index": meta.get("chunk_index", -1),
                            "project_id": meta.get("project_id", project_id or "unknown"),
                        },
                    }
                )
            logger.info("Auto-retrieved %d chunks for topic '%s'", len(formatted_results), topic)
            return formatted_results
        except Exception as e:
            logger.error("Failed to auto-retrieve for topic '%s': %s", topic, e)
            return []

    def format_rag_context(self, chunks: list[dict[str, Any]], max_chars: int | None = None) -> str:
        """Format RAG chunks into a context string for LLM prompts."""
        return self.rag_formatter.format(chunks, max_chars=max_chars)


def get_dms_for_project(project_id: str, project_store: Any = None) -> DMS:
    """Get or create a DMS instance for a specific project.

    Factory function used by both the DMS router and the debate router.
    Loads DMS configuration (including OCR settings) and passes it through
    to ``DocumentProcessor``.

    The entire check-then-create-then-insert sequence is protected by
    ``_dms_cache_lock`` to prevent duplicate instances under concurrent access.

    The ``project_store`` parameter is kept for backward compatibility but
    is no longer required. Internally ``get_case_dir()`` is used for
    directory resolution.
    """
    with _dms_cache_lock:
        if project_id in _dms_cache:
            return _dms_cache[project_id]

        from backend.api.deps import get_case_dir, get_project_store

        project = get_project_store().get(project_id)
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        project_dir = get_case_dir(project_id)
        dms_dir = project_dir / "dms"
        dms_dir.mkdir(parents=True, exist_ok=True)

        from backend.services.dms.config import load_dms_config

        try:
            dms_config = load_dms_config()
        except Exception:
            dms_config = {}

        dms = DMS(
            db_path=str(dms_dir / "dms.db"),
            chroma_path=str(dms_dir / "chroma_db"),
            config=dms_config,
            project_id=project_id,
        )

        if not dms.db.get_project(project_id):
            project_name = project.name if project else project_id
            dms.db.conn.execute(
                "INSERT OR IGNORE INTO projects (id, name, description, created_at, metadata_json) VALUES (?, ?, ?, ?, ?)",
                (project_id, project_name, "", datetime.now().isoformat(), ""),
            )
            dms.db.conn.commit()

        _dms_cache[project_id] = dms
        return dms
