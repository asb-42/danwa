"""Tests for the last_workspace tenant-scoping fix (2026-06-16).

The original implementation stored a single ``users.last_workspace`` string
per user, with no tenant context.  When a user switched tenants and re-
mounted the Workspace view, the restore path pulled back a case id from a
tenant that was no longer active.  This file pins down the three layers of
the fix:

  1. UserStore now persists ``(user_id, tenant_id) → case_id`` in
     ``user_last_workspace``.  The legacy single-value column is kept as a
     one-shot backfill source but is no longer the authoritative read.
  2. ``GET /api/v1/auth/me/last-workspace`` and ``PUT /api/v1/auth/me/last-workspace``
     resolve the active tenant via ``X-Tenant-Id`` and write to the per-
     tenant mapping row.  Case ids from other tenants are never returned.
  3. ``GET /api/v1/workspace/summary`` re-checks that the loaded case
     actually belongs to the caller's active tenant.  A mismatch is logged
     and surfaced as 404.

@see plans/2026-06-16_last-workspace-cross-tenant-bug.md
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.core.security import create_access_token, hash_password
from backend.persistence.membership_store import MembershipStore
from backend.persistence.user_store import UserStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_store(tmp_path):
    """Fresh, isolated UserStore per test."""
    return UserStore(db_path=tmp_path / "test_auth.db")


@pytest.fixture()
def membership_store(tmp_path):
    """Fresh MembershipStore that shares the auth DB with user_store."""
    return MembershipStore(db_path=tmp_path / "test_auth.db")


@pytest.fixture()
def admin_user(user_store):
    """An admin seeded in the default tenant."""
    return user_store.create(
        email="admin@example.com",
        display_name="Admin",
        password_hash=hash_password("adminpass"),
        role="admin",
        tenant_id="tenant-A",
    )


@pytest.fixture()
def app_with_auth(app, user_store, membership_store, admin_user):
    """App with overridden user_store, membership_store, and get_current_user.

    Tests that need to switch the active principal can re-override
    ``get_current_user`` after this fixture wires the default admin.
    """
    from backend.api.deps import get_current_user, get_membership_store, get_user_store

    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_membership_store] = lambda: membership_store
    app.dependency_overrides[get_current_user] = lambda: admin_user
    get_user_store.cache_clear()
    get_membership_store.cache_clear()
    yield app
    app.dependency_overrides.pop(get_user_store, None)
    app.dependency_overrides.pop(get_membership_store, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client_auth(app_with_auth) -> TestClient:
    return TestClient(app_with_auth)


def _auth_headers(user, tenant_id: str | None = None) -> dict[str, str]:
    """Build the headers a real client would send: Bearer + X-Tenant-Id."""
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}
    if tenant_id is not None:
        headers["X-Tenant-Id"] = tenant_id
    return headers


# ---------------------------------------------------------------------------
# Stufe 1 — UserStore: per-tenant mapping
# ---------------------------------------------------------------------------


class TestUserStoreLastWorkspacePerTenant:
    """Pin down the per-tenant mapping table + get/set round-trip."""

    def test_get_returns_none_when_never_set(self, user_store, admin_user):
        """A user that never persisted a workspace has no per-tenant row."""
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") is None

    def test_set_and_get_roundtrip_with_tenant(self, user_store, admin_user):
        """The new signature: (user_id, tenant_id) → case_id round-trips."""
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-A",
            tenant_id="tenant-A",
        )
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") == "case-in-A"

    def test_tenant_isolation(self, user_store, admin_user):
        """A case id persisted for tenant-A is invisible to tenant-B."""
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-A",
            tenant_id="tenant-A",
        )
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-B",
            tenant_id="tenant-B",
        )
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") == "case-in-A"
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-B") == "case-in-B"

    def test_clear_with_none(self, user_store, admin_user):
        """Passing case_id=None removes the per-tenant row, not the legacy column."""
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-A",
            tenant_id="tenant-A",
        )
        user_store.set_last_workspace(admin_user.id, None, tenant_id="tenant-A")
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") is None

    def test_legacy_fallback_when_tenant_id_is_none(self, user_store, admin_user):
        """The legacy read path still works for callers that don't pass a tenant.

        This is the back-compat path: an older caller asking for
        ``get_last_workspace(user_id)`` (no tenant) still gets the value
        from the legacy ``users.last_workspace`` column when no per-tenant
        row exists.  Once a per-tenant write has happened, the legacy
        column may be stale and is never silently used as a fallback for
        a tenant-aware caller.
        """
        # Seed the legacy column directly (bypassing the new write path)
        user_store.conn.execute(
            "UPDATE users SET last_workspace = ? WHERE id = ?",
            ("legacy-case-id", admin_user.id),
        )
        user_store.conn.commit()
        # Tenant=None read returns the legacy value
        assert user_store.get_last_workspace(admin_user.id) == "legacy-case-id"
        # Tenant-aware read returns None (no per-tenant row)
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") is None

    def test_no_silent_backfill_from_legacy_column(self, tmp_path):
        """Bug A (2026-06-16): the schema-migration block must NOT
        backfill the legacy ``users.last_workspace`` value into the
        new per-tenant mapping.

        We pin this by simulating a real pre-migration DB:

        1. Create a UserStore and seed a user with a value in the
           legacy ``users.last_workspace`` column.
        2. Close it.
        3. Open a fresh UserStore against the same file.  This is
           the "restart with an existing DB" scenario where the
           backfill used to fire.
        4. Assert that the per-tenant mapping is empty.

        Silently using the user's primary ``tenant_id`` (as the
        pre-fix code did) leaks case ids into the wrong tenant's
        workspace.  The expected behaviour is: the user must
        explicitly ``PUT /api/v1/auth/me/last-workspace`` with the
        active ``X-Tenant-Id`` header to populate the per-tenant
        row.
        """
        # Phase 1: build a pre-migration DB and seed the legacy column.
        db_path = tmp_path / "backfill_test.db"
        phase1 = UserStore(db_path=db_path)
        u = phase1.create(
            email="nolegacy@example.com",
            display_name="No Backfill",
            password_hash=hash_password("p"),
            role="viewer",
            tenant_id="tenant-A",
        )
        phase1.conn.execute(
            "UPDATE users SET last_workspace = ? WHERE id = ?",
            ("hkk", u.id),
        )
        phase1.conn.commit()
        phase1.conn.close()

        # Phase 2: re-open the DB.  The backfill (if any) would fire here.
        phase2 = UserStore(db_path=db_path)
        try:
            # Per-tenant mapping is empty — the migration did NOT
            # backfill the legacy value into any tenant row.
            assert phase2.get_last_workspace(u.id, tenant_id="tenant-A") is None
            assert phase2.get_last_workspace(u.id, tenant_id="tenant-B") is None

            # The legacy column is preserved for back-compat reads
            # when called without a tenant_id.
            assert phase2.get_last_workspace(u.id) == "hkk"

            # Only an explicit per-tenant write populates the new row.
            phase2.set_last_workspace(
                u.id,
                "case-in-A",
                tenant_id="tenant-A",
            )
            assert phase2.get_last_workspace(u.id, tenant_id="tenant-A") == "case-in-A"
            # The other tenant stays empty.
            assert phase2.get_last_workspace(u.id, tenant_id="tenant-B") is None
        finally:
            phase2.conn.close()


# ---------------------------------------------------------------------------
# Stufe 2 — Auth-Route: tenant-scoped persistence
# ---------------------------------------------------------------------------


class TestAuthLastWorkspaceTenantScoped:
    """Verify that the route uses the X-Tenant-Id header to scope writes/reads."""

    def test_get_returns_case_for_active_tenant(self, client_auth, user_store, admin_user):
        """A case id written for tenant-A is returned when the caller is in tenant-A."""
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-A",
            tenant_id="tenant-A",
        )
        response = client_auth.get(
            "/api/v1/auth/me/last-workspace",
            headers={"X-Tenant-Id": "tenant-A"},
        )
        assert response.status_code == 200
        assert response.json()["case_id"] == "case-in-A"

    def test_get_does_not_leak_across_tenants(self, client_auth, user_store, admin_user):
        """A case id written for tenant-A is NOT returned to a caller in tenant-B.

        This is the test that pins down the cross-tenant-leak fix at the
        API layer.  Before the fix, the route used the legacy single-
        value column and would have returned ``case-in-A`` here, leaking
        a case from another tenant.
        """
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-A",
            tenant_id="tenant-A",
        )
        response = client_auth.get(
            "/api/v1/auth/me/last-workspace",
            headers={"X-Tenant-Id": "tenant-B"},
        )
        assert response.status_code == 200
        assert response.json()["case_id"] is None

    def test_put_writes_to_active_tenant(self, client_auth, user_store, admin_user):
        """PUT with X-Tenant-Id=tenant-A writes into (admin, tenant-A)."""
        response = client_auth.put(
            "/api/v1/auth/me/last-workspace",
            json={"case_id": "case-X"},
            headers={"X-Tenant-Id": "tenant-A"},
        )
        assert response.status_code == 200
        assert response.json()["case_id"] == "case-X"
        # Verify it landed in the per-tenant row
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") == "case-X"
        # And NOT in any other tenant
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-B") is None

    def test_put_tenant_b_does_not_overwrite_tenant_a(self, client_auth, user_store, admin_user):
        """Writing for tenant-B must not clobber a value already stored for tenant-A."""
        user_store.set_last_workspace(
            admin_user.id,
            "case-in-A",
            tenant_id="tenant-A",
        )
        client_auth.put(
            "/api/v1/auth/me/last-workspace",
            json={"case_id": "case-in-B"},
            headers={"X-Tenant-Id": "tenant-B"},
        )
        # Both should still be intact
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") == "case-in-A"
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-B") == "case-in-B"

    def test_put_clear_with_null(self, client_auth, user_store, admin_user):
        """case_id=null clears the per-tenant row only."""
        user_store.set_last_workspace(
            admin_user.id,
            "case-X",
            tenant_id="tenant-A",
        )
        response = client_auth.put(
            "/api/v1/auth/me/last-workspace",
            json={"case_id": None},
            headers={"X-Tenant-Id": "tenant-A"},
        )
        assert response.status_code == 200
        assert user_store.get_last_workspace(admin_user.id, tenant_id="tenant-A") is None


# ---------------------------------------------------------------------------
# Stufe 3 — Workspace summary: tenant-mismatch defence
# ---------------------------------------------------------------------------


class TestWorkspaceSummaryTenantDefence:
    """Verify that the summary endpoint refuses cross-tenant cases.

    Note: the project-level ``app`` fixture (see tests/backend/conftest.py)
    already overrides ``get_case_store`` with a real CaseStore populated
    by ``default_case``.  We replace that override here with a stub that
    is independent of any real DB state, so the tenant-isolation logic
    is exercised in isolation.
    """

    @pytest.fixture
    def enabled(self, monkeypatch):
        from backend.api.routers import workspace as workspace_module

        monkeypatch.setattr(workspace_module.settings, "enable_case_space", True)

    def _stub(self, *, case_tenant: str):
        """Return a case-store stub whose ``get`` always yields a case
        whose ``tenant_id`` is ``case_tenant``.  Used to simulate a
        misconfigured store that returns a foreign-tenant case."""

        class _Stub:
            def get(self, tenant_id, case_id):
                return SimpleNamespace(
                    id=case_id,
                    tenant_id=case_tenant,
                    title=f"Case {case_id}",
                    description=None,
                    status="active",
                    tags=[],
                    members=[],
                    debate_ids=[],
                    document_ids=[],
                )

            def list(self):
                return []

        return _Stub()

    def test_summary_200_when_case_belongs_to_active_tenant(
        self,
        tmp_path,
    ):
        """Sanity: matching tenant_id is served normally.

        Construct a minimal FastAPI app with only the workspace router
        and a fresh CaseStore.  This bypasses the project-level conftest
        module-level mpatch of ``get_case_store`` (which would otherwise
        serve a real empty CaseStore and 404 our synthetic case).
        """
        from fastapi import FastAPI, Header
        from fastapi.testclient import TestClient

        from backend.api.deps import get_active_tenant, get_case_store
        from backend.api.routers.workspace import router as workspace_router
        from backend.persistence.case_store import CaseStore

        case_store = CaseStore(base_dir=tmp_path / "summary_cases_ok")
        case_store.create("tenant-A", "OK", case_id="matching-case", description="")

        def _active_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
            return x_tenant_id or "tenant-A"

        app = FastAPI()
        app.include_router(workspace_router, prefix="/api/v1")
        app.dependency_overrides[get_active_tenant] = _active_tenant
        app.dependency_overrides[get_case_store] = lambda: case_store

        with TestClient(app) as tc:
            response = tc.get(
                "/api/v1/workspace/summary",
                params={"case_id": "matching-case"},
                headers={"X-Tenant-Id": "tenant-A"},
            )

        if response.status_code != 200:
            print("\n[DEBUG] status=", response.status_code, "body=", response.text)
        assert response.status_code == 200, f"expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert body["case_id"] == "matching-case"
        assert body["tenant_id"] == "tenant-A"

    def test_summary_404_when_case_belongs_to_other_tenant(
        self,
        tmp_path,
    ):
        """Cross-tenant case is rejected with 404, not silently rendered.

        Same minimal-app approach as the 200 test, but with a stub
        store that returns a case whose ``tenant_id`` differs from the
        caller's X-Tenant-Id.
        """
        from fastapi import FastAPI, Header
        from fastapi.testclient import TestClient

        from backend.api.deps import get_active_tenant, get_case_store
        from backend.api.routers.workspace import router as workspace_router

        class _Stub:
            def get(self, tenant_id, case_id):
                return SimpleNamespace(
                    id=case_id,
                    tenant_id="tenant-A",  # mismatch
                    title="Foreign",
                    description=None,
                    status="active",
                    tags=[],
                    members=[],
                    debate_ids=[],
                    document_ids=[],
                )

            def list(self):
                return []

        def _active_tenant(x_tenant_id: str | None = Header(default=None)) -> str:
            return x_tenant_id or "tenant-A"

        app = FastAPI()
        app.include_router(workspace_router, prefix="/api/v1")
        app.dependency_overrides[get_active_tenant] = _active_tenant
        app.dependency_overrides[get_case_store] = lambda: _Stub()

        with TestClient(app) as tc:
            response = tc.get(
                "/api/v1/workspace/summary",
                params={"case_id": "any"},
                headers={"X-Tenant-Id": "tenant-B"},
            )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
