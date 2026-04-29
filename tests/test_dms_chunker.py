import tiktoken
from src.dms.chunker import TextChunker

encoder = tiktoken.get_encoding("cl100k_base")


def test_empty_text():
    chunker = TextChunker()
    assert chunker.chunk("") == []


def _make_text_with_tokens(n: int) -> str:
    base = "a " * (n * 2)
    tokens = encoder.encode(base)[:n]
    return encoder.decode(tokens)


def test_short_text():
    chunker = TextChunker()
    text = _make_text_with_tokens(100)
    assert chunker.chunk(text) == [text]


def test_exact_chunk_size():
    chunker = TextChunker()
    text = _make_text_with_tokens(512)
    assert chunker.chunk(text) == [text]


def test_text_with_513_tokens():
    chunker = TextChunker()
    text = _make_text_with_tokens(513)
    chunks = chunker.chunk(text)
    assert len(chunks) == 2
    chunk1_tokens = encoder.encode(chunks[0])
    chunk2_tokens = encoder.encode(chunks[1])
    assert chunk1_tokens[-51:] == chunk2_tokens[:51]


def test_multiple_chunks():
    chunker = TextChunker()
    text = _make_text_with_tokens(974)
    chunks = chunker.chunk(text)
    assert len(chunks) == 3
    chunk1_tokens = encoder.encode(chunks[0])
    chunk2_tokens = encoder.encode(chunks[1])
    chunk3_tokens = encoder.encode(chunks[2])
    assert chunk1_tokens[-51:] == chunk2_tokens[:51]
    assert chunk2_tokens[-51:] == chunk3_tokens[:51]


def test_overlap_correctness():
    chunker = TextChunker()
    text = _make_text_with_tokens(1000)
    chunks = chunker.chunk(text)
    assert len(chunks) >= 2
    for i in range(len(chunks) - 1):
        current_tokens = encoder.encode(chunks[i])
        next_tokens = encoder.encode(chunks[i + 1])
        assert current_tokens[-51:] == next_tokens[:51]
