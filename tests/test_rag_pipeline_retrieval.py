import pytest
from unittest.mock import Mock, patch, AsyncMock

from src.dms.rag_pipeline import RAGPipeline
from src.dms.hybrid_retriever import HybridRetriever
from src.dms.chunker import TextChunker


class TestRAGPipeline:
    @pytest.fixture
    def pipeline(self):
        return RAGPipeline(
            document_processor=Mock(),
            text_chunker=Mock(),
            vector_store=Mock(),
            db=Mock()
        )

    def test_process_document_stores_chunks_in_chromadb(self, pipeline):
        doc_id = "doc1"
        pipeline.db.get_document.return_value = {
            "project_id": "proj1",
            "filename": "test.txt",
            "uploaded_at": "2024-01-01"
        }
        pipeline.text_chunker.chunk.return_value = ["chunk1", "chunk2"]
        pipeline.vector_store.add_chunks = Mock()

        result = pipeline.process_document(doc_id, "sample text")

        pipeline.text_chunker.chunk.assert_called_once_with("sample text")
        pipeline.vector_store.add_chunks.assert_called_once_with(
            document_id=doc_id,
            chunks=[
                {"text": "chunk1", "chunk_index": 0, "page": 0},
                {"text": "chunk2", "chunk_index": 1, "page": 0}
            ],
            project_id="proj1"
        )
        assert result == ["doc1_chunk_0", "doc1_chunk_1"]

    @pytest.mark.asyncio
    async def test_process_file_with_async_support(self, pipeline):
        doc_id = "doc1"
        file_path = "/path/to/file.txt"
        pipeline.document_processor.process_file = AsyncMock(
            return_value={"text": "extracted text"}
        )
        pipeline.text_chunker.chunk.return_value = ["chunk1"]
        pipeline.db.get_document.return_value = {
            "project_id": "proj1",
            "filename": "file.txt",
            "uploaded_at": "2024-01-01"
        }

        result = await pipeline.process_file(doc_id, file_path)

        pipeline.document_processor.process_file.assert_called_once_with(file_path)
        assert result == ["doc1_chunk_0"]

    def test_pipeline_handles_processing_errors(self, pipeline):
        assert pipeline.process_document("doc1", "") == []

        pipeline.db.get_document.return_value = None
        assert pipeline.process_document("doc1", "text") == []

        pipeline.db.get_document.return_value = {"project_id": "proj1"}
        pipeline.text_chunker.chunk.side_effect = Exception("Chunking failed")
        assert pipeline.process_document("doc1", "text") == []

        pipeline.text_chunker.chunk.side_effect = None
        pipeline.text_chunker.chunk.return_value = ["chunk1"]
        pipeline.vector_store.add_chunks.side_effect = Exception("Vector store failed")
        assert pipeline.process_document("doc1", "text") == []

        pipeline.vector_store.add_chunks.side_effect = None
        pipeline.db.add_chunk.side_effect = Exception("DB add failed")
        assert pipeline.process_document("doc1", "text") == ["doc1_chunk_0"]


