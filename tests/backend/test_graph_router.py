"""Tests for backend/api/routers/graph.py — Case-Space Knowledge Graph API.

Phase 4 of plans/2026-06-14_case-space-workspace.md (Anhang A).

Covers the three endpoints:

  GET /api/v1/graph/local?entity_type=…&entity_id=…&hops=1   → GraphPayload
  GET /api/v1/graph/global?tenant_id=…&filters=…             → GraphPayload
  GET /api/v1/graph/edges?src=…&tgt=…                        → EdgeDetail
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.api.routers import graph as graph_module
from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(graph_module.settings, "enable_case_space_graph", True)


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the graph feature flag off for the duration of the test."""
    monkeypatch.setattr(graph_module.settings, "enable_case_space_graph", False)


# ---------------------------------------------------------------------------
# Feature gate
# ---------------------------------------------------------------------------


def test_local_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.get(
        "/api/v1/graph/local",
        params={"entity_type": "case", "entity_id": "c1"},
    )
    assert response.status_code == 404
    assert "DANWA_ENABLE_CASE_SPACE_GRAPH" in response.json()["detail"]


def test_global_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.get("/api/v1/graph/global", params={"tenant_id": "t1"})
    assert response.status_code == 404


def test_edges_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.get(
        "/api/v1/graph/edges",
        params={"src": "case:c1", "tgt": "case:c2"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/v1/graph/local
# ---------------------------------------------------------------------------


def test_local_returns_empty_when_case_not_found(client: TestClient, enabled: None) -> None:
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = None
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    try:
        response = client.get(
            "/api/v1/graph/local",
            params={"entity_type": "case", "entity_id": "missing"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 404


def test_local_returns_centre_node_with_debates_and_tags(client: TestClient, enabled: None) -> None:
    case = SimpleNamespace(
        id="c1",
        tenant_id="t1",
        title="AI Ethics",
        status="active",
        tags=["ethics", "research"],
    )
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = case

    debate_store = mock.MagicMock()
    debate_store.list_all.return_value = [
        {"debate_id": "d1", "status": "completed", "topic": "T1"},
        {"debate_id": "d2", "status": "running", "topic": "T2"},
    ]

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.deps.get_debate_store_for_case",
        return_value=debate_store,
    ):
        try:
            response = client.get(
                "/api/v1/graph/local",
                params={"entity_type": "case", "entity_id": "c1"},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    node_ids = {n["id"] for n in body["nodes"]}
    assert "case:c1" in node_ids
    assert "debate:d1" in node_ids
    assert "debate:d2" in node_ids
    assert "tag:ethics" in node_ids
    assert "tag:research" in node_ids
    # Edges: case→debate (2x) + case→tag (2x) = 4
    edge_pairs = {(e["src"], e["tgt"]) for e in body["edges"]}
    assert ("case:c1", "debate:d1") in edge_pairs
    assert ("case:c1", "debate:d2") in edge_pairs
    assert ("case:c1", "tag:ethics") in edge_pairs
    assert ("case:c1", "tag:research") in edge_pairs
    assert body["truncated"] is False
    assert body["total_count"] == 5


def test_local_rejects_unknown_entity_type(client: TestClient, enabled: None) -> None:
    response = client.get(
        "/api/v1/graph/local",
        params={"entity_type": "alien", "entity_id": "x1"},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/v1/graph/global
# ---------------------------------------------------------------------------


def test_global_returns_empty_for_unknown_tenant(client: TestClient, enabled: None) -> None:
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = []
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    try:
        response = client.get("/api/v1/graph/global", params={"tenant_id": "t-unknown"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["nodes"] == []
    assert body["edges"] == []
    assert body["truncated"] is False
    assert body["total_count"] == 0


def test_global_aggregates_cases_with_shared_tags(client: TestClient, enabled: None) -> None:
    """Tags that appear in multiple cases must be deduped in the node set."""
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [
        SimpleNamespace(id="c1", tenant_id="t1", title="C1", status="active", tags=["ethics"]),
        SimpleNamespace(id="c2", tenant_id="t1", title="C2", status="active", tags=["ethics"]),
    ]
    debate_store = mock.MagicMock()
    debate_store.list_all.return_value = []

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.deps.get_debate_store_for_case",
        return_value=debate_store,
    ):
        try:
            response = client.get("/api/v1/graph/global", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    body = response.json()
    # Two case nodes + one (deduped) tag node = 3
    tag_nodes = [n for n in body["nodes"] if n["id"] == "tag:ethics"]
    assert len(tag_nodes) == 1
    # But two edges: c1→tag and c2→tag
    tag_edges = [e for e in body["edges"] if e["tgt"] == "tag:ethics"]
    assert len(tag_edges) == 2


def test_global_caps_at_limit_and_sets_truncated(client: TestClient, enabled: None) -> None:
    big_cases = [SimpleNamespace(id=f"c{i}", tenant_id="t1", title=f"C{i}", status="active", tags=[]) for i in range(10)]
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = big_cases
    debate_store = mock.MagicMock()
    debate_store.list_all.return_value = []

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.deps.get_debate_store_for_case",
        return_value=debate_store,
    ):
        try:
            response = client.get(
                "/api/v1/graph/global",
                params={"tenant_id": "t1", "limit": 3},
            )
        finally:
            app.dependency_overrides = {}

    body = response.json()
    # Only 3 case nodes should be in the response
    case_node_count = sum(1 for n in body["nodes"] if n["type"] == "Case")
    assert case_node_count == 3
    assert body["truncated"] is True
    assert body["total_count"] == 10
    assert body["sampled_count"] == 3


def test_global_rejects_limit_out_of_range(client: TestClient, enabled: None) -> None:
    response = client.get(
        "/api/v1/graph/global",
        params={"tenant_id": "t1", "limit": 0},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# /api/v1/graph/edges  (Phase 4.3/5.2 - graph_edge_cache)
# ---------------------------------------------------------------------------


def test_edges_without_case_id_returns_placeholder(client: TestClient, enabled: None) -> None:
    """No case_id supplied -> router cannot resolve a tenant and
    returns a soft placeholder instead of an error."""
    response = client.get(
        "/api/v1/graph/edges",
        params={"src": "case:c1", "tgt": "tag:ethics"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["src"] == "case:c1"
    assert body["tgt"] == "tag:ethics"
    assert body["weight"] == 1.0
    # No audit events in the test DB -> placeholder is returned
    assert any("not yet materialised" in e for e in body["evidence"])


def test_edges_with_unknown_case_id_returns_placeholder(client: TestClient, enabled: None) -> None:
    """case_id is provided but does not resolve to any known
    case (case_store cache is empty in tests).  Router falls
    back to the same soft placeholder as the no-case-id path."""
    response = client.get(
        "/api/v1/graph/edges",
        params={"src": "case:c1", "tgt": "tag:ethics", "case_id": "missing"},
    )
    assert response.status_code == 200
    body = response.json()
    assert any("not yet materialised" in e for e in body["evidence"])


def test_edges_validation_422(client: TestClient, enabled: None) -> None:
    """Empty src/tgt are rejected by the Query validation."""
    response = client.get("/api/v1/graph/edges", params={"src": "", "tgt": "x"})
    assert response.status_code == 422


# ─── Phase 2.8: tag-id -> name resolution (TagStore lookup) ─────


def test_global_graph_resolves_tag_ids_to_names(client: TestClient, enabled: None, monkeypatch) -> None:
    """The graph endpoints store tag IDs (UUIDs) in case.tags and
    must resolve them to the human-readable tag name before
    sending them to the BrowseView.  Without this, the
    BrowseView lists tag rows by their raw UUID, which is
    unreadable."""
    # 1) Mock the TagStore so the test does not depend on the
    #    real file-backed TagStore contents
    from backend.persistence.tag_store import TagStore

    class FakeTag:
        def __init__(self, name):
            self.name = name

    def fake_load(self, tenant_id):
        return {
            "fake-tag-uuid-1": FakeTag("Science"),
            "fake-tag-uuid-2": FakeTag("Ethics"),
        }

    monkeypatch.setattr(TagStore, "_load_tenant", fake_load)

    # 2) Build a fake case_store that returns one case with
    #    two tag UUIDs
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from backend.api.deps import get_case_store

    case_obj = SimpleNamespace(
        id="case-fake",
        tenant_id="t-fake",
        title="Fake Case",
        status="active",
        tags=["fake-tag-uuid-1", "fake-tag-uuid-2"],
    )
    case_store = MagicMock()
    case_store._cache = {"t-fake": {}}
    case_store.get.return_value = case_obj
    case_store.list_by_tenant.return_value = [case_obj]
    app.dependency_overrides[get_case_store] = lambda: case_store
    try:
        r = client.get("/api/v1/graph/global?tenant_id=t-fake&limit=10")
    finally:
        app.dependency_overrides = {}
    assert r.status_code == 200
    payload = r.json()
    tag_nodes = {n["id"]: n["label"] for n in payload["nodes"] if n["type"] == "Tag"}
    # Both tag UUIDs must resolve to their human names
    assert tag_nodes.get("tag:fake-tag-uuid-1") == "Science"
    assert tag_nodes.get("tag:fake-tag-uuid-2") == "Ethics"
