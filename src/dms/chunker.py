import logging
import tiktoken

logger = logging.getLogger(__name__)


class TextChunker:
    def __init__(self):
        self.encoder = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = 512
        self.overlap = 51

    def chunk(self, text: str) -> list[str]:
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
