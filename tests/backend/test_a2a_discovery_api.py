"""Tests for Phase 8 Group D — A2A Discovery API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture()
def app():
    return create_app()


@pytest.fixture()
def client(app):
    return TestClient(app)


class TestDiscoverEndpoint:
    def test_invalid_url_returns_400(self, client):
        resp = client.post("/api/v1/a2a/discover", json={"endpoint_url": "not-a-url"})
        assert resp.status_code == 400  # URL validation error

    def test_file_scheme_returns_400(self, client):
        resp = client.post("/api/v1/a2a/discover", json={"endpoint_url": "file:///etc/passwd"})
        assert resp.status_code == 400

    def test_private_ip_returns_403(self, client):
        resp = client.post("/api/v1/a2a/discover", json={"endpoint_url": "http://192.168.1.1"})
        assert resp.status_code == 403

    def test_unreachable_returns_502(self, client):
        resp = client.post("/api/v1/a2a/discover", json={"endpoint_url": "http://192.0.2.1:9999"})
        # 502 or 504 depending on whether it's a connection error or timeout
        assert resp.status_code in (502, 504)


class TestCapabilitiesEndpoint:
    def test_store_capabilities_nonexistent_profile(self, client):
        resp = client.post(
            "/api/v1/a2a/capabilities/nonexistent",
            json={"capabilities": {"name": "Test"}},
        )
        assert resp.status_code == 404
