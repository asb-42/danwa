"""RAG pipeline — document processing, chunking, and vector store indexing.

Migrated from src/dms/rag_pipeline.py.
"""

import logging
from typing import Any

from backend.services.dms.chunker import TextChunker
from backend.services.dms.database import DMSDB
from backend.services.dms.document_processor import DocumentProcessor
from backend.services.dms.vector_store import DMSVectorStore

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Processes documents into chunks and indexes them in the vector store."""

    def __init__(
        self,
        document_processor: DocumentProcessor,
        text_chunker: TextChunker,
        vector_store: DMSVectorStore,
        db: DMSDB,
    ):
        """Initialise RAGPipeline."""
        self.document_processor = document_processor
        self.text_chunker = text_chunker
        self.vector_store = vector_store
        self.db = db

    def process_document(self, doc_id: str, text: str) -> list[str]:
        """Process text into chunks and index in vector store."""
        logger.info("Processing document %s", doc_id)
        if not text:
            logger.warning("No text provided for document %s", doc_id)
            return []

        doc = self.db.get_document(doc_id)
        if not doc:
            logger.error("Document %s not found in database", doc_id)
            return []

        try:
            chunks = self.text_chunker.chunk(text)
        except Exception as e:
            logger.error("Chunking failed for document %s: %s", doc_id, e)
            return []

        if not chunks:
            logger.warning("No chunks generated for document %s", doc_id)
            return []

        chunk_dicts = [{"text": chunk_text, "chunk_index": idx, "page": 0, "file_name": doc["filename"]} for idx, chunk_text in enumerate(chunks)]

        try:
            self.vector_store.add_chunks(
                document_id=doc_id,
                chunks=chunk_dicts,
                project_id=doc["project_id"],
            )
        except Exception as e:
            logger.error("Failed to add chunks to vector store for document %s: %s", doc_id, e)
            return []

        for idx, chunk_text in enumerate(chunks):
            try:
                self.db.add_chunk(
                    document_id=doc_id,
                    chunk_index=idx,
                    text=chunk_text,
                    page=0,
                    metadata_json=str(
                        {
                            "file_name": doc["filename"],
                            "upload_date": doc["uploaded_at"],
                            "project_id": doc["project_id"],
                        }
                    ),
                )
            except Exception as e:
                logger.error("Failed to add chunk %d to DB for document %s: %s", idx, doc_id, e)

        chunk_ids = [f"{doc_id}_chunk_{idx}" for idx in range(len(chunks))]
        logger.info("Processed document %s, generated %d chunks", doc_id, len(chunk_ids))
        return chunk_ids

    async def process_file(self, doc_id: str, file_path: str) -> dict[str, Any]:
        """Process a file: extract text, then chunk and index.

        Returns a dict with keys:
          - chunk_ids (list[str])
          - ocr_used (bool)
          - ocr_engine (str | None)
          - char_count (int)
          - word_count (int)

        Raises:
            ValueError: If the file cannot be processed (e.g. image without OCR).
        """
        logger.info("Processing file %s for document %s", file_path, doc_id)
        proc_result = await self.document_processor.process_file(file_path)
        text = proc_result.get("text", "")
        meta = proc_result.get("metadata", {})
        ocr_used = proc_result.get("ocr_used", False)

        if not text:
            logger.warning("No text extracted from file %s", file_path)
            return {
                "chunk_ids": [],
                "ocr_used": ocr_used,
                "ocr_engine": meta.get("ocr_engine"),
                "char_count": 0,
                "word_count": 0,
            }

        chunk_ids = self.process_document(doc_id, text)
        return {
            "chunk_ids": chunk_ids,
            "ocr_used": ocr_used,
            "ocr_engine": meta.get("ocr_engine"),
            "char_count": meta.get("char_count", len(text)),
            "word_count": meta.get("word_count", len(text.split())),
        }
