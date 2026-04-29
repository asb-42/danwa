import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.dms.dms import DMS
from src.dms.dms_memory import DMSMemory
from src.dms.project_manager import ProjectManager


class TestDMS:
    @pytest.fixture(autouse=True)
    def setup(self):
        with patch("src.dms.dms.DMSDB") as mock_db_cls, \
             patch("src.dms.dms.ProjectManager") as mock_pm_cls, \
             patch("src.dms.dms.DocumentProcessor") as mock_dp_cls, \
             patch("src.dms.dms.TextChunker") as mock_tc_cls, \
             patch("src.dms.dms.RAGPipeline") as mock_rp_cls, \
             patch("src.dms.dms.DMSVectorStore") as mock_vs_cls, \
             patch("src.dms.dms.HybridRetriever") as mock_hr_cls, \
             patch("src.dms.dms.MetadataIndex") as mock_mi_cls:

            self.mock_db = mock_db_cls.return_value
            self.mock_pm = mock_pm_cls.return_value
            self.mock_dp = mock_dp_cls.return_value
            self.mock_tc = mock_tc_cls.return_value
            self.mock_rp = mock_rp_cls.return_value
            self.mock_vs = mock_vs_cls.return_value
            self.mock_hr = mock_hr_cls.return_value
            self.mock_mi = mock_mi_cls.return_value

            self.dms = DMS(db_path="test_db", chroma_path="test_chroma")
            yield

    def test_create_project_and_upload_document(self):
        mock_project = {"id": "proj1", "name": "Test Project", "description": ""}
        self.mock_pm.create_project.return_value = mock_project
        project_id = self.dms.create_project("Test Project", "Desc")
        assert project_id == "proj1"
        self.mock_pm.create_project.assert_called_once_with("Test Project", "Desc")

        self.mock_pm.create_project.side_effect = Exception("DB error")
        project_id = self.dms.create_project("Fail Project")
        assert project_id == ""
        self.mock_pm.create_project.side_effect = None

        self.mock_pm.get_project.return_value = mock_project
        mock_doc = {"id": "doc1", "filename": "test.pdf", "file_path": "/tmp/test.pdf"}
        self.mock_db.add_document.return_value = mock_doc
        with patch("src.dms.dms.Path.exists", return_value=True), \
             patch("asyncio.run") as mock_asyncio_run:
            doc_id = self.dms.upload_document(project_id, "test.pdf")
            assert doc_id == "doc1"
            self.mock_db.add_document.assert_called_once_with(
                project_id=project_id,
                filename="test.pdf",
                file_path=str(Path("test.pdf").resolve())
            )
            mock_asyncio_run.assert_called_once()

        with patch("src.dms.dms.Path.exists", return_value=False):
            doc_id = self.dms.upload_document(project_id, "missing.pdf")
            assert doc_id == ""

        self.mock_pm.get_project.return_value = None
        doc_id = self.dms.upload_document("invalid_proj", "test.pdf")
        assert doc_id == ""

        self.mock_pm.get_project.return_value = mock_project
        self.mock_db.add_document.side_effect = Exception("DB error")
        doc_id = self.dms.upload_document(project_id, "test.pdf")
        assert doc_id == ""
        self.mock_db.add_document.side_effect = None

    def test_get_rag_context_integration(self):
        mock_chunks = [{"text": "chunk1", "metadata": {"project_id": "proj1"}}]
        self.mock_hr.retrieve.return_value = mock_chunks
        result = self.dms.get_rag_context("test query", project_id="proj1", k=3)
        assert result == mock_chunks
        self.mock_hr.retrieve.assert_called_once_with("test query", project_id="proj1", k=3)

        self.mock_hr.retrieve.side_effect = Exception("Retrieval failed")
        result = self.dms.get_rag_context("test query")
        assert result == []
        self.mock_hr.retrieve.side_effect = None

    def test_manual_rag_context_flow(self):
        result = self.dms.add_to_rag_context("doc1")
        assert result is True
        assert "doc1" in self.dms._manual_rag_docs

        result = self.dms.add_to_rag_context("doc1")
        assert result is False

        result = self.dms.list_manual_rag_documents()
        assert result == ["doc1"]

        mock_chunks = [{"id": "c1", "text": "test"}]
        self.mock_mi.get_chunks_by_document.return_value = mock_chunks
        result = self.dms.get_manual_rag_context(k=2)
        assert result == mock_chunks
        self.mock_mi.get_chunks_by_document.assert_called_once_with("doc1")

        result = self.dms.remove_from_rag_context("doc1")
        assert result is True
        assert "doc1" not in self.dms._manual_rag_docs

        result = self.dms.remove_from_rag_context("doc1")
        assert result is False

        self.mock_mi.get_chunks_by_document.reset_mock()
        result = self.dms.get_manual_rag_context()
        assert result == []

    def test_auto_retrieve_for_topic(self):
        mock_raw_chunks = [
            {"text": "chunk1", "metadata": {"file_name": "doc1.pdf", "chunk_index": 0, "project_id": "proj1"}},
            {"text": "chunk2", "metadata": {"file_name": "doc2.pdf", "chunk_index": 1, "project_id": "proj1"}},
        ]
        with patch.object(self.dms, "get_rag_context", return_value=mock_raw_chunks):
            result = self.dms.auto_retrieve_for_topic("test topic", project_id="proj1", k=2)
            assert len(result) == 2
            assert result[0]["text"] == "chunk1"
            assert result[0]["source"] == "doc1.pdf"
            assert result[0]["chunk_index"] == 0
            assert result[0]["project_id"] == "proj1"
            self.dms.get_rag_context.assert_called_once_with("test topic", "proj1", 2)

        with patch.object(self.dms, "get_rag_context", return_value=[]):
            result = self.dms.auto_retrieve_for_topic("test topic")
            assert result == []

        with patch.object(self.dms, "get_rag_context", side_effect=Exception("Failed")):
            result = self.dms.auto_retrieve_for_topic("test topic")
            assert result == []

    def test_document_management(self):
        project_id = "proj1"
        mock_project = {"id": project_id}
        self.mock_pm.get_project.return_value = mock_project
        mock_doc = {"id": "doc1"}
        self.mock_db.add_document.return_value = mock_doc
        with patch("src.dms.dms.Path.exists", return_value=True), \
             patch("asyncio.run"):
            doc_id = self.dms.upload_document(project_id, "test.pdf")
            assert doc_id == "doc1"

        self.mock_db.delete_document.return_value = True
        result = self.dms.delete_document("doc1")
        assert result is True
        self.mock_db.delete_document.assert_called_once_with("doc1")
        self.mock_vs.delete_document_chunks.assert_called_once_with("doc1")

        self.mock_db.delete_document.side_effect = Exception("DB error")
        result = self.dms.delete_document("doc1")
        assert result is False
        self.mock_db.delete_document.side_effect = None

        mock_docs = [{"id": "doc1"}, {"id": "doc2"}]
        self.mock_db.list_documents.return_value = mock_docs
        result = self.dms.list_documents(project_id)
        assert result == mock_docs
        self.mock_db.list_documents.assert_called_once_with(project_id)

        self.mock_db.conn.execute.return_value.fetchall.return_value = [{"id": "doc1"}]
        result = self.dms.list_documents()
        assert len(result) == 1
        self.mock_db.conn.execute.assert_called_once_with(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        )


