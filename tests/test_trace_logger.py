"""Tests for TraceLogger — full prompt/response logging."""

from __future__ import annotations

import pytest
from src.core.trace_logger import TraceLogger
from pathlib import Path
from unittest.mock import patch


@pytest.fixture
def logger(tmp_path):
    with patch("src.core.trace_logger.LOG_DIR", tmp_path / "logs"):
        tmp_path.mkdir(exist_ok=True)
        (tmp_path / "logs").mkdir(exist_ok=True)
        return TraceLogger("test_session"), tmp_path


def test_logger_initialization(logger):
    log, _ = logger
    assert log.file is not None
    assert "test_session" in str(log.file)


def test_log_entry(logger):
    log, _ = logger

    log.log(
        step="R1",
        agent="strategist",
        prompt="Test prompt",
        response="Test response",
        metadata={"tokens": 100},
        prompt_version="v1.0",
        prompt_hash="abc123",
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
            metadata={},
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
        prompt_variant="A",
    )

    entries = log.get_session_log()
    entry = entries[0]

    assert "timestamp" in entry
    assert entry["step"] == "R1"
    assert entry["agent"] == "moderator"
    assert "prompt_variant" in entry
    assert "prompt_version" in entry
    assert "prompt_hash" in entry
    assert "prompt" in entry
    assert "response" in entry
    assert entry["prompt"] == "Rate consensus"
    assert entry["response"] == "0.85"


def test_log_special_characters(logger):
    log, _ = logger

    log.log(
        step="test",
        agent="test",
        prompt="Special: äöü ß",
        response="Response with\nnewline",
        metadata={},
    )

    entries = log.get_session_log()
    assert len(entries) == 1
    assert "äöü" in entries[0]["prompt"]


def test_file_created_in_logs_dir(tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()

    with patch("src.core.trace_logger.LOG_DIR", logs_dir):
        log = TraceLogger("session1")
        log.log("s", "a", "p", "r", {})

        assert log.file.exists()


def test_log_preserves_full_content(logger):
    """Verify that full prompt/response text is stored, not just previews."""
    long_prompt = "A" * 5000
    long_response = "B" * 5000

    log, _ = logger
    log.log(
        step="R1",
        agent="strategist",
        prompt=long_prompt,
        response=long_response,
        metadata={},
    )

    entries = log.get_session_log()
    entry = entries[0]
    assert entry["prompt"] == long_prompt
    assert entry["response"] == long_response
