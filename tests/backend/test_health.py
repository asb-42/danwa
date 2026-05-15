"""Tests for the /health endpoint."""

from __future__ import annotations


def test_health_returns_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health_version_matches(client):
    response = client.get("/health")
    data = response.json()
    assert data["version"] == "1.1.0"
