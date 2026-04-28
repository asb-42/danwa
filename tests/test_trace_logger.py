import pytest
from src.core.trace_logger import TraceLogger
from pathlib import Path
import tempfile


@pytest.fixture
def logger(tmp_path):
    return TraceLogger("test_session"), tmp_path


def test_logger_initialization(logger):
    log, _ = logger
    assert log.file is not None
    assert "test_session" in str(log.file)


def test_log_entry(logger):
    log, tmp_path = logger
    
    log.log(
        step="R1",
        agent="strategist",
        prompt="Test prompt",
        response="Test response",
        metadata={"tokens": 100},
        prompt_version="v1.0",
        prompt_hash="abc123"
    )
    
    assert log.file.exists()
    content = log.file.read_text()
    assert "Test prompt" in content
    assert "Test response" in content


def test_log_multiple_entries(logger):
    log, _ = logger
    
    for i in range(3):
        log.log(
            step=f"R{i}",
            agent="agent",
            prompt="p",
            response="r",
            metadata={}
        )
    
    log_entries = log.get_session_log()
    assert len(log_entries) == 3


def test_get_session_log_empty(tmp_path):
    log = TraceLogger("empty_session")
    entries = log.get_session_log()
    assert entries == []


def test_log_entry_structure(logger):
    log, _ = logger
    
    log.log(
        step="R1",
        agent="moderator",
        prompt="Rate consensus",
        response="0.85",
        metadata={"consensus": 0.85},
        prompt_variant="A"
    )
    
    entries = log.get_session_log()
    entry = entries[0]
    
    assert "timestamp" in entry
    assert entry["step"] == "R1"
    assert entry["agent"] == "moderator"
    assert "prompt_variant" in entry
    assert "prompt_version" in entry
    assert "prompt_hash" in entry


def test_log_special_characters(logger):
    log, _ = logger
    
    log.log(
        step="test",
        agent="test",
        prompt="Special: äöü ß",
        response="Response with\nnewline",
        metadata={}
    )
    
    entries = log.get_session_log()
    assert len(entries) == 1
    assert "äöü" in entries[0]["prompt_preview"]


def test_file_created_in_logs_dir(tmp_path):
    with patch("src.core.trace_logger.LOG_DIR") as mock_dir:
        mock_dir.__truediv__ = lambda s, o: tmp_path / "logs" / o
        mock_dir.mkdir = MagicMock()
        mock_dir.exists = MagicMock(return_value=True)
        
        log = TraceLogger("session1")
        log.log("s", "a", "p", "r", {})
        
        assert log.file.exists()
