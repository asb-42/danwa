"""Tests for backend/api/routers/workspace.py — Case-Space Workspace API.

These tests cover the two Phase-1 endpoints introduced in
``plans/2026-06-14_case-space-workspace.md``:

  * ``GET /api/v1/workspace/summary?case_id=…`` → WorkspaceSummary
  * ``GET /api/v1/cases/search?q=…``             → list[CaseSearchHit]

The router is feature-gated by ``settings.enable_case_space``; while the
flag is False both endpoints return 404.  We toggle the flag via
``monkeypatch`` on the imported module reference.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.api.routers import workspace as workspace_module
from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the feature flag on for the duration of the test."""
    monkeypatch.setattr(workspace_module.settings, "enable_case_space", True)


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the feature flag off for the duration of the test.

    Case-Space is ON by default (P1+P2 default was reversed — the
    feature is no longer hidden behind an env-var gate).  Tests that
    verify the 404-on-disabled behaviour must opt in explicitly.
    """
    monkeypatch.setattr(workspace_module.settings, "enable_case_space", False)


@pytest.fixture
def fake_case_store():
    """Replace the case store dependency with a deterministic stub."""

    class _Stub:
        def get(self, case_id: str):
            if case_id == "missing":
                return None
            return SimpleNamespace(
                id=case_id,
                tenant_id="t1",
                title=f"Case {case_id}",
                description="desc",
                status="active",
                tags=["ethics", "research"],
                members=["alice"],
                debate_ids=["d1", "d2"],
                document_ids=["doc1"],
            )

        def list(self):
            return [
                SimpleNamespace(
                    id="c1",
                    tenant_id="t1",
                    title="AI Ethics Research",
                    status="active",
                    tags=["ethics"],
                ),
                SimpleNamespace(
                    id="c2",
                    tenant_id="t1",
                    title="Legal Review",
                    status="archived",
                    tags=["legal"],
                ),
            ]

    return _Stub()


# ---------------------------------------------------------------------------
# Feature gate
# ---------------------------------------------------------------------------


def test_summary_returns_404_when_feature_disabled(
    client: TestClient, disabled: None
) -> None:
    response = client.get("/api/v1/workspace/summary", params={"case_id": "c1"})
    assert response.status_code == 404
    assert "DANWA_ENABLE_CASE_SPACE" in response.json()["detail"]


def test_search_returns_404_when_feature_disabled(
    client: TestClient, disabled: None
) -> None:
    response = client.get("/api/v1/cases/search", params={"q": "ai"})
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/v1/workspace/summary
# ---------------------------------------------------------------------------


def test_summary_returns_payload_when_enabled(client: TestClient, enabled: None, fake_case_store) -> None:
    app.dependency_overrides = {}
    # Wire the fake store into the dependency injection
    from backend.api.deps import get_case_store
    from backend.api.routers.workspace import get_workspace_summary  # noqa: F401

    app.dependency_overrides[get_case_store] = lambda: fake_case_store
    try:
        response = client.get("/api/v1/workspace/summary", params={"case_id": "c1"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == "c1"
    assert body["tenant_id"] == "t1"
    assert body["title"] == "Case c1"
    assert body["debate_count"] == 2
    assert body["document_count"] == 1
    assert "ethics" in body["tags"]
    assert "recent_events" in body
    assert isinstance(body["suggested_next_steps"], list)
    assert "generated_at" in body


def test_summary_returns_404_for_missing_case(client: TestClient, enabled: None, fake_case_store) -> None:
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: fake_case_store
    try:
        response = client.get("/api/v1/workspace/summary", params={"case_id": "missing"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_summary_emits_suggested_steps_for_empty_case(client: TestClient, enabled: None) -> None:
    """A case with zero debates and zero documents gets two suggestions."""

    empty_store = mock.MagicMock()
    empty_store.get.return_value = SimpleNamespace(
        id="c-empty",
        tenant_id="t1",
        title="Empty",
        description=None,
        status="active",
        tags=[],
        members=[],
        debate_ids=[],
        document_ids=[],
    )
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: empty_store
    try:
        response = client.get("/api/v1/workspace/summary", params={"case_id": "c-empty"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    kinds = {s["kind"] for s in response.json()["suggested_next_steps"]}
    assert "no_documents" in kinds
    assert "no_debates" in kinds


# ---------------------------------------------------------------------------
# /api/v1/cases/search
# ---------------------------------------------------------------------------


def test_search_returns_hits_by_title(client: TestClient, enabled: None, fake_case_store) -> None:
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: fake_case_store
    try:
        response = client.get("/api/v1/cases/search", params={"q": "ai"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["case_id"] == "c1"
    assert body[0]["title"] == "AI Ethics Research"


def test_search_returns_hits_by_tag(client: TestClient, enabled: None, fake_case_store) -> None:
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: fake_case_store
    try:
        response = client.get("/api/v1/cases/search", params={"q": "legal"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["case_id"] == "c2"


def test_search_respects_limit(client: TestClient, enabled: None) -> None:
    big_store = mock.MagicMock()
    big_store.list.return_value = [SimpleNamespace(id=f"c{i}", tenant_id="t1", title=f"Case {i}", status="active", tags=[]) for i in range(50)]
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: big_store
    try:
        response = client.get("/api/v1/cases/search", params={"q": "case", "limit": 3})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_search_empty_query_returns_empty(client: TestClient, enabled: None) -> None:
    """An empty or whitespace-only query must return 200 with an empty list,
    not 422 — the endpoint exists for typeahead UX and must be robust.
    """
    big_store = mock.MagicMock()
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: big_store
    try:
        response = client.get("/api/v1/cases/search", params={"q": "   "})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == []
    big_store.list.assert_not_called()


def test_search_handles_store_failure_gracefully(client: TestClient, enabled: None) -> None:
    """If the underlying store raises, the endpoint must return 200 with []."""
    failing_store = mock.MagicMock()
    failing_store.list.side_effect = RuntimeError("db down")
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: failing_store
    try:
        response = client.get("/api/v1/cases/search", params={"q": "anything"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json() == []
