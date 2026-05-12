import pytest
from src.core.privacy import PrivacyGuard
from pathlib import Path
import tempfile
import time
from unittest.mock import patch


@pytest.fixture
def privacy():
    return PrivacyGuard(strict_mode=False, retention_days=90, redact_traces=True)


def test_privacy_initialization(privacy):
    assert privacy.strict_mode == False
    assert privacy.retention_days == 90
    assert privacy.redact_traces == True


def test_redact_email(privacy):
    text = "Contact me at test@example.com for info"
    result = privacy.redact_text(text)
    assert "[REDACTED_EMAIL]" in result
    assert "test@example.com" not in result


def test_redact_ipv4(privacy):
    text = "Server at 192.168.1.1 is down"
    result = privacy.redact_text(text)
    assert "[REDACTED_IPV4]" in result
    assert "192.168.1.1" not in result


def test_redact_phone_de(privacy):
    text = "Call me at +49 123 456789"
    result = privacy.redact_text(text)
    assert "[REDACTED_PHONE_DE]" in result


def test_redact_id_number(privacy):
    text = "My ID is AB1234567C"
    result = privacy.redact_text(text)
    assert "[REDACTED_ID_NUMBER]" in result


def test_redact_multiple(privacy):
    text = "Email: test@example.com, IP: 10.0.0.1"
    result = privacy.redact_text(text)
    assert "[REDACTED_EMAIL]" in result
    assert "[REDACTED_IPV4]" in result


def test_redact_no_pii(privacy):
    text = "Just some normal text without sensitive data"
    result = privacy.redact_text(text)
    assert result == text


def test_redact_idempotent(privacy):
    text = "Email: test@example.com"
    result1 = privacy.redact_text(text)
    result2 = privacy.redact_text(result1)
    assert result1 == result2


def test_enforce_retention(privacy, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    
    old_file = logs_dir / "old_log.jsonl"
    old_file.write_text("old data")
    old_time = time.time() - (100 * 24 * 3600)
    import os
    os.utime(old_file, (old_time, old_time))
    
    recent_file = logs_dir / "recent_log.jsonl"
    recent_file.write_text("recent data")
    
    privacy.enforce_retention(str(tmp_path))
    
    assert not old_file.exists()
    assert recent_file.exists()


def test_enforce_retention_nonexistent_dir(privacy):
    privacy.enforce_retention("/nonexistent/path")
    assert True


def test_strict_mode_blocks():
    privacy = PrivacyGuard(strict_mode=True)
    assert privacy.strict_mode == True
