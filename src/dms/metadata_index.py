import logging
from typing import List, Dict
from .vector_store import DMSVectorStore
from .database import DMSDB

logger = logging.getLogger(__name__)


class MetadataIndex:
    def __init__(self, chroma_store: DMSVectorStore):
        self.chroma_store = chroma_store

    def get_chunks_by_project(self, project_id: str) -> List[Dict]:
        try:
            results = self.chroma_store.collection.get(
                where={"project_id": project_id},
                include=["metadatas", "documents", "ids"]
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error(f"Failed to fetch chunks for project {project_id}: {e}")
            return []

    def get_chunks_by_document(self, document_id: str) -> List[Dict]:
        try:
            results = self.chroma_store.collection.get(
                where={"document_id": document_id},
                include=["metadatas", "documents", "ids"]
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error(f"Failed to fetch chunks for document {document_id}: {e}")
            return []

    def get_chunks_by_date_range(self, start_date: str, end_date: str) -> List[Dict]:
        try:
            results = self.chroma_store.collection.get(
                where={"upload_date": {"$gte": start_date, "$lte": end_date}},
                include=["metadatas", "documents", "ids"]
            )
            return self._process_chunks(results)
        except Exception as e:
            logger.error(f"Failed to fetch chunks between {start_date} and {end_date}: {e}")
            return []

    def _process_chunks(self, results: Dict) -> List[Dict]:
        chunks = []
        doc_ids = set()
        for meta in results.get("metadatas", []):
            if "document_id" in meta:
                doc_ids.add(meta["document_id"])

        doc_info = {}
        if doc_ids:
            try:
                db = DMSDB()
                for doc_id in doc_ids:
                    doc = db.get_document(doc_id)
                    if doc:
                        doc_info[doc_id] = {
                            "file_name": doc["filename"],
                            "upload_date": doc["uploaded_at"]
                        }
                db.close()
            except Exception as e:
                logger.error(f"Failed to fetch document info from DMSDB: {e}")

        for chunk_id, doc_text, meta in zip(
            results.get("ids", []),
            results.get("documents", []),
            results.get("metadatas", [])
        ):
            chunks.append({
                "id": chunk_id,
                "text": doc_text,
                "metadata": {
                    "project_id": meta.get("project_id"),
                    "document_id": meta.get("document_id"),
                    "chunk_index": meta.get("chunk_index"),
                    "file_name": doc_info.get(meta.get("document_id"), {}).get("file_name"),
                    "upload_date": doc_info.get(meta.get("document_id"), {}).get("upload_date"),
                }
            })
        return chunks
