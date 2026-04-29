from unittest.mock import Mock, patch
from src.dms.dms import DMS


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_dms_init_creates_components(
    mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db
):
    _dms = DMS()
    mock_db.assert_called_once()
    mock_pm.assert_called_once_with(mock_db.return_value)
    mock_dp.assert_called_once()
    mock_tc.assert_called_once()
    mock_vs.assert_called_once()
    mock_mi.assert_called_once_with(mock_vs.return_value)
    mock_rp.assert_called_once()
    mock_hr.assert_called_once_with(
        vector_store=mock_vs.return_value,
        metadata_index=mock_mi.return_value,
    )


@patch("src.dms.dms.ProjectManager")
def test_create_project_returns_id(mock_pm_cls):
    mock_pm = mock_pm_cls.return_value
    mock_pm.create_project.return_value = {"id": "proj_123", "name": "Test"}
    dms = DMS()
    dms.project_manager = mock_pm
    proj_id = dms.create_project("Test Project", "Desc")
    assert proj_id == "proj_123"
    mock_pm.create_project.assert_called_once_with("Test Project", "Desc")


@patch("src.dms.dms.ProjectManager")
def test_list_projects_returns_list(mock_pm_cls):
    mock_pm = mock_pm_cls.return_value
    mock_pm.list_projects.return_value = [{"id": "1"}, {"id": "2"}]
    dms = DMS()
    dms.project_manager = mock_pm
    projects = dms.list_projects()
    assert len(projects) == 2
    assert projects[0]["id"] == "1"


@patch("src.dms.dms.Path")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DMSDB")
@patch("asyncio.run")
def test_upload_document_success(mock_run, mock_db_cls, mock_pm_cls, mock_path):
    mock_path_instance = Mock()
    mock_path_instance.exists.return_value = True
    mock_path_instance.name = "test.pdf"
    mock_path_instance.resolve.return_value = "/fake/test.pdf"
    mock_path.return_value = mock_path_instance

    mock_pm = mock_pm_cls.return_value
    mock_pm.get_project.return_value = {"id": "proj1"}

    mock_db = mock_db_cls.return_value
    mock_db.add_document.return_value = {"id": "doc1"}

    mock_run.return_value = ["chunk1"]

    dms = DMS()
    dms.project_manager = mock_pm
    dms.db = mock_db

    doc_id = dms.upload_document("proj1", "test.pdf")
    assert doc_id == "doc1"
    mock_db.add_document.assert_called_once()
    mock_run.assert_called_once()


@patch("src.dms.dms.HybridRetriever")
def test_get_rag_context_calls_retriever(mock_hr_cls):
    mock_hr = mock_hr_cls.return_value
    mock_hr.retrieve.return_value = [{"text": "ctx1", "metadata": {}}]
    dms = DMS()
    dms.hybrid_retriever = mock_hr
    result = dms.get_rag_context("test query", project_id="proj1", k=3)
    assert len(result) == 1
    mock_hr.retrieve.assert_called_once_with("test query", project_id="proj1", k=3)


