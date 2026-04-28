import pytest
from unittest.mock import patch, MagicMock
from src.core.memory import DebateMemory
from src.core.debate_engine import DebateState
import tempfile
from pathlib import Path


@pytest.fixture
def memory(tmp_path):
    with patch("src.core.memory.chromadb") as mock_chromadb:
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb.PersistentClient.return_value = mock_client
        mock_chromadb.api.types.EmbeddingFunction = object
        
        with patch("src.core.memory.MEMORY_DIR", tmp_path / "memory"):
            return DebateMemory(), mock_collection


def test_memory_initialization(memory):
    mem, _ = memory
    assert mem is not None


def test_format_document(memory):
    mem, _ = memory
    state = DebateState()
    state.context = "Test context for the debate"
    state.final_consensus = 0.85
    state.output = "This is the final output of the debate"
    
    result = mem._format_document(state)
    
    assert "Test context" in result
    assert "0.85" in result
    assert "final output" in result.lower()


def test_store_debate(memory):
    mem, mock_collection = memory
    state = DebateState()
    state.context = "Test topic"
    state.final_consensus = 0.90
    state.output = "Final argumentation"
    
    mem.store_debate(state)
    
    mock_collection.add.assert_called_once()
    call_args = mock_collection.add.call_args[1]
    assert "documents" in call_args
    assert "metadatas" in call_args
    assert "ids" in call_args


def test_store_debate_empty_output(memory):
    mem, mock_collection = memory
    state = DebateState()
    state.output = ""
    
    mem.store_debate(state)
    
    mock_collection.add.assert_not_called()


def test_search_precedents(memory):
    mem, mock_collection = memory
    mock_collection.count.return_value = 2
    mock_collection.query.return_value = {
        "documents": [["Doc 1", "Doc 2"]],
        "metadatas": [[{"session_id": "abc", "consensus": 0.85, "timestamp": "2024-01-01", "rounds": 3, "validated": True}]],
        "distances": [[0.1, 0.3]]
    }
    
    results = mem.search_precedents("test query", top_k=2)
    
    assert len(results) == 2
    assert "document" in results[0]
    assert "relevance_score" in results[0]
    assert results[0]["relevance_score"] > 0


def test_search_precedents_empty(memory):
    mem, mock_collection = memory
    mock_collection.count.return_value = 0
    
    results = mem.search_precedents("test query")
    
    assert results == []
    mock_collection.query.assert_not_called()


def test_search_precedents_exception(memory):
    mem, mock_collection = memory
    mock_collection.count.return_value = 1
    mock_collection.query.side_effect = Exception("Query failed")
    
    results = mem.search_precedents("test query")
    
    assert results == []