class TestDMSMemory:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_dms = Mock(spec=DMS)
        self.mock_rag_formatter = Mock()
        with patch("src.dms.dms_memory.RAGContextFormatter", return_value=self.mock_rag_formatter):
            self.memory = DMSMemory(dms_instance=self.mock_dms)
        yield

    def test_memory_get_context(self):
        mock_chunks = [{"text": "chunk1"}]
        self.mock_dms.get_rag_context.return_value = mock_chunks
        self.mock_rag_formatter.format.return_value = "formatted context"
        result = self.memory.get_context("test query", project_id="proj1", k=3)
        assert result == "formatted context"
        self.mock_dms.get_rag_context.assert_called_once_with("test query", project_id="proj1", k=3)
        self.mock_rag_formatter.format.assert_called_once_with(mock_chunks)

        self.mock_dms.get_rag_context.side_effect = Exception("Failed")
        result = self.memory.get_context("test query")
        assert result == ""
        self.mock_dms.get_rag_context.side_effect = None

    def test_memory_add_remove_document_context(self):
        self.mock_dms.add_to_rag_context.return_value = True
        result = self.memory.add_document_context("doc1")
        assert result is True
        self.mock_dms.add_to_rag_context.assert_called_once_with("doc1")

        self.mock_dms.add_to_rag_context.return_value = False
        result = self.memory.add_document_context("doc1")
        assert result is False

        self.mock_dms.remove_from_rag_context.return_value = True
        result = self.memory.remove_document_context("doc1")
        assert result is True
        self.mock_dms.remove_from_rag_context.assert_called_once_with("doc1")

        self.mock_dms.remove_from_rag_context.return_value = False
        result = self.memory.remove_document_context("doc1")
        assert result is False


class TestProjectManager:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_db = Mock()
        self.pm = ProjectManager(self.mock_db)
        yield

    def test_project_crud_operations(self):
        mock_project = {"id": "proj1", "name": "Test", "description": "Desc", "created_at": "2024-01-01"}
        self.mock_db.create_project.return_value = mock_project
        result = self.pm.create_project("Test", "Desc")
        assert result == mock_project
        self.mock_db.create_project.assert_called_once_with("Test", "Desc")

        self.mock_db.get_project.return_value = mock_project
        result = self.pm.get_project("proj1")
        assert result == mock_project
        self.mock_db.get_project.assert_called_once_with("proj1")

        self.mock_db.get_project.return_value = None
        result = self.pm.get_project("invalid")
        assert result is None

        mock_projects = [mock_project]
        self.mock_db.list_projects.return_value = mock_projects
        result = self.pm.list_projects()
        assert result == mock_projects

        self.mock_db.get_project.return_value = mock_project
        updated_project = {**mock_project, "name": "Updated"}
        self.mock_db.get_project.return_value = updated_project
        result = self.pm.update_project("proj1", name="Updated")
        assert result["name"] == "Updated"
        assert self.mock_db.conn.execute.called
        self.mock_db.conn.commit.assert_called_once()

        self.mock_db.get_project.return_value = mock_project
        result = self.pm.update_project("proj1")
        assert result == mock_project

        self.mock_db.get_project.return_value = None
        result = self.pm.update_project("invalid", name="Test")
        assert result is None

        self.mock_db.delete_project.return_value = True
        result = self.pm.delete_project("proj1")
        assert result is True
        self.mock_db.delete_project.assert_called_once_with("proj1")

    def test_document_management(self):
        assert not hasattr(self.pm, "add_document")
        assert not hasattr(self.pm, "delete_document")
        assert not hasattr(self.pm, "list_documents")
