"""RAG context formatter — formats retrieved chunks for LLM prompts.

Migrated from src/dms/rag_context_formatter.py. Default max_chars increased to 50,000.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ~12,500 tokens — fits comfortably in the smallest context windows (32K)
# while leaving room for system prompt, user prompt, and agent output.
DEFAULT_MAX_CHARS = 50_000


class RAGContextFormatter:
    """Formats RAG chunks into a readable string for LLM context injection."""

    def format(self, chunks: list[dict[str, Any]], max_chars: int | None = None) -> str:
        """Format chunks into a single context string.

        Args:
            chunks: List of chunk dicts with 'text' and 'metadata' keys.
            max_chars: Maximum character count. Defaults to 50,000 (~12,500 tokens).

        Returns:
            Formatted context string, truncated if necessary.
        """
        if not chunks:
            return ""

        effective_max = max_chars or DEFAULT_MAX_CHARS

        formatted_parts = []
        for idx, chunk in enumerate(chunks, start=1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown")
            formatted = f"[Document {idx} from {file_name}]: {text}\n\n"
            formatted_parts.append(formatted)

        full_context = "".join(formatted_parts)

        if len(full_context) > effective_max:
            truncate_len = effective_max - 3
            if truncate_len < 0:
                truncate_len = 0
            full_context = full_context[:truncate_len] + "..."

        return full_context
