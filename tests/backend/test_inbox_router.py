"""Tests for backend/api/routers/inbox.py — Case-Space Inbox API.

Phase 2 of plans/2026-06-14_case-space-workspace.md.  Covers:

  * feature-gate (404 while disabled)
  * GET /api/v1/inbox?tenant_id=…  → InboxSummary with kinds
  * POST /api/v1/inbox/bulk-move   → InboxBulkResult (incl. cross-tenant rejection)
  * POST /api/v1/inbox/bulk-tag    → InboxBulkResult (incl. empty-tag no-op)
  * POST /api/v1/inbox/bulk-delete  → InboxBulkResult (soft-delete)
 * POST /api/v1/inbox/bulk-archive → DEPRECATED alias of /bulk-delete

The router is feature-gated by ``settings.enable_case_space_inbox``;
while the flag is False all endpoints return 404.  We toggle via
``monkeypatch`` on the imported module reference (mirrors the
workspace test pattern).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.api.routers import inbox as inbox_module
from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the inbox feature flag on for the duration of the test."""
    monkeypatch.setattr(inbox_module.settings, "enable_case_space_inbox", True)


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the inbox feature flag off for the duration of the test.

    Case-Space Inbox is ON by default (P2 default was reversed — the
    feature is no longer hidden behind an env-var gate).  Tests that
    verify the 404-on-disabled behaviour must opt in explicitly.
    """
    monkeypatch.setattr(inbox_module.settings, "enable_case_space_inbox", False)


# Feature gate tests below
# ---------------------------------------------------------------------------


def test_inbox_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.get("/api/v1/inbox", params={"tenant_id": "t1"})
    assert response.status_code == 404
    assert "DANWA_ENABLE_CASE_SPACE_INBOX" in response.json()["detail"]


def test_bulk_move_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.post(
        "/api/v1/inbox/bulk-move",
        json={"debate_ids": ["d1"], "target_case_id": "c1"},
    )
    assert response.status_code == 404


def test_bulk_tag_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.post(
        "/api/v1/inbox/bulk-tag",
        json={"debate_ids": ["d1"], "tag_ids": ["a"]},
    )
    assert response.status_code == 404


def test_bulk_delete_returns_404_when_feature_disabled(client: TestClient, disabled: None) -> None:
    response = client.post(
        "/api/v1/inbox/bulk-archive",
        json={"debate_ids": ["d1"]},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# /api/v1/inbox
# ---------------------------------------------------------------------------


def test_inbox_returns_empty_when_no_cases(client: TestClient, enabled: None) -> None:
    empty_store = mock.MagicMock()
    empty_store.list_by_tenant.return_value = []
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: empty_store
    try:
        response = client.get("/api/v1/inbox", params={"tenant_id": "t-empty"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "t-empty"
    assert body["items"] == []
    assert body["counts"] == {}
    assert body["is_all_clear"] is True


def test_inbox_emits_untagged_kinds(client: TestClient, enabled: None) -> None:
    """A debate with no tags must surface as ``untagged`` regardless of status."""

    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="Case", tags=[])
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [case_obj]

    fake_store = mock.MagicMock()
    fake_store.list_by_status.return_value = []
    fake_store.list_all.return_value = [
        {
            "debate_id": "d-no-tags",
            "status": "running",
            "tags": [],
            "topic": "No tags debate",
            "updated_at": "2026-06-01T00:00:00+00:00",
        },
        {
            "debate_id": "d-with-tags",
            "status": "running",
            "tags": ["ethics"],
            "topic": "Tagged debate",
            "updated_at": "2026-06-01T00:00:00+00:00",
        },
    ]

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.get("/api/v1/inbox", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    kinds = {it["kind"] for it in body["items"]}
    assert "untagged" in kinds
    assert body["is_all_clear"] is False


def test_inbox_emits_recently_completed_within_7_days(client: TestClient, enabled: None) -> None:
    from datetime import UTC, datetime, timedelta

    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="Case", tags=[])
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [case_obj]

    recent = (datetime.now(UTC) - timedelta(days=2)).isoformat()
    old = (datetime.now(UTC) - timedelta(days=30)).isoformat()

    fake_store = mock.MagicMock()
    fake_store.list_by_status.side_effect = lambda status: (
        [
            {
                "debate_id": "d-fresh",
                "status": "completed",
                "tags": ["a"],
                "topic": "Fresh",
                "completed_at": recent,
            },
            {
                "debate_id": "d-stale",
                "status": "completed",
                "tags": ["a"],
                "topic": "Stale",
                "completed_at": old,
            },
        ]
        if status == "completed"
        else []
    )
    fake_store.list_all.return_value = []

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.get("/api/v1/inbox", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    body = response.json()
    recently_completed_ids = [it["id"] for it in body["items"] if it["kind"] == "recently_completed"]
    assert "d-fresh" in recently_completed_ids
    assert "d-stale" not in recently_completed_ids


def test_inbox_emits_stale_running_over_24h(client: TestClient, enabled: None) -> None:
    from datetime import UTC, datetime, timedelta

    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="Case", tags=[])
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [case_obj]

    stale_ts = (datetime.now(UTC) - timedelta(hours=48)).isoformat()
    fresh_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    fake_store = mock.MagicMock()
    fake_store.list_by_status.side_effect = lambda status: (
        [
            {
                "debate_id": "d-stale",
                "status": "running",
                "tags": [],
                "topic": "Stuck",
                "updated_at": stale_ts,
            },
            {
                "debate_id": "d-fresh",
                "status": "running",
                "tags": [],
                "topic": "Fresh run",
                "updated_at": fresh_ts,
            },
        ]
        if status == "running"
        else []
    )
    fake_store.list_all.return_value = []

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.get("/api/v1/inbox", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    body = response.json()
    stale_ids = [it["id"] for it in body["items"] if it["kind"] == "stale_running"]
    assert "d-stale" in stale_ids
    assert "d-fresh" not in stale_ids


# ---------------------------------------------------------------------------
# /api/v1/inbox/bulk-move
# ---------------------------------------------------------------------------


def test_bulk_move_rejects_cross_tenant(client: TestClient, enabled: None) -> None:
    """A debate in tenant A cannot be moved into a case in tenant B."""
    case_a = SimpleNamespace(id="c-a", tenant_id="t-a", title="A", tags=[])
    case_b = SimpleNamespace(id="c-b", tenant_id="t-b", title="B", tags=[])
    case_store = mock.MagicMock()
    case_store.list_by_tenant.side_effect = lambda tid: [case_a] if tid == "t-a" else [case_b]
    case_store.get.side_effect = lambda tid, cid: case_a if (tid == "t-a" and cid == "c-a") else case_b if (tid == "t-b" and cid == "c-b") else None
    # Make _known_tenants_via_case_store return both tenants
    case_store._cache = {"t-a": {}, "t-b": {}}

    fake_store_a = mock.MagicMock()
    fake_store_a.get.return_value = {
        "debate_id": "d-cross",
        "status": "running",
        "tags": [],
        "topic": "Cross tenant",
    }
    fake_store_b = mock.MagicMock()
    fake_store_b.get.return_value = None

    def _store_for(case_id):
        return fake_store_a if case_id == "c-a" else fake_store_b

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", side_effect=_store_for):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-move",
                json={"debate_ids": ["d-cross"], "target_case_id": "c-b"},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == []
    assert len(body["failed"]) == 1
    assert body["failed"][0]["id"] == "d-cross"
    assert "cross_tenant" in body["failed"][0]["reason"]


def test_bulk_move_404_for_missing_target_case(client: TestClient, enabled: None) -> None:
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = None

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    try:
        response = client.post(
            "/api/v1/inbox/bulk-move",
            json={"debate_ids": ["d1"], "target_case_id": "missing"},
        )
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 404
    assert "missing" in response.json()["detail"]


def test_bulk_move_calls_store_move(client: TestClient, enabled: None) -> None:
    case_a = SimpleNamespace(id="c-a", tenant_id="t1", title="A", tags=[])
    case_b = SimpleNamespace(id="c-b", tenant_id="t1", title="B", tags=[])
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.side_effect = lambda tid, cid: case_a if cid == "c-a" else case_b if cid == "c-b" else None
    case_store.list_by_tenant.return_value = [case_a, case_b]

    src_store = mock.MagicMock()
    src_store.get.return_value = {
        "debate_id": "d1",
        "status": "running",
        "tags": [],
        "topic": "Move me",
    }
    src_store.move.return_value = True
    tgt_store = mock.MagicMock()

    with mock.patch(
        "backend.api.routers.inbox.get_debate_store_for_case",
        side_effect=lambda cid: src_store if cid == "c-a" else tgt_store,
    ):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-move",
                json={"debate_ids": ["d1"], "target_case_id": "c-b"},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == ["d1"]
    assert body["failed"] == []
    src_store.move.assert_called_once_with("d1", tgt_store)


# ---------------------------------------------------------------------------
# /api/v1/inbox/bulk-tag
# ---------------------------------------------------------------------------


def test_bulk_tag_empty_tag_ids_is_noop(client: TestClient, enabled: None) -> None:
    """An empty tag list is a 200 with all ids in ``succeeded``, not a 400."""
    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="C", tags=[])
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = case_obj
    case_store.list_by_tenant.return_value = [case_obj]

    fake_store = mock.MagicMock()
    fake_store.get.return_value = {
        "debate_id": "d1",
        "status": "running",
        "tags": ["a"],
        "topic": "T",
    }
    fake_store.put = mock.MagicMock()

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-tag",
                json={"debate_ids": ["d1"], "tag_ids": []},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == ["d1"]
    # put is still called once to persist the (unchanged) tag list
    fake_store.put.assert_called_once()


def test_bulk_tag_unions_existing(client: TestClient, enabled: None) -> None:
    """Existing tags are kept; new tags are added (idempotent union)."""
    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="C", tags=[])
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = case_obj
    case_store.list_by_tenant.return_value = [case_obj]

    fake_store = mock.MagicMock()
    fake_store.get.return_value = {
        "debate_id": "d1",
        "status": "running",
        "tags": ["existing"],
        "topic": "T",
    }
    fake_store.put = mock.MagicMock()

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-tag",
                json={"debate_ids": ["d1"], "tag_ids": ["new", "existing"]},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == ["d1"]
    # The persisted debate dict should have the union
    persisted = fake_store.put.call_args[0][1]
    assert set(persisted["tags"]) == {"existing", "new"}


# ---------------------------------------------------------------------------
# /api/v1/inbox/bulk-archive
# ---------------------------------------------------------------------------


def test_bulk_delete_flips_status(client: TestClient, enabled: None) -> None:
    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="C", tags=[])
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = case_obj
    case_store.list_by_tenant.return_value = [case_obj]

    fake_store = mock.MagicMock()
    fake_store.get.return_value = {
        "debate_id": "d1",
        "status": "completed",
        "tags": [],
        "topic": "Archive me",
    }
    fake_store.put = mock.MagicMock()

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-archive",
                json={"debate_ids": ["d1"]},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == ["d1"]
    persisted = fake_store.put.call_args[0][1]
    # Phase 2.8 visual revision: the Inbox row's Delete button
    # sets status='deleted' (was 'archived').  We keep archived_at
    # as a mirror field for backward-compat with audit tooling.
    assert persisted["status"] == "deleted"
    assert "deleted_at" in persisted
    assert "archived_at" in persisted


# /api/v1/inbox/bulk-delete (canonical)
# ---------------------------------------------------------------------------


def test_bulk_delete_canonical_flips_status(
    client: TestClient,
    enabled: None,
) -> None:
    """The canonical /inbox/bulk-delete endpoint sets
    status='deleted' on the listed debates."""
    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="C", tags=[])
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = case_obj
    case_store.list_by_tenant.return_value = [case_obj]

    fake_store = mock.MagicMock()
    fake_store.get.return_value = {
        "debate_id": "d1",
        "status": "completed",
        "tags": [],
        "topic": "Delete me",
    }
    fake_store.put = mock.MagicMock()

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-delete",
                json={"debate_ids": ["d1"]},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == ["d1"]
    persisted = fake_store.put.call_args[0][1]
    assert persisted["status"] == "deleted"
    assert "deleted_at" in persisted
    assert "archived_at" in persisted  # mirror for backward compat


def test_bulk_delete_canonical_returns_404_when_feature_disabled(
    client: TestClient,
    disabled: None,
) -> None:
    response = client.post(
        "/api/v1/inbox/bulk-delete",
        json={"debate_ids": ["d1"]},
    )
    assert response.status_code == 404


# /api/v1/inbox/bulk-archive (deprecated alias — kept for backward compat)
# ---------------------------------------------------------------------------


def test_bulk_archive_legacy_alias_still_works(
    client: TestClient,
    enabled: None,
) -> None:
    """The legacy /inbox/bulk-archive endpoint remains callable
    and produces the same effect as /bulk-delete."""
    case_obj = SimpleNamespace(id="c1", tenant_id="t1", title="C", tags=[])
    case_store = mock.MagicMock()
    case_store._cache = {"t1": {}}
    case_store.get.return_value = case_obj
    case_store.list_by_tenant.return_value = [case_obj]

    fake_store = mock.MagicMock()
    fake_store.get.return_value = {
        "debate_id": "d-legacy",
        "status": "completed",
        "tags": [],
        "topic": "Legacy archive endpoint",
    }
    fake_store.put = mock.MagicMock()

    with mock.patch("backend.api.routers.inbox.get_debate_store_for_case", return_value=fake_store):
        from backend.api.deps import get_case_store

        app.dependency_overrides[get_case_store] = lambda: case_store
        try:
            response = client.post(
                "/api/v1/inbox/bulk-archive",
                json={"debate_ids": ["d-legacy"]},
            )
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] == ["d-legacy"]
    persisted = fake_store.put.call_args[0][1]
    assert persisted["status"] == "deleted"  # same effect as canonical
