from unittest.mock import Mock, patch
from src.dms.dms_memory import DMSMemory
from src.dms.dms import DMS


class TestDMSMemory:
    def test_init_with_default_dms(self):
        with patch("src.dms.dms_memory.DMS") as mock_dms_class:
            mock_dms_instance = Mock()
            mock_dms_class.return_value = mock_dms_instance
            memory = DMSMemory()
            mock_dms_class.assert_called_once()
            assert memory.dms == mock_dms_instance

    def test_init_with_provided_dms(self):
        mock_dms = Mock(spec=DMS)
        memory = DMSMemory(dms_instance=mock_dms)
        assert memory.dms == mock_dms

    def test_get_context_success(self):
        mock_dms = Mock(spec=DMS)
        mock_chunks = [{"text": "test chunk", "metadata": {"file_name": "test.txt"}}]
        mock_dms.get_rag_context.return_value = mock_chunks
        memory = DMSMemory(dms_instance=mock_dms)
        mock_formatter = Mock()
        mock_formatter.format.return_value = "formatted context"
        memory.rag_formatter = mock_formatter

        result = memory.get_context("test query", project_id="proj1", k=3)
        mock_dms.get_rag_context.assert_called_once_with("test query", project_id="proj1", k=3)
        mock_formatter.format.assert_called_once_with(mock_chunks)
        assert result == "formatted context"

    def test_get_context_handles_exception(self):
        mock_dms = Mock(spec=DMS)
        mock_dms.get_rag_context.side_effect = Exception("retrieval failed")
        memory = DMSMemory(dms_instance=mock_dms)
        result = memory.get_context("test query")
        assert result == ""

    def test_add_document_context_success(self):
        mock_dms = Mock(spec=DMS)
        mock_dms.add_to_rag_context.return_value = True
        memory = DMSMemory(dms_instance=mock_dms)
        result = memory.add_document_context("doc123")
        mock_dms.add_to_rag_context.assert_called_once_with("doc123")
        assert result is True

    def test_remove_document_context_success(self):
        mock_dms = Mock(spec=DMS)
        mock_dms.remove_from_rag_context.return_value = True
        memory = DMSMemory(dms_instance=mock_dms)
        result = memory.remove_document_context("doc123")
        mock_dms.remove_from_rag_context.assert_called_once_with("doc123")
        assert result is True