@patch("src.dms.dms.ProjectManager")
def test_delete_project(mock_pm_cls):
    mock_pm = mock_pm_cls.return_value
    mock_pm.delete_project.return_value = True
    dms = DMS()
    dms.project_manager = mock_pm
    result = dms.delete_project("proj1")
    assert result is True
    mock_pm.delete_project.assert_called_once_with("proj1")


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_add_to_rag_context(mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db):
    dms = DMS()
    result = dms.add_to_rag_context("doc1")
    assert result is True
    assert "doc1" in dms._manual_rag_docs
    result = dms.add_to_rag_context("doc1")
    assert result is False
    result = dms.add_to_rag_context("doc2")
    assert result is True
    assert "doc2" in dms._manual_rag_docs


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_remove_from_rag_context(mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db):
    dms = DMS()
    dms._manual_rag_docs.add("doc1")
    result = dms.remove_from_rag_context("doc1")
    assert result is True
    assert "doc1" not in dms._manual_rag_docs
    result = dms.remove_from_rag_context("doc2")
    assert result is False


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_list_manual_rag_documents(mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db):
    dms = DMS()
    dms._manual_rag_docs.update({"doc1", "doc2", "doc3"})
    docs = dms.list_manual_rag_documents()
    assert len(docs) == 3
    assert set(docs) == {"doc1", "doc2", "doc3"}


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_get_manual_rag_context(mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db):
    dms = DMS()
    dms._manual_rag_docs.add("doc1")
    mock_chunks = [
        {"id": "chunk1", "text": "test chunk 1", "metadata": {}},
        {"id": "chunk2", "text": "test chunk 2", "metadata": {}},
    ]
    dms.metadata_index.get_chunks_by_document.return_value = mock_chunks
    result = dms.get_manual_rag_context(k=5)
    assert len(result) == 2
    assert result == mock_chunks
    result = dms.get_manual_rag_context(k=1)
    assert len(result) == 1
    assert result[0] == mock_chunks[0]
    dms._manual_rag_docs.clear()
    result = dms.get_manual_rag_context()
    assert result == []


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_get_manual_rag_context_multiple_docs(mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db):
    dms = DMS()
    dms._manual_rag_docs.update({"doc1", "doc2"})
    chunks1 = [{"id": "c1", "text": "chunk1", "metadata": {}}]
    chunks2 = [{"id": "c2", "text": "chunk2", "metadata": {}}]
    dms.metadata_index.get_chunks_by_document.side_effect = [chunks1, chunks2]
    result = dms.get_manual_rag_context(k=5)
    assert len(result) == 2
    assert any(c["id"] == "c1" for c in result)
    assert any(c["id"] == "c2" for c in result)


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_auto_retrieve_for_topic_formats_chunks(
    mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db
):
    dms = DMS()
    with patch.object(dms, 'get_rag_context') as mock_get_rag:
        mock_get_rag.return_value = [
            {
                "text": "chunk 1 content",
                "metadata": {
                    "file_name": "report.pdf",
                    "chunk_index": 0,
                    "project_id": "proj_123",
                    "document_id": "doc_456"
                },
                "score": 0.95
            },
            {
                "text": "chunk 2 content",
                "metadata": {
                    "file_name": "data.docx",
                    "chunk_index": 3,
                    "project_id": "proj_123",
                    "document_id": "doc_789"
                },
                "score": 0.87
            }
        ]
        result = dms.auto_retrieve_for_topic("climate change", project_id="proj_123", k=2)
        assert len(result) == 2
        assert result[0]["text"] == "chunk 1 content"
        assert result[0]["source"] == "report.pdf"
        assert result[0]["chunk_index"] == 0
        assert result[0]["project_id"] == "proj_123"
        assert result[1]["text"] == "chunk 2 content"
        assert result[1]["source"] == "data.docx"
        assert result[1]["chunk_index"] == 3
        mock_get_rag.assert_called_once_with("climate change", "proj_123", 2)


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_auto_retrieve_for_topic_empty_results(
    mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db
):
    dms = DMS()
    with patch.object(dms, 'get_rag_context') as mock_get_rag:
        mock_get_rag.return_value = []
        result = dms.auto_retrieve_for_topic("empty topic")
        assert result == []


@patch("src.dms.dms.DMSDB")
@patch("src.dms.dms.ProjectManager")
@patch("src.dms.dms.DocumentProcessor")
@patch("src.dms.dms.TextChunker")
@patch("src.dms.dms.DMSVectorStore")
@patch("src.dms.dms.MetadataIndex")
@patch("src.dms.dms.RAGPipeline")
@patch("src.dms.dms.HybridRetriever")
def test_auto_retrieve_for_topic_missing_metadata(
    mock_hr, mock_rp, mock_mi, mock_vs, mock_tc, mock_dp, mock_pm, mock_db
):
    dms = DMS()
    with patch.object(dms, 'get_rag_context') as mock_get_rag:
        mock_get_rag.return_value = [
            {"text": "orphan chunk", "metadata": {}}
        ]
        result = dms.auto_retrieve_for_topic("topic")
        assert len(result) == 1
        assert result[0]["source"] == "unknown"
        assert result[0]["chunk_index"] == -1
        assert result[0]["project_id"] == "unknown"
