"""Tests for Phase 8 Group B — A2A URL Validator."""

from __future__ import annotations

import pytest

from backend.a2a.exceptions import A2AValidationError
from backend.a2a.url_validator import validate_a2a_url


class TestValidURLs:
    def test_http_url(self):
        assert validate_a2a_url("http://example.com") == "http://example.com"

    def test_https_url(self):
        assert validate_a2a_url("https://example.com") == "https://example.com"

    def test_https_with_path(self):
        assert validate_a2a_url("https://example.com/a2a") == "https://example.com/a2a"

    def test_public_ip(self):
        assert validate_a2a_url("http://8.8.8.8") == "http://8.8.8.8"

    def test_domain_with_port(self):
        assert validate_a2a_url("https://agent.example.com:8080") == "https://agent.example.com:8080"


class TestPrivateIPsBlocked:
    def test_10_x(self):
        with pytest.raises(A2AValidationError, match="Private IP"):
            validate_a2a_url("http://10.0.0.1")

    def test_192_168_x(self):
        with pytest.raises(A2AValidationError, match="Private IP"):
            validate_a2a_url("http://192.168.1.1")

    def test_127_x(self):
        with pytest.raises(A2AValidationError, match="Private IP"):
            validate_a2a_url("http://127.0.0.1")

    def test_ipv6_loopback(self):
        with pytest.raises(A2AValidationError, match="Private IP"):
            validate_a2a_url("http://[::1]")

    def test_private_allowed(self):
        result = validate_a2a_url("http://192.168.1.1", allow_private_ips=True)
        assert result == "http://192.168.1.1"


class TestInvalidSchemes:
    def test_file_scheme(self):
        with pytest.raises(A2AValidationError, match="Invalid URL scheme"):
            validate_a2a_url("file:///etc/passwd")

    def test_ftp_scheme(self):
        with pytest.raises(A2AValidationError, match="Invalid URL scheme"):
            validate_a2a_url("ftp://example.com")

    def test_javascript_scheme(self):
        with pytest.raises(A2AValidationError, match="Invalid URL scheme"):
            validate_a2a_url("javascript:alert(1)")


class TestMalformedURLs:
    def test_no_hostname(self):
        with pytest.raises(A2AValidationError):
            validate_a2a_url("http://")
