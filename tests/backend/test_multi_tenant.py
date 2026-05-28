"""Integration tests for multi-tenant isolation, auth flow, and quotas."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.core.security import create_access_token, create_refresh_token, decode_token, hash_password
from backend.models.tenant import Tenant
from backend.models.user import User
from backend.persistence.user_store import UserStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tmp_path():
    return Path(tempfile.mkdtemp())


def _make_user(user_id: str, tenant_id: str, role: str = "viewer") -> User:
    return User(
        id=user_id,
        email=f"{user_id}@test.com",
        display_name=f"User {user_id}",
        password_hash=hash_password("testpass123"),
        role=role,
        tenant_id=tenant_id,
    )


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    """Verify that users from different tenants cannot access each other's data."""

    def test_users_isolated_by_tenant(self):
        user_store = UserStore(db_path=_tmp_path() / "auth.db")

        user_store.create("alice@t1.com", "Alice", hash_password("pass"), role="admin", tenant_id="tenant-1")
        user_store.create("bob@t2.com", "Bob", hash_password("pass"), role="admin", tenant_id="tenant-2")

        t1_users = user_store.list_by_tenant("tenant-1")
        t2_users = user_store.list_by_tenant("tenant-2")

        assert len(t1_users) == 1
        assert len(t2_users) == 1
        assert t1_users[0].email == "alice@t1.com"
        assert t2_users[0].email == "bob@t2.com"

    def test_projects_isolated_by_tenant(self):
        from backend.persistence.project_store import ProjectStore

        store = ProjectStore(base_dir=_tmp_path() / "projects")

        store.create("Project A", tenant_id="tenant-1")
        store.create("Project B", tenant_id="tenant-1")
        store.create("Project C", tenant_id="tenant-2")

        assert len(store.list_by_tenant("tenant-1")) == 2
        assert len(store.list_by_tenant("tenant-2")) == 1
        assert len(store.list_by_tenant("tenant-3")) == 0


# ---------------------------------------------------------------------------
# JWT token flow
# ---------------------------------------------------------------------------


class TestJWTTokenFlow:
    """Verify complete JWT lifecycle: create, decode, refresh."""

    def test_access_token_contains_claims(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "test-secret")
        user = _make_user("u1", "tenant-1", role="editor")
        token = create_access_token(user)
        data = decode_token(token)

        assert data.user_id == "u1"
        assert data.email == "u1@test.com"
        assert data.role == "editor"
        assert data.tenant_id == "tenant-1"
        assert data.token_type == "access"

    def test_refresh_token_is_different_type(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "test-secret")
        user = _make_user("u1", "tenant-1")
        token = create_refresh_token(user)
        data = decode_token(token)

        assert data.token_type == "refresh"
        assert data.user_id == "u1"

    def test_token_from_different_secret_fails(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "secret-1")
        user = _make_user("u1", "tenant-1")
        token = create_access_token(user)

        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "secret-2")
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token(token)


# ---------------------------------------------------------------------------
# Quota enforcement
# ---------------------------------------------------------------------------


class TestQuotaEnforcement:
    """Verify tenant quota checks work correctly."""

    def test_debate_quota_allows_within_limit(self):
        from backend.api.quota import check_debate_quota

        tenant = Tenant(name="T", max_concurrent_debates=5)
        check_debate_quota(tenant, 4)  # Should not raise

    def test_debate_quota_blocks_at_limit(self):
        from backend.api.quota import check_debate_quota

        tenant = Tenant(name="T", max_concurrent_debates=5)
        with pytest.raises(Exception):
            check_debate_quota(tenant, 5)

    def test_debate_quota_blocks_over_limit(self):
        from backend.api.quota import check_debate_quota

        tenant = Tenant(name="T", max_concurrent_debates=2)
        with pytest.raises(Exception):
            check_debate_quota(tenant, 10)

    def test_document_quota_allows_within_limit(self):
        from backend.api.quota import check_document_quota

        tenant = Tenant(name="T", max_documents=50)
        check_document_quota(tenant, 49)

    def test_document_quota_blocks_at_limit(self):
        from backend.api.quota import check_document_quota

        tenant = Tenant(name="T", max_documents=50)
        with pytest.raises(Exception):
            check_document_quota(tenant, 50)

    def test_project_quota_allows_within_limit(self):
        from backend.api.quota import check_project_quota

        tenant = Tenant(name="T", max_projects=5)
        check_project_quota(tenant, 3)

    def test_project_quota_blocks_at_limit(self):
        from backend.api.quota import check_project_quota

        tenant = Tenant(name="T", max_projects=5)
        with pytest.raises(Exception):
            check_project_quota(tenant, 5)


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


class TestMultiTenantMigration:
    """Verify the v001 migration script works correctly."""

    def test_migration_creates_default_tenant(self, monkeypatch):
        tmpdir = _tmp_path()
        auth_db = tmpdir / "auth.db"

        from backend.persistence import tenant_store

        _orig_store = tenant_store.TenantStore

        class PatchedStore(_orig_store):
            def __init__(self, db_path=None):
                super().__init__(db_path=auth_db)

        monkeypatch.setattr(tenant_store, "TenantStore", PatchedStore)

        from backend.migrations.v001_multi_tenant import _ensure_default_tenant

        _ensure_default_tenant()

        store = _orig_store(db_path=auth_db)
        assert store.get("_default") is not None
        assert store.get("_default").name == "Default"

    def test_migration_is_idempotent(self, monkeypatch):
        tmpdir = _tmp_path()
        auth_db = tmpdir / "auth.db"

        from backend.persistence import tenant_store

        _orig_store = tenant_store.TenantStore

        class PatchedStore(_orig_store):
            def __init__(self, db_path=None):
                super().__init__(db_path=auth_db)

        monkeypatch.setattr(tenant_store, "TenantStore", PatchedStore)

        from backend.migrations.v001_multi_tenant import _ensure_default_tenant

        _ensure_default_tenant()
        _ensure_default_tenant()  # Second run should be no-op

        store = _orig_store(db_path=auth_db)
        assert store.count() == 1
