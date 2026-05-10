"""DMS (Document Management System) package — migrated from src/dms/."""

from backend.services.dms.chunker import TextChunker
from backend.services.dms.config import DEFAULT_DMS_CONFIG, load_dms_config
from backend.services.dms.database import DMSDB
from backend.services.dms.hybrid_retriever import HybridRetriever
from backend.services.dms.metadata_index import MetadataIndex
from backend.services.dms.rag_context_formatter import RAGContextFormatter
from backend.services.dms.rag_pipeline import RAGPipeline
from backend.services.dms.service import DMS

__all__ = [
    "DEFAULT_DMS_CONFIG",
    "DMS",
    "DMSDB",
    "HybridRetriever",
    "MetadataIndex",
    "RAGContextFormatter",
    "RAGPipeline",
    "TextChunker",
    "load_dms_config",
]
