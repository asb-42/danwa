import pytest
from src.core.logging_config import setup_logging, JSONFormatter
import logging
import json
from pathlib import Path
import tempfile
from unittest.mock import patch, MagicMock


def test_json_formatter():
    fmt = JSONFormatter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None
    )
    
    result = fmt.format(record)
    parsed = json.loads(result)
    
    assert "ts" in parsed
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "Test message"
    assert "src" in parsed


def test_json_formatter_with_exception():
    fmt = JSONFormatter()
    try:
        raise ValueError("Test error")
    except Exception:
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=True
        )

    result = fmt.format(record)
    parsed = json.loads(result)

    assert parsed["level"] == "ERROR"
    assert "exc" in parsed


def test_setup_logging_creates_logs_dir(tmp_path):
    with patch("src.core.logging_config.Path") as mock_path:
        mock_logs_dir = tmp_path / "logs"
        mock_logs_dir.mkdir(exist_ok=True)
        mock_path.return_value.exists.return_value = False
        mock_path.return_value.mkdir = MagicMock()

        setup_logging()

        mock_path.return_value.mkdir.assert_called_once()


def test_setup_logging_sets_level():
    with patch("src.core.logging_config.logging") as mock_logging:
        setup_logging(level="DEBUG")
        mock_logging.basicConfig.assert_called_once()
        call_kwargs = mock_logging.basicConfig.call_args[1]
        assert call_kwargs["level"] == "DEBUG"


def test_setup_logging_configures_litellm_level():
    with patch("src.core.logging_config.logging") as mock_logging:
        mock_litellm = MagicMock()
        mock_logging.getLogger.side_effect = lambda name: {
            "litellm": mock_litellm
        }.get(name, MagicMock())

        setup_logging()

        mock_litellm.setLevel.assert_called_once()
