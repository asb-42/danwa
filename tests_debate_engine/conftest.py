"""Shared test fixtures for debate_engine tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from debate_engine.api.deps import get_audit_service, get_settings
from debate_engine.core.config import Settings
from debate_engine.main import create_app
from debate_engine.persistence.audit import AuditService


@pytest.fixture()
def settings(tmp_path) -> Settings:
    """Test settings with temporary database path."""
    return Settings(
        db_path=tmp_path / "test_audit.db",
        cors_origins=["http://testserver"],
        debug=True,
    )


@pytest.fixture()
def audit_service(tmp_path) -> AuditService:
    """Isolated AuditService with temp database."""
    return AuditService(db_path=tmp_path / "test_audit.db")


@pytest.fixture()
def app(settings, audit_service):
    """FastAPI app with overridden dependencies."""
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    return application


@pytest.fixture()
def client(app) -> TestClient:
    """Synchronous test client."""
    return TestClient(app)
