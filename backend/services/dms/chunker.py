"""Token-based text chunker using tiktoken.

Migrated from src/dms/chunker.py.
"""

import logging

import tiktoken

logger = logging.getLogger(__name__)


class TextChunker:
    """Splits text into overlapping chunks based on token count."""

    def __init__(self, chunk_size: int = 512, overlap: int = 51):
        """Initialise TextChunker."""
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, text: str) -> list[str]:
        """Chunk the instance."""
        if not text:
            return []
        tokens = self.encoder.encode(text)
        if len(tokens) <= self.chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunks.append(self.encoder.decode(chunk_tokens))
            start += self.chunk_size - self.overlap
            if start >= len(tokens):
                break
        return chunks
