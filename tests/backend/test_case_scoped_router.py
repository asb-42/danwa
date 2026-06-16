"""Tests for backend/api/routers/case_scoped.py — case-scoped API router.

The router had 44 % coverage.  These tests cover the high-value endpoints
that are easy to exercise in isolation:

  * helpers: ``_resolve_case_dir``, ``_get_debate_store_for_case``,
    ``_resolve_tags``, ``_resolve_llm_model``, ``_build_debate_item``
  * list endpoints: ``/tenants/{tid}/debates``,
    ``/tenants/{tid}/cases/{cid}/debates``
  * create/get/delete/cancel/force-reset debate
  * OOB input
  * forks listing
  * case audit delegation
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.routers.case_scoped import (
    _build_debate_item,
    _get_debate_store_for_case,
    _resolve_case_dir,
    _resolve_llm_model,
    _resolve_tags,
)
from backend.models.schemas import (
    CaseInput,
    DebateRequest,
    DebateStatus,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tenant_a(tenant_store):
    """Create tenant A and return its id."""
    t = tenant_store.create("Tenant A", tenant_id="t-A")
    return t.id


@pytest.fixture()
def case_a(case_store, tenant_a):
    """Create a case in tenant A and return its id."""
    c = case_store.create(tenant_a, "Case Alpha", description="primary")
    return c.id


@pytest.fixture()
def case_b(case_store, tenant_a):
    """Second case in tenant A."""
    c = case_store.create(tenant_a, "Case Beta", description="secondary")
    return c.id


def _seed_debate(case_dir: Path, debate_id: str, **overrides) -> dict:
    """Persist a debate JSON file in the case debates dir."""
    from backend.persistence.debate_store import DebateStore

    store = DebateStore(data_dir=case_dir / "debates")
    base = {
        "debate_id": debate_id,
        "status": DebateStatus.PENDING,
        "title": overrides.get("title", f"Debate {debate_id}"),
        "request": overrides.get(
            "request",
            {
                "case": {"text": "Sample case", "project_id": None},
                "language": "de",
                "max_rounds": 3,
            },
        ),
        "max_rounds": overrides.get("max_rounds", 3),
        "current_round": overrides.get("current_round", 0),
        "rounds": overrides.get("rounds", []),
        "result": overrides.get("result", None),
        "created_at": overrides.get("created_at", datetime.now(UTC)),
        "updated_at": overrides.get("updated_at", datetime.now(UTC)),
    }
    # Apply overrides AFTER base is built so callers can replace any field
    base.update(overrides)
    store.put(debate_id, base)
    return base


@pytest.fixture()
def tag_store(tmp_path):
    """Isolated TagStore with temp directory."""
    from backend.persistence.tag_store import TagStore

    return TagStore(base_dir=tmp_path / "test_tags")


@pytest.fixture(autouse=True)
def _patch_get_case_dir(case_store):
    """Make get_case_dir() resolve to the temp case dir.

    The case-scoped audit endpoint calls ``get_debate_store_for_case(case_id)``
    in ``backend.api.deps`` which uses ``get_case_dir()`` with the default
    base directory.  For the in-process tests to see the seeded debates
    we redirect ``get_case_dir`` to scan the case_store for a matching
    case across all tenants.
    """
    from backend.api import deps as deps_module

    original = deps_module.get_case_dir

    def _patched(case_id: str):
        # Walk the case_store filesystem dynamically on every call.
        case_store_dir = case_store._base_dir  # type: ignore[attr-defined]
        if case_store_dir.exists():
            for tenant_dir in case_store_dir.iterdir():
                if not tenant_dir.is_dir():
                    continue
                candidate = tenant_dir / "cases" / case_id
                if candidate.is_dir():
                    return candidate
        return original(case_id)

    deps_module.get_case_dir = _patched
    yield
    deps_module.get_case_dir = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestResolveCaseDir:
    def test_resolves_existing_case(self, case_store, case_a, tenant_a):
        d = _resolve_case_dir(tenant_a, case_a, case_store)
        assert isinstance(d, Path)
        assert d.exists()
        assert d.name == case_a

    def test_raises_404_for_missing_case(self, case_store, tenant_a):
        with pytest.raises(HTTPException) as exc:
            _resolve_case_dir(tenant_a, "no-such-case", case_store)
        assert exc.value.status_code == 404


class TestGetDebateStoreForCase:
    def test_creates_debates_dir(self, case_store, case_a, tenant_a):
        store = _get_debate_store_for_case(tenant_a, case_a, case_store)
        assert store is not None
        # subdirectory should be created
        assert (case_store.get_case_dir(tenant_a, case_a) / "debates").exists()

    def test_returns_isolated_stores_per_case(self, case_store, case_a, case_b, tenant_a):
        store_a = _get_debate_store_for_case(tenant_a, case_a, case_store)
        store_b = _get_debate_store_for_case(tenant_a, case_b, case_store)
        assert store_a is not store_b


class TestResolveLLMModel:
    def test_empty_profile_returns_empty(self):
        assert _resolve_llm_model("", "p") == ""

    def test_resolves_via_blueprint_repo(self, monkeypatch):
        fake_profile = mock.MagicMock(model="gpt-4o")
        fake_repo = mock.MagicMock(get_llm_profile=lambda _id: fake_profile)
        monkeypatch.setattr("backend.api.deps.get_blueprint_repository", lambda: fake_repo)
        result = _resolve_llm_model("profile-1", "p")
        assert result == "gpt-4o"

    def test_falls_back_to_id_when_repo_raises(self, monkeypatch):
        def boom():
            raise RuntimeError("db error")

        monkeypatch.setattr("backend.api.deps.get_blueprint_repository", boom)
        # Returns the profile_id when the repo can't resolve
        assert _resolve_llm_model("profile-1", "p") == "profile-1"

    def test_falls_back_to_id_when_profile_missing(self, monkeypatch):
        fake_repo = mock.MagicMock(get_llm_profile=lambda _id: None)
        monkeypatch.setattr("backend.api.deps.get_blueprint_repository", lambda: fake_repo)
        assert _resolve_llm_model("missing", "p") == "missing"


class TestResolveTags:
    def test_empty_returns_empty(self, tag_store, tenant_a):
        assert _resolve_tags(tenant_a, [], tag_store) == []

    def test_resolves_existing_tags(self, tag_store, tenant_a):
        t1 = tag_store.create(tenant_a, "Tag One", color="#ff0000")
        t2 = tag_store.create(tenant_a, "Tag Two", color="#00ff00")
        out = _resolve_tags(tenant_a, [t1.id, t2.id], tag_store)
        assert len(out) == 2
        assert {t.id for t in out} == {t1.id, t2.id}
        assert {t.name for t in out} == {"Tag One", "Tag Two"}

    def test_skips_missing_tags(self, tag_store, tenant_a):
        t1 = tag_store.create(tenant_a, "Only")
        out = _resolve_tags(tenant_a, [t1.id, "missing-id"], tag_store)
        assert len(out) == 1
        assert out[0].id == t1.id


class TestBuildDebateItem:
    def test_minimal_dict_builds_item(self):
        d = {
            "debate_id": "d-1",
            "status": DebateStatus.COMPLETED,
            "title": "T",
            "current_round": 2,
            "max_rounds": 3,
            "request": {"case": {"text": "Hello"}, "language": "en"},
            "result": {"final_consensus": 0.9},
        }
        item = _build_debate_item(d, [d], case_id="c1", case_title="Case 1")
        assert item.debate_id == "d-1"
        assert item.status == DebateStatus.COMPLETED
        assert item.title == "T"
        assert item.case_preview == "Hello"
        assert item.consensus_score == 0.9
        assert item.case_id == "c1"
        assert item.case_title == "Case 1"

    def test_fork_count(self):
        parent = {
            "debate_id": "parent",
            "status": "completed",
            "request": {"case": {"text": ""}, "language": "de"},
        }
        child = {
            "debate_id": "child",
            "status": "completed",
            "request": {"case": {"text": ""}, "language": "de"},
            "fork_info": {"parent_debate_id": "parent"},
        }
        all_debates = [parent, child]
        item = _build_debate_item(parent, all_debates, case_id="c1")
        assert item.forks_count == 1
        assert item.parent_debate_id is None

    def test_fork_info_on_self(self):
        child = {
            "debate_id": "child",
            "status": "completed",
            "request": {"case": {"text": ""}, "language": "de"},
            "fork_info": {"parent_debate_id": "parent"},
        }
        item = _build_debate_item(child, [child], case_id="c1")
        assert item.parent_debate_id == "parent"
        assert item.forks_count == 0

    def test_pydantic_request(self):
        """When the request has been re-hydrated into a Pydantic object."""
        req = DebateRequest(case=CaseInput(text="From Pydantic"), max_rounds=2)
        d = {
            "debate_id": "d-py",
            "status": DebateStatus.PENDING,
            "request": req,
        }
        item = _build_debate_item(d, [d], case_id="c")
        assert item.case_text == "From Pydantic"

    def test_unknown_request_type(self):
        d = {
            "debate_id": "d-x",
            "status": "pending",
            "request": "garbage",  # not dict, not model
        }
        item = _build_debate_item(d, [d], case_id="c")
        assert item.case_text == ""


# ---------------------------------------------------------------------------
# /tenants/{tid}/debates
# ---------------------------------------------------------------------------


class TestListTenantDebates:
    def test_empty_tenant(self, client: TestClient, tenant_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/debates")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unknown_tenant_returns_empty(self, client: TestClient):
        resp = client.get("/api/v1/tenants/no-such-tenant/debates")
        assert resp.status_code == 200
        # Unknown tenant -> no cases -> empty list
        assert resp.json() == []

    def test_aggregates_across_cases(self, client: TestClient, case_store, tenant_a, case_a, case_b):
        # Seed one debate per case
        _seed_debate(case_store.get_case_dir(tenant_a, case_a), "d-A")
        _seed_debate(case_store.get_case_dir(tenant_a, case_b), "d-B")
        resp = client.get(f"/api/v1/tenants/{tenant_a}/debates")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ids = {d["debate_id"] for d in data}
        assert ids == {"d-A", "d-B"}

    def test_filter_by_status(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-pending",
            status=DebateStatus.PENDING,
        )
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-completed",
            status=DebateStatus.COMPLETED,
        )
        resp = client.get(f"/api/v1/tenants/{tenant_a}/debates?status=completed")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["debate_id"] == "d-completed"

    def test_search_by_title(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d1",
            title="Climate Policy 2026",
        )
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d2",
            title="Space Exploration",
        )
        resp = client.get(f"/api/v1/tenants/{tenant_a}/debates?search=climate")
        assert resp.status_code == 200
        ids = {d["debate_id"] for d in resp.json()}
        assert ids == {"d1"}

    def test_pagination(self, client: TestClient, case_store, tenant_a, case_a):
        for i in range(3):
            _seed_debate(case_store.get_case_dir(tenant_a, case_a), f"d{i}")
        resp = client.get(f"/api/v1/tenants/{tenant_a}/debates?limit=2&offset=0")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# /tenants/{tid}/cases/{cid}/debates
# ---------------------------------------------------------------------------


class TestListCaseDebates:
    def test_empty_case(self, client: TestClient, tenant_a, case_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unknown_case_404(self, client: TestClient, tenant_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/no-such-case/debates")
        assert resp.status_code == 404

    def test_lists_debates_in_case(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(case_store.get_case_dir(tenant_a, case_a), "d1", title="First")
        _seed_debate(case_store.get_case_dir(tenant_a, case_a), "d2", title="Second")
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates")
        assert resp.status_code == 200
        ids = {d["debate_id"] for d in resp.json()}
        assert ids == {"d1", "d2"}

    def test_search_filter(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d1",
            request={
                "case": {"text": "Solar energy future", "project_id": None},
                "language": "de",
                "max_rounds": 3,
            },
        )
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d2",
            request={
                "case": {"text": "Wind turbines", "project_id": None},
                "language": "de",
                "max_rounds": 3,
            },
        )
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates?search=solar")
        assert resp.status_code == 200
        ids = {d["debate_id"] for d in resp.json()}
        assert ids == {"d1"}


# ---------------------------------------------------------------------------
# POST /tenants/{tid}/cases/{cid}/debates
# ---------------------------------------------------------------------------


class TestCreateCaseDebate:
    def test_creates_pending_debate(self, client: TestClient, tenant_a, case_a):
        body = {
            "case": {"text": "Discuss AI ethics"},
            "max_rounds": 3,
        }
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["title"] == ""
        assert "debate_id" in data

    def test_unknown_case_returns_404(self, client: TestClient, tenant_a):
        body = {"case": {"text": "X"}}
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/no-such/debates", json=body)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /tenants/{tid}/cases/{cid}/debates/{did}
# ---------------------------------------------------------------------------


class TestGetCaseDebate:
    def test_returns_status(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.RUNNING,
            current_round=1,
        )
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["debate_id"] == "d-1"
        assert data["status"] == "running"
        assert data["current_round"] == 1

    def test_unknown_debate_returns_404(self, client: TestClient, tenant_a, case_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/missing")
        assert resp.status_code == 404

    def test_unknown_case_returns_404(self, client: TestClient, tenant_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/no-such/debates/d-1")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /tenants/{tid}/cases/{cid}/debates/{did}
# ---------------------------------------------------------------------------


class TestDeleteCaseDebate:
    def test_deletes_pending(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.PENDING,
        )
        resp = client.delete(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1")
        assert resp.status_code == 200
        assert resp.json()["detail"] == "Debate deleted"
        # Verify it's actually gone
        from backend.persistence.debate_store import DebateStore

        store = DebateStore(data_dir=case_store.get_case_dir(tenant_a, case_a) / "debates")
        assert store.get("d-1") is None

    def test_deletes_completed(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.COMPLETED,
        )
        resp = client.delete(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1")
        assert resp.status_code == 200

    def test_running_returns_409(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.RUNNING,
        )
        resp = client.delete(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1")
        assert resp.status_code == 409
        assert "running" in resp.json()["detail"]

    def test_missing_returns_404(self, client: TestClient, tenant_a, case_a):
        resp = client.delete(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/missing")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /tenants/{tid}/cases/{cid}/debates/{did}/cancel
# ---------------------------------------------------------------------------


class TestCancelCaseDebate:
    def test_cancel_running(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.RUNNING,
        )
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_cancel_pending(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.PENDING,
        )
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_cancel_completed_idempotent(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.COMPLETED,
        )
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    def test_missing_404(self, client: TestClient, tenant_a, case_a):
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/missing/cancel")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /tenants/{tid}/cases/{cid}/debates/{did}/force-reset
# ---------------------------------------------------------------------------


class TestForceResetCaseDebate:
    def test_force_reset_running(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.RUNNING,
        )
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/force-reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        from backend.persistence.debate_store import DebateStore

        store = DebateStore(data_dir=case_store.get_case_dir(tenant_a, case_a) / "debates")
        d = store.get("d-1")
        assert d["status"] == DebateStatus.FAILED
        assert "error" in (d.get("result") or {})

    def test_force_reset_pending_noop(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.PENDING,
        )
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/force-reset")
        assert resp.status_code == 200
        # Status should be unchanged (pending) — only running gets reset
        from backend.persistence.debate_store import DebateStore

        store = DebateStore(data_dir=case_store.get_case_dir(tenant_a, case_a) / "debates")
        d = store.get("d-1")
        assert d["status"] == DebateStatus.PENDING

    def test_missing_404(self, client: TestClient, tenant_a, case_a):
        resp = client.post(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/missing/force-reset")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /tenants/{tid}/cases/{cid}/debates/{did}/oob
# ---------------------------------------------------------------------------


class TestOOBCaseInput:
    def test_oob_non_running_returns_409(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.PENDING,
        )
        body = {
            "content": "more context",
            "target": {"type": "next_agent"},
            "urgency": "append",
        }
        resp = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/oob",
            json=body,
        )
        assert resp.status_code == 409

    def test_oob_missing_debate_404(self, client: TestClient, tenant_a, case_a):
        body = {
            "content": "x",
            "target": {"type": "next_agent"},
            "urgency": "append",
        }
        resp = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/missing/oob",
            json=body,
        )
        assert resp.status_code == 404

    def test_oob_running_queues_input(self, client: TestClient, case_store, tenant_a, case_a, monkeypatch):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            status=DebateStatus.RUNNING,
        )

        # Stub async event publish (in events module)
        async def _noop(*_args, **_kwargs):
            return None

        monkeypatch.setattr("backend.api.events.publish_async", _noop)

        # Stub the enqueue to capture the call
        from backend.services import debate_workflow

        enqueued: list = []
        monkeypatch.setattr(
            debate_workflow,
            "enqueue_oob",
            lambda _did, entry: enqueued.append(entry),
        )

        body = {
            "content": "injected context",
            "target": {
                "type": "specific_agent",
                "agent_role": "strategist",
            },
            "urgency": "inject_now",
        }
        resp = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/d-1/oob",
            json=body,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
        assert "oob_id" in data
        assert data["target_resolved"] == "specific_agent"
        assert len(enqueued) == 1
        assert enqueued[0]["content"] == "injected context"


# ---------------------------------------------------------------------------
# GET /tenants/{tid}/cases/{cid}/debates/{did}/forks
# ---------------------------------------------------------------------------


class TestListCaseForks:
    def test_no_forks(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(case_store.get_case_dir(tenant_a, case_a), "parent")
        _seed_debate(case_store.get_case_dir(tenant_a, case_a), "other")
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/parent/forks")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_lists_only_children(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(case_store.get_case_dir(tenant_a, case_a), "parent")
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "child1",
            fork_info={"parent_debate_id": "parent"},
        )
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "other-child",
            fork_info={"parent_debate_id": "different"},
        )
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/debates/parent/forks")
        assert resp.status_code == 200
        ids = {d["debate_id"] for d in resp.json()}
        assert ids == {"child1"}

    def test_unknown_case_404(self, client: TestClient, tenant_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/no-such/debates/d-1/forks")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /tenants/{tid}/cases/{cid}/audit/{did}
# ---------------------------------------------------------------------------


class TestListCaseAuditEvents:
    def test_audit_for_unknown_debate(self, client: TestClient, tenant_a, case_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/audit/missing")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_audit_unknown_case_404(self, client: TestClient, tenant_a):
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/no-such/audit/missing")
        assert resp.status_code == 404

    def test_audit_delegates_to_resolver(self, client: TestClient, case_store, tenant_a, case_a):
        _seed_debate(
            case_store.get_case_dir(tenant_a, case_a),
            "d-1",
            title="My Title",
        )
        # The endpoint resolves via the case debate store, which should
        # find this title in the case-scoped store.  No events recorded,
        # so empty list returned.
        resp = client.get(f"/api/v1/tenants/{tenant_a}/cases/{case_a}/audit/My Title")
        assert resp.status_code == 200
        # The debate is found but has no audit events
        assert resp.json() == []


# ---------------------------------------------------------------------------
# /tenants/{tid}/cases/{cid}/dms/analyze/export
# ---------------------------------------------------------------------------
#
# The frontend hits this URL (see frontend/src/lib/api/document.js
# ::exportAnalysis).  The route must accept POST {format: 'pdf'|'odt'|'md'}
# and return a downloadable file response.  Before the 2026-06-16 fix the
# endpoint did not exist on the case-scoped router, so the UI got a 404
# ("Not Found") and the export silently failed.
#
# We seed the analysis payload by writing to the case dir directly (the
# same path the analyze endpoint uses via ``get_case_dir(case_id)``).
# The export handler is then expected to render that analysis to the
# requested format and return a ``FileResponse``.


def _seed_analysis(case_dir: Path, analysis: dict) -> None:
    """Persist an analysis.json in the case dir for export tests."""
    import json

    (case_dir / "analysis.json").write_text(json.dumps(analysis))


class TestCaseAnalysisExport:
    """Pin down the case-scoped /dms/analyze/export endpoint."""

    def test_endpoint_exists_and_returns_markdown(
        self,
        client: TestClient,
        case_store,
        tenant_a,
        case_a,
    ):
        """The endpoint must exist (no 404) and return a downloadable md.

        Before the fix this raised 404 because the route was only
        registered on the legacy ``/dms/analyze/export`` path.
        """
        case_dir = case_store.get_case_dir(tenant_a, case_a)
        _seed_analysis(
            case_dir,
            {
                "case_summary": "Test summary",
                "key_facts": ["fact 1"],
                "parties": [],
                "timeline": [],
                "key_issues": [],
                "documents": [],
            },
        )
        response = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/dms/analyze/export",
            json={"format": "md"},
        )
        assert response.status_code == 200, response.text
        assert "markdown" in response.headers.get("content-type", "")
        body = response.text
        # Body is a markdown rendering; the case summary must appear.
        assert "Test summary" in body

    def test_endpoint_404_when_no_analysis_exists(
        self,
        client: TestClient,
        case_store,
        tenant_a,
        case_a,
    ):
        """If no analysis has been run yet, the endpoint must 404 with
        a clear message (mirrors the legacy behaviour)."""
        # Use a fresh case dir with no analysis.json written.
        case_dir = case_store.get_case_dir(tenant_a, case_a)
        if (case_dir / "analysis.json").exists():
            (case_dir / "analysis.json").unlink()
        response = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/dms/analyze/export",
            json={"format": "md"},
        )
        assert response.status_code == 404
        assert "analysis" in response.json()["detail"].lower()

    def test_endpoint_422_for_unsupported_format(
        self,
        client: TestClient,
        case_store,
        tenant_a,
        case_a,
    ):
        """Requesting a non-pdf/odt/md format must return 422."""
        case_dir = case_store.get_case_dir(tenant_a, case_a)
        _seed_analysis(
            case_dir,
            {
                "case_summary": "x",
                "key_facts": [],
                "parties": [],
                "timeline": [],
                "key_issues": [],
                "documents": [],
            },
        )
        response = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/dms/analyze/export",
            json={"format": "docx"},
        )
        assert response.status_code == 422
        assert "format" in response.json()["detail"].lower()

    def test_endpoint_pdf_uses_weasyprint(
        self,
        client: TestClient,
        case_store,
        tenant_a,
        case_a,
        monkeypatch,
    ):
        """The PDF path must invoke WeasyPrint and return application/pdf.

        We monkey-patch the underlying ``weasyprint.HTML.write_pdf`` to
        avoid the real PDF generator (which is heavy in tests) and
        assert that the endpoint produces a 200 with the correct
        media-type and a non-empty body.
        """
        case_dir = case_store.get_case_dir(tenant_a, case_a)
        _seed_analysis(
            case_dir,
            {
                "case_summary": "PDF test",
                "key_facts": [],
                "parties": [],
                "timeline": [],
                "key_issues": [],
                "documents": [],
            },
        )

        # We don't need to monkey-patch the template; we just want to
        # confirm the endpoint dispatches to the PDF branch and returns
        # a file with the expected media-type.  Patch weasyprint to a
        # minimal fake.
        class _FakeHTML:
            def __init__(self, string):
                self.string = string

            def write_pdf(self, target):
                Path(target).write_bytes(b"%PDF-1.4 fake")

        import sys

        fake_weasy = mock.MagicMock()
        fake_weasy.HTML = _FakeHTML
        monkeypatch.setitem(sys.modules, "weasyprint", fake_weasy)

        response = client.post(
            f"/api/v1/tenants/{tenant_a}/cases/{case_a}/dms/analyze/export",
            json={"format": "pdf"},
        )
        assert response.status_code == 200, response.text
        assert "application/pdf" in response.headers.get("content-type", "")
        # The fake PDF must come through as the response body.
        assert response.content.startswith(b"%PDF-1.4")
