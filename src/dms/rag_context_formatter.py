import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class RAGContextFormatter:
    def format(self, chunks: List[Dict], max_chars: int = 4000) -> str:
        if not chunks:
            return ""
        
        formatted_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown")
            formatted = f"[Document {idx} from {file_name}]: {text}\n\n"
            formatted_parts.append(formatted)
        
        full_context = "".join(formatted_parts)
        
        if len(full_context) > max_chars:
            truncate_len = max_chars - 3
            if truncate_len < 0:
                truncate_len = 0
            full_context = full_context[:truncate_len] + "..."
        
        return full_context