class TestHybridRetriever:
    @pytest.fixture
    def retriever(self):
        return HybridRetriever(
            vector_store=Mock(),
            metadata_index=Mock()
        )

    def test_bm25_retrieval_returns_results(self, retriever):
        chunks = [
            {"id": "c1", "text": "hello world", "metadata": {}},
            {"id": "c2", "text": "hello there", "metadata": {}},
            {"id": "c3", "text": "goodbye world", "metadata": {}}
        ]
        retriever._fetch_chunks = Mock(return_value=chunks)

        results = retriever._bm25_retrieve("hello", chunks, top_n=20)

        assert len(results) >= 1
        assert all("id" in r and "bm25_score" in r for r in results)

    def test_vector_retrieval_returns_results(self, retriever):
        retriever.vector_store.search.return_value = [
            {"text": "vec1", "metadata": {"document_id": "d1", "chunk_index": 0}, "score": 0.9}
        ]
        retriever._fetch_chunks = Mock(return_value=[])
        retriever._bm25_retrieve = Mock(return_value=[])

        results = retriever.retrieve("test", k=5)

        retriever.vector_store.search.assert_called_once_with("test", project_id=None, k=20)
        assert len(results) >= 1

    def test_hybrid_retriever_combines_results(self, retriever):
        retriever._fetch_chunks = Mock(return_value=[
            {"id": "c1", "text": "bm25 result", "metadata": {}}
        ])
        retriever._bm25_retrieve = Mock(return_value=[
            {"id": "c1", "text": "bm25 result", "metadata": {}}
        ])
        retriever.vector_store.search = Mock(return_value=[
            {"text": "vec result", "metadata": {"document_id": "d1", "chunk_index": 0}}
        ])

        results = retriever.retrieve("test", k=5)

        assert len(results) == 2
        assert any(r["text"] == "bm25 result" for r in results)
        assert any(r["text"] == "vec result" for r in results)

    def test_reranking_with_crossencoder(self, retriever):
        mock_encoder = Mock()
        mock_encoder.predict.return_value = [0.95, 0.85]
        retriever.cross_encoder = mock_encoder

        retriever._fetch_chunks = Mock(return_value=[])
        retriever._bm25_retrieve = Mock(return_value=[
            {"id": "c1", "text": "text1", "metadata": {}}
        ])
        retriever.vector_store.search = Mock(return_value=[
            {"text": "text2", "metadata": {"document_id": "d1", "chunk_index": 0}}
        ])

        results = retriever.retrieve("test", k=5)

        mock_encoder.predict.assert_called_once()
        assert all("score" in r for r in results)

    def test_retrieval_with_project_filter(self, retriever):
        retriever.metadata_index.get_chunks_by_project = Mock(return_value=[
            {"id": "c1", "text": "proj chunk", "metadata": {"project_id": "p1"}}
        ])
        retriever._bm25_retrieve = Mock(return_value=[])
        retriever.vector_store.search = Mock(return_value=[])

        retriever.retrieve("test", project_id="p1", k=5)
        retriever.metadata_index.get_chunks_by_project.assert_called_once_with("p1")

        retriever.metadata_index = None
        retriever.vector_store.collection = Mock()
        retriever.vector_store.collection.get.return_value = {
            "ids": ["c1"], "documents": ["chunk"], "metadatas": [{"project_id": "p1"}]
        }
        retriever.retrieve("test", project_id="p1", k=5)
        retriever.vector_store.collection.get.assert_called_once_with(
            where={"project_id": "p1"}, include=["documents", "metadatas", "ids"]
        )


class TestTextChunker:
    @pytest.fixture
    def chunker(self):
        with patch("src.dms.chunker.tiktoken") as mock_tiktoken:
            mock_encoder = Mock()
            mock_tiktoken.get_encoding.return_value = mock_encoder
            chunker = TextChunker()
            chunker.encoder = mock_encoder
            return chunker

    def test_chunk_text_512_tokens(self, chunker):
        chunker.encoder.encode.return_value = list(range(600))
        chunker.encoder.decode.side_effect = lambda t: f"chunk_{len(t)}"

        chunks = chunker.chunk("text")

        assert len(chunks) == 2
        decode_calls = chunker.encoder.decode.call_args_list
        assert len(decode_calls[0][0][0]) == 512
        assert len(decode_calls[1][0][0]) == 139

    def test_chunk_overlap_10_percent(self, chunker):
        assert chunker.chunk_size == 512
        assert chunker.overlap == 51
        assert abs((chunker.overlap / chunker.chunk_size) * 100 - 10) < 1

        chunker.encoder.encode.return_value = list(range(600))
        chunker.encoder.decode.side_effect = lambda t: "".join(str(x) for x in t)
        chunks = chunker.chunk("text")
        if len(chunks) >= 2:
            overlap = "".join(str(x) for x in range(461, 512))
            assert overlap in chunks[0] and overlap in chunks[1]

    def test_empty_text_returns_empty_list(self, chunker):
        assert chunker.chunk("") == []
