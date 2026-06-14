"""Tests for backend/api/routers/onboarding.py — Case-Space Onboarding API.

Phase 3 of plans/2026-06-14_case-space-workspace.md.

Covers the single GET endpoint:

  GET /api/v1/onboarding/state?tenant_id=…  → OnboardingState

The endpoint is best-effort by design: it never raises; if a
store is unavailable the corresponding boolean is False.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# /api/v1/onboarding/state
# ---------------------------------------------------------------------------


def test_onboarding_state_for_empty_tenant(
    client: TestClient,
) -> None:
    """A tenant with no cases must report all three booleans as False."""
    empty_store = mock.MagicMock()
    empty_store.list_by_tenant.return_value = []
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: empty_store
    try:
        response = client.get("/api/v1/onboarding/state", params={"tenant_id": "t-empty"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "t-empty"
    assert body["has_cases"] is False
    assert body["has_documents"] is False
    assert body["has_debates"] is False


def test_onboarding_state_with_cases_no_debates(
    client: TestClient,
) -> None:
    """A tenant with cases but no debates reports has_cases=True, has_debates=False."""
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [
        SimpleNamespace(id="c1", tenant_id="t1"),
    ]
    empty_debate_store = mock.MagicMock()
    empty_debate_store.list_all.return_value = []

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.routers.onboarding.get_debate_store_for_case",
        return_value=empty_debate_store,
    ):
        try:
            response = client.get("/api/v1/onboarding/state", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["has_cases"] is True
    assert body["has_debates"] is False
    assert body["has_documents"] is False  # always False in this scope (project-scoped)


def test_onboarding_state_with_at_least_one_debate(
    client: TestClient,
) -> None:
    """has_debates must be True if any case has at least one debate."""
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [
        SimpleNamespace(id="c1", tenant_id="t1"),
        SimpleNamespace(id="c2", tenant_id="t1"),
    ]
    empty_store = mock.MagicMock()
    empty_store.list_all.return_value = []
    full_store = mock.MagicMock()
    full_store.list_all.return_value = [{"id": "d1"}]

    def _store_for(case_id):
        return full_store if case_id == "c2" else empty_store

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.routers.onboarding.get_debate_store_for_case",
        side_effect=_store_for,
    ):
        try:
            response = client.get("/api/v1/onboarding/state", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    body = response.json()
    assert body["has_cases"] is True
    assert body["has_debates"] is True


def test_onboarding_state_short_circuits_after_first_debate(
    client: TestClient,
) -> None:
    """Once we find one case with a debate, we stop iterating cases."""
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [
        SimpleNamespace(id="c1", tenant_id="t1"),
        SimpleNamespace(id="c2", tenant_id="t1"),
        SimpleNamespace(id="c3", tenant_id="t1"),
    ]
    debate_store_c1 = mock.MagicMock()
    debate_store_c1.list_all.return_value = [{"id": "d1"}]  # first case has a debate
    # c2 and c3 should never be queried

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.routers.onboarding.get_debate_store_for_case",
        return_value=debate_store_c1,
    ) as store_mock:
        try:
            response = client.get("/api/v1/onboarding/state", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    assert response.json()["has_debates"] is True
    # The endpoint should have called the debate store factory only once
    # (for c1) — short-circuit after the first positive match.
    assert store_mock.call_count == 1


def test_onboarding_state_survives_store_failure(
    client: TestClient,
) -> None:
    """If the case store raises, the endpoint must still return a state."""
    failing_store = mock.MagicMock()
    failing_store.list_by_tenant.side_effect = RuntimeError("db down")
    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: failing_store
    try:
        response = client.get("/api/v1/onboarding/state", params={"tenant_id": "t1"})
    finally:
        app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["has_cases"] is False
    assert body["has_debates"] is False


def test_onboarding_state_continues_when_individual_debate_store_fails(
    client: TestClient,
) -> None:
    """A failure for one case's debate store must not break the whole response."""
    case_store = mock.MagicMock()
    case_store.list_by_tenant.return_value = [
        SimpleNamespace(id="c1", tenant_id="t1"),
        SimpleNamespace(id="c2", tenant_id="t1"),
    ]

    def _store_for(case_id):
        if case_id == "c1":
            raise RuntimeError("case-1 store unavailable")
        # c2 returns a debate
        s = mock.MagicMock()
        s.list_all.return_value = [{"id": "d1"}]
        return s

    from backend.api.deps import get_case_store

    app.dependency_overrides[get_case_store] = lambda: case_store
    with mock.patch(
        "backend.api.routers.onboarding.get_debate_store_for_case",
        side_effect=_store_for,
    ):
        try:
            response = client.get("/api/v1/onboarding/state", params={"tenant_id": "t1"})
        finally:
            app.dependency_overrides = {}

    assert response.status_code == 200
    body = response.json()
    assert body["has_cases"] is True
    assert body["has_debates"] is True
