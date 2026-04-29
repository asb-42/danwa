import logging
from typing import Optional

from .dms import DMS
from .rag_context_formatter import RAGContextFormatter

logger = logging.getLogger(__name__)


class DMSMemory:
    def __init__(self, dms_instance: Optional[DMS] = None):
        if dms_instance is None:
            self.dms = DMS()
        else:
            self.dms = dms_instance
        self.rag_formatter = RAGContextFormatter()
        logger.info("DMSMemory initialized")

    def get_context(self, query: str, project_id: Optional[str] = None, k: int = 5) -> str:
        try:
            chunks = self.dms.get_rag_context(query, project_id=project_id, k=k)
            formatted_context = self.rag_formatter.format(chunks)
            logger.info("Retrieved RAG context for query: %s", query)
            return formatted_context
        except Exception as e:
            logger.error("Failed to get RAG context for query '%s': %s", query, e)
            return ""

    def add_document_context(self, document_id: str) -> bool:
        try:
            result = self.dms.add_to_rag_context(document_id)
            logger.info("Add document %s to manual RAG context: %s", document_id, result)
            return result
        except Exception as e:
            logger.error("Failed to add document %s to manual RAG context: %s", document_id, e)
            return False

    def remove_document_context(self, document_id: str) -> bool:
        try:
            result = self.dms.remove_from_rag_context(document_id)
            logger.info("Remove document %s from manual RAG context: %s", document_id, result)
            return result
        except Exception as e:
            logger.error("Failed to remove document %s from manual RAG context: %s", document_id, e)
            return False
