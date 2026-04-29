import logging
from typing import List
from src.dms.document_processor import DocumentProcessor
from src.dms.chunker import TextChunker
from src.dms.vector_store import DMSVectorStore
from src.dms.database import DMSDB

logger = logging.getLogger(__name__)


class RAGPipeline:
    def __init__(
        self,
        document_processor: DocumentProcessor,
        text_chunker: TextChunker,
        vector_store: DMSVectorStore,
        db: DMSDB,
    ):
        self.document_processor = document_processor
        self.text_chunker = text_chunker
        self.vector_store = vector_store
        self.db = db

    def process_document(self, doc_id: str, text: str) -> List[str]:
        logger.info(f"Processing document {doc_id}")
        if not text:
            logger.warning(f"No text provided for document {doc_id}")
            return []

        doc = self.db.get_document(doc_id)
        if not doc:
            logger.error(f"Document {doc_id} not found in database")
            return []

        try:
            chunks = self.text_chunker.chunk(text)
        except Exception as e:
            logger.error(f"Chunking failed for document {doc_id}: {e}")
            return []

        if not chunks:
            logger.warning(f"No chunks generated for document {doc_id}")
            return []

        chunk_dicts = [
            {"text": chunk_text, "chunk_index": idx, "page": 0}
            for idx, chunk_text in enumerate(chunks)
        ]

        try:
            self.vector_store.add_chunks(
                document_id=doc_id,
                chunks=chunk_dicts,
                project_id=doc["project_id"],
            )
        except Exception as e:
            logger.error(f"Failed to add chunks to vector store for document {doc_id}: {e}")
            return []

        for idx, chunk_text in enumerate(chunks):
            try:
                self.db.add_chunk(
                    document_id=doc_id,
                    chunk_index=idx,
                    text=chunk_text,
                    page=0,
                    metadata_json=str({
                        "file_name": doc["filename"],
                        "upload_date": doc["uploaded_at"],
                        "project_id": doc["project_id"],
                    }),
                )
            except Exception as e:
                logger.error(f"Failed to add chunk {idx} to DB for document {doc_id}: {e}")

        chunk_ids = [f"{doc_id}_chunk_{idx}" for idx in range(len(chunks))]
        logger.info(f"Processed document {doc_id}, generated {len(chunk_ids)} chunks")
        return chunk_ids

    async def process_file(self, doc_id: str, file_path: str) -> List[str]:
        logger.info(f"Processing file {file_path} for document {doc_id}")
        try:
            result = await self.document_processor.process_file(file_path)
            text = result.get("text", "")
            if not text:
                logger.warning(f"No text extracted from file {file_path}")
                return []
            return self.process_document(doc_id, text)
        except Exception as e:
            logger.error(f"Failed to process file {file_path}: {e}")
            return []
