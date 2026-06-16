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
        def get(self, tenant_id: str, case_id: str):
            # Mirrors the real CaseStore.get signature: (tenant_id, case_id)
            if case_id == "missing":
                return None
            return SimpleNamespace(
                id=case_id,
                tenant_id=tenant_id,
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


def test_summary_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.get("/api/v1/workspace/summary", params={"case_id": "c1"})
    assert response.status_code == 404
    assert "DANWA_ENABLE_CASE_SPACE" in response.json()["detail"]


def test_search_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
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
        # X-Tenant-Id header is honoured by get_active_tenant; the
        # fake stub's get() returns tenant_id="t1" for any caller,
        # so the response body["tenant_id"] == "t1" assertion
        # requires us to send the matching header.
        response = client.get(
            "/api/v1/workspace/summary",
            params={"case_id": "c1"},
            headers={"X-Tenant-Id": "t1"},
        )
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


# ---------------------------------------------------------------------------
# Bug D (2026-06-16) — workspace/summary must use the tenant-scoped debate
# store, not the legacy project-scoped one with cross-tenant filesystem scan.
# ---------------------------------------------------------------------------
#
# The pre-fix route called ``get_debate_store_for_case(case.id)`` which
# searches the project store first, then walks every tenant dir looking
# for ``<case_id>`` and uses the first match.  This led to two symptoms:
#
#   1. Cases in a non-default tenant got ``debate_count = 0`` because
#      the filesystem scan did not find a ``debates/`` subdir under
#      the wrong tenant.
#   2. (Worse) Cross-tenant leak: a case with the same id in two
#      tenants could pick up the other tenant's debate count.
#
# These tests build a minimal FastAPI app with a real CaseStore so the
# tenant-scoped debate directory is the *only* valid path.  They fail
# with the pre-fix route (``debate_count=0``) and pass once the route
# is switched to ``_get_debate_store_for_case(tenant, case, store)``.


class TestWorkspaceSummaryDebateCountTenantScoped:
    """Pin down that the summary endpoint counts debates via the
    tenant-scoped store, not via a cross-tenant filesystem walk.
    """

    def _seed_debate(self, case_dir, debate_id: str, **overrides) -> None:
        """Persist a debate JSON file in the case's tenant-scoped debates dir."""
        import json
        from backend.persistence.debate_store import DebateStore

        store = DebateStore(data_dir=case_dir / "debates")
        payload = {
            "debate_id": debate_id,
            "status": "completed",
            "title": overrides.get("title", f"Debate {debate_id}"),
            "request": {"case": {"text": "Sample", "project_id": None}, "language": "de", "max_rounds": 3},
            "max_rounds": 3,
            "current_round": 3,
            "rounds": [],
            "result": None,
            "created_at": "2026-06-16T00:00:00+00:00",
            "updated_at": "2026-06-16T00:00:00+00:00",
        }
        payload.update(overrides)
        store.put(debate_id, payload)

    def test_summary_counts_debates_in_active_tenant(
        self, tmp_path, monkeypatch,
    ):
        """Two debates under ``data/cases/<tenant>/cases/<case>/debates/``
        must surface as ``debate_count == 2``.  The pre-fix code used
        the legacy project-scoped helper and returned 0.
        """
        from fastapi import FastAPI, Header
        from fastapi.testclient import TestClient
        from backend.api.deps import get_active_tenant, get_case_store
        from backend.api.routers.workspace import router as workspace_router
        from backend.persistence.case_store import CaseStore

        case_store = CaseStore(base_dir=tmp_path / "cases_d")
        case_store.create("tenant-A", "X", case_id="case-X", description="")
        case_dir = case_store.get_case_dir("tenant-A", "case-X")
        self._seed_debate(case_dir, "d-1", title="Alpha")
        self._seed_debate(case_dir, "d-2", title="Beta")

        def _active_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
            return x_tenant_id or "tenant-A"

        app = FastAPI()
        app.include_router(workspace_router, prefix="/api/v1")
        app.dependency_overrides[get_active_tenant] = _active_tenant
        app.dependency_overrides[get_case_store] = lambda: case_store
        monkeypatch.setattr(
            "backend.api.routers.workspace.settings.enable_case_space", True,
        )

        with TestClient(app) as tc:
            response = tc.get(
                "/api/v1/workspace/summary",
                params={"case_id": "case-X"},
                headers={"X-Tenant-Id": "tenant-A"},
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["case_id"] == "case-X"
        # The pre-fix code returned 0 because the legacy filesystem
        # scan did not find the tenant-scoped debates/ dir.  After
        # the fix the count must reflect the seeded debates.
        assert body["debate_count"] == 2, (
            f"expected debate_count=2, got {body['debate_count']!r} \u2014 "
            "the workspace route is likely still using the legacy "
            "project-scoped debate store"
        )

    def test_summary_does_not_count_debates_from_other_tenant(
        self, tmp_path, monkeypatch,
    ):
        """Same case_id in two tenants; only the active tenant's
        debates must be counted.  Pre-fix code's filesystem walk
        would return whichever tenant's ``case_dir`` it found first.
        """
        from fastapi import FastAPI, Header
        from fastapi.testclient import TestClient
        from backend.api.deps import get_active_tenant, get_case_store
        from backend.api.routers.workspace import router as workspace_router
        from backend.persistence.case_store import CaseStore

        case_store = CaseStore(base_dir=tmp_path / "cases_dx")
        case_store.create("tenant-A", "A's case", case_id="shared", description="")
        case_store.create("tenant-B", "B's case", case_id="shared", description="")

        # Tenant A: 3 debates.
        for i in range(3):
            self._seed_debate(
                case_store.get_case_dir("tenant-A", "shared"),
                f"a-{i}", title=f"A debate {i}",
            )
        # Tenant B: 1 debate.
        self._seed_debate(
            case_store.get_case_dir("tenant-B", "shared"),
            "b-0", title="B debate 0",
        )

        def _active_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
            return x_tenant_id or "tenant-A"

        app = FastAPI()
        app.include_router(workspace_router, prefix="/api/v1")
        app.dependency_overrides[get_active_tenant] = _active_tenant
        app.dependency_overrides[get_case_store] = lambda: case_store
        monkeypatch.setattr(
            "backend.api.routers.workspace.settings.enable_case_space", True,
        )

        with TestClient(app) as tc:
            # Caller is in tenant-A: must see exactly 3 (NOT 1, not 4).
            response_a = tc.get(
                "/api/v1/workspace/summary",
                params={"case_id": "shared"},
                headers={"X-Tenant-Id": "tenant-A"},
            )
            # Caller is in tenant-B: must see exactly 1.
            response_b = tc.get(
                "/api/v1/workspace/summary",
                params={"case_id": "shared"},
                headers={"X-Tenant-Id": "tenant-B"},
            )

        assert response_a.status_code == 200, response_a.text
        assert response_a.json()["debate_count"] == 3, (
            f"tenant-A: expected 3, got {response_a.json()['debate_count']!r}"
        )
        assert response_b.status_code == 200, response_b.text
        assert response_b.json()["debate_count"] == 1, (
            f"tenant-B: expected 1, got {response_b.json()['debate_count']!r}"
        )
        assert response_b.json()["title"] == "B's case", (
            "tenant-B must see B's case title, not A's"
        )
