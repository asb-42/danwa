import asyncio
import logging
from pathlib import Path
from typing import List, Dict

from .database import DMSDB
from .project_manager import ProjectManager
from .document_processor import DocumentProcessor
from .chunker import TextChunker
from .rag_pipeline import RAGPipeline
from .vector_store import DMSVectorStore
from .hybrid_retriever import HybridRetriever
from .metadata_index import MetadataIndex

logger = logging.getLogger(__name__)


class DMS:
    def __init__(self, db_path: str = None, chroma_path: str = None):
        self.db_path = db_path or "memory/dms.db"
        self.chroma_path = chroma_path or "memory/chroma_db"

        self.db = DMSDB()
        self.project_manager = ProjectManager(self.db)

        doc_config = {}
        self.document_processor = DocumentProcessor(doc_config)
        self.text_chunker = TextChunker()

        vs_config = {"chroma_collection": "document_chunks"}
        self.vector_store = DMSVectorStore(vs_config)
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
        self._manual_rag_docs = set()

        logger.info("DMS initialized (db: %s, chroma: %s)", self.db_path, self.chroma_path)

    def create_project(self, name: str, description: str = "") -> str:
        try:
            project = self.project_manager.create_project(name, description)
            logger.info("Created project %s: %s", project["id"], name)
            return project["id"]
        except Exception as e:
            logger.error("Failed to create project '%s': %s", name, e)
            return ""

    def delete_project(self, project_id: str) -> bool:
        try:
            result = self.project_manager.delete_project(project_id)
            logger.info("Deleted project %s: %s", project_id, result)
            return result
        except Exception as e:
            logger.error("Failed to delete project %s: %s", project_id, e)
            return False

    def list_projects(self) -> List[Dict]:
        try:
            return self.project_manager.list_projects()
        except Exception as e:
            logger.error("Failed to list projects: %s", e)
            return []

    def upload_document(self, project_id: str, file_path: str) -> str:
        file_p = Path(file_path)
        if not file_p.exists():
            logger.error("File not found: %s", file_path)
            return ""

        if not self.project_manager.get_project(project_id):
            logger.error("Project not found: %s", project_id)
            return ""

        try:
            doc = self.db.add_document(
                project_id=project_id,
                filename=file_p.name,
                file_path=str(file_p.resolve()),
            )
            doc_id = doc["id"]
            logger.info("Created document entry %s for project %s", doc_id, project_id)
        except Exception as e:
            logger.error("Failed to create document entry for %s: %s", file_path, e)
            return ""

        try:
            asyncio.run(self.rag_pipeline.process_file(doc_id, file_path))
        except Exception as e:
            logger.error("Failed to process document %s: %s", doc_id, e)

        return doc_id

    def delete_document(self, document_id: str) -> bool:
        try:
            self.db.delete_document(document_id)
            self.vector_store.delete_document_chunks(document_id)
            logger.info("Deleted document %s", document_id)
            return True
        except Exception as e:
            logger.error("Failed to delete document %s: %s", document_id, e)
            return False

    def list_documents(self, project_id: str = None) -> List[Dict]:
        try:
            if project_id is None:
                cursor = self.db.conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC")
                return [dict(row) for row in cursor.fetchall()]
            return self.db.list_documents(project_id)
        except Exception as e:
            logger.error("Failed to list documents (project %s): %s", project_id, e)
            return []

    def get_rag_context(self, query: str, project_id: str = None, k: int = 5) -> List[Dict]:
        try:
            return self.hybrid_retriever.retrieve(query, project_id=project_id, k=k)
        except Exception as e:
            logger.error("Failed to get RAG context for query '%s': %s", query, e)
            return []

    def add_to_rag_context(self, document_id: str) -> bool:
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

    def list_manual_rag_documents(self) -> List[str]:
        try:
            return list(self._manual_rag_docs)
        except Exception as e:
            logger.error("Failed to list manual RAG documents: %s", e)
            return []

    def get_manual_rag_context(self, k: int = 5) -> List[Dict]:
        try:
            all_chunks = []
            for doc_id in self._manual_rag_docs:
                chunks = self.metadata_index.get_chunks_by_document(doc_id)
                all_chunks.extend(chunks)
            return all_chunks[:k]
        except Exception as e:
            logger.error("Failed to get manual RAG context: %s", e)
            return []

    def auto_retrieve_for_topic(self, topic: str, project_id: str = None, k: int = 5) -> List[Dict]:
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
