"""Tests for Phase 8 Group B — A2A URL Validator."""

from __future__ import annotations

import socket
from unittest.mock import patch

import pytest

from backend.a2a.exceptions import A2AValidationError
from backend.a2a.url_validator import validate_a2a_url


def _mock_addrinfo_public(*ips: str):
    """Return a stub socket.getaddrinfo that yields the given public IPs.

    Each IP is wrapped in the ``(family, type, proto, canon, sockaddr)``
    5-tuple that ``getaddrinfo`` normally returns. We use ``AF_INET`` for
    simplicity; the validator only inspects ``sockaddr[0]``.
    """

    def _fake(host, port, *args, **kwargs):  # noqa: ARG001
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in ips]

    return _fake


def _mock_addrinfo_fail(*_args, **_kwargs):
    raise socket.gaierror("Name or service not known")


class TestValidURLs:
    def test_http_url(self):
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("93.184.216.34")):
            assert validate_a2a_url("http://example.com") == "http://example.com"

    def test_https_url(self):
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("93.184.216.34")):
            assert validate_a2a_url("https://example.com") == "https://example.com"

    def test_https_with_path(self):
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("93.184.216.34")):
            assert validate_a2a_url("https://example.com/a2a") == "https://example.com/a2a"

    def test_public_ip(self):
        # Literal public IP — does not go through DNS.
        assert validate_a2a_url("http://8.8.8.8") == "http://8.8.8.8"

    def test_domain_with_port(self):
        # P3.1 — the validator now resolves hostnames; mock DNS to return a
        # public address so the test is hermetic and does not depend on
        # the real ``agent.example.com`` record.
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("93.184.216.34")):
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

    def test_hostname_resolves_to_private_ip(self):
        # P3.1 — DNS-resolution SSRF defence.
        # The literal hostname is fine, but if it resolves to 10.x, we
        # must block the URL.
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("10.0.0.5")):
            with pytest.raises(A2AValidationError, match="resolves to a private IP"):
                validate_a2a_url("https://internal.example.com")

    def test_hostname_resolves_to_loopback(self):
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("127.0.0.1")):
            with pytest.raises(A2AValidationError, match="resolves to a private IP"):
                validate_a2a_url("https://localhost.example.com")

    def test_dns_resolution_failure(self):
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_fail):
            with pytest.raises(A2AValidationError, match="DNS resolution failed"):
                validate_a2a_url("https://does-not-exist.invalid")

    def test_hostname_resolves_to_public_ip_passes(self):
        with patch("backend.a2a.url_validator.socket.getaddrinfo", _mock_addrinfo_public("1.1.1.1")):
            assert validate_a2a_url("https://public.example.com") == "https://public.example.com"


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
