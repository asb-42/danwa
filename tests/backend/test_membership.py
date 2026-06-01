"""Tests for tenant membership — MembershipStore unit tests and API tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pytest import fixture

from backend.api.deps import (
    get_audit_service,
    get_current_user,
    get_debate_store,
    get_membership_store,
    get_project_store,
    get_settings,
)
from backend.core.config import Settings
from backend.main import create_app
from backend.models.user import User
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.membership_store import MembershipStore
from backend.persistence.project_store import ProjectStore

_TENANT_A = "tenant-a"
_TENANT_B = "tenant-b"


@fixture()
def membership_store(tmp_path) -> MembershipStore:
    return MembershipStore(db_path=tmp_path / "auth.db")


@fixture()
def settings(tmp_path) -> Settings:
    return Settings(
        db_path=tmp_path / "test_audit.db",
        cors_origins=["http://testserver"],
        debug=True,
    )


@fixture()
def audit_service(tmp_path) -> AuditService:
    return AuditService(db_path=tmp_path / "test_audit.db")


@fixture()
def debate_store(tmp_path) -> DebateStore:
    return DebateStore(data_dir=tmp_path / "test_debates")


@fixture()
def project_store(tmp_path) -> ProjectStore:
    return ProjectStore(base_dir=tmp_path / "projects")


@fixture()
def app(settings, audit_service, debate_store, project_store, membership_store):
    application = create_app()

    _test_user = User(
        id="test-user",
        email="test@danwa.local",
        display_name="Test User",
        password_hash="",
        role="admin",
        tenant_id=_TENANT_A,
    )

    application.dependency_overrides[get_settings] = lambda: settings
    application.dependency_overrides[get_current_user] = lambda: _test_user
    application.dependency_overrides[get_audit_service] = lambda: audit_service
    application.dependency_overrides[get_debate_store] = lambda: debate_store
    application.dependency_overrides[get_project_store] = lambda: project_store
    application.dependency_overrides[get_membership_store] = lambda: membership_store
    return application


@fixture()
def client(app) -> TestClient:
    return TestClient(app)


# ===========================================================================
# MembershipStore Unit Tests
# ===========================================================================


class TestMembershipStoreAdd:
    def test_add_membership(self, membership_store):
        m = membership_store.add(_TENANT_A, "user1", role="admin")
        assert m.tenant_id == _TENANT_A
        assert m.user_id == "user1"
        assert m.role == "admin"
        assert m.joined_at is not None

    def test_add_membership_default_role(self, membership_store):
        m = membership_store.add(_TENANT_A, "user2")
        assert m.role == "member"

    def test_add_with_invited_by(self, membership_store):
        m = membership_store.add(_TENANT_A, "user3", invited_by="admin-user")
        assert m.invited_by == "admin-user"

    def test_add_duplicate_updates(self, membership_store):
        membership_store.add(_TENANT_A, "user1", role="member")
        membership_store.add(_TENANT_A, "user1", role="admin")
        m = membership_store.get(_TENANT_A, "user1")
        assert m.role == "admin"


class TestMembershipStoreGet:
    def test_get_existing(self, membership_store):
        membership_store.add(_TENANT_A, "user1")
        m = membership_store.get(_TENANT_A, "user1")
        assert m is not None
        assert m.user_id == "user1"

    def test_get_nonexistent(self, membership_store):
        assert membership_store.get(_TENANT_A, "nobody") is None

    def test_get_wrong_tenant(self, membership_store):
        membership_store.add(_TENANT_A, "user1")
        assert membership_store.get(_TENANT_B, "user1") is None


class TestMembershipStoreRemove:
    def test_remove_existing(self, membership_store):
        membership_store.add(_TENANT_A, "user1")
        assert membership_store.remove(_TENANT_A, "user1") is True
        assert membership_store.get(_TENANT_A, "user1") is None

    def test_remove_nonexistent(self, membership_store):
        assert membership_store.remove(_TENANT_A, "nobody") is False


class TestMembershipStoreList:
    def test_list_by_user(self, membership_store):
        membership_store.add(_TENANT_A, "user1")
        membership_store.add(_TENANT_B, "user1")
        memberships = membership_store.list_by_user("user1")
        assert len(memberships) == 2
        tenant_ids = {m.tenant_id for m in memberships}
        assert tenant_ids == {_TENANT_A, _TENANT_B}

    def test_list_by_user_empty(self, membership_store):
        assert membership_store.list_by_user("nobody") == []

    def test_list_by_tenant(self, membership_store):
        membership_store.add(_TENANT_A, "user1")
        membership_store.add(_TENANT_A, "user2")
        memberships = membership_store.list_by_tenant(_TENANT_A)
        assert len(memberships) == 2

    def test_list_by_tenant_empty(self, membership_store):
        assert membership_store.list_by_tenant(_TENANT_A) == []

    def test_tenant_isolation(self, membership_store):
        membership_store.add(_TENANT_A, "user1")
        membership_store.add(_TENANT_B, "user2")
        assert len(membership_store.list_by_tenant(_TENANT_A)) == 1
        assert len(membership_store.list_by_tenant(_TENANT_B)) == 1


class TestMembershipStoreUpdateRole:
    def test_update_role(self, membership_store):
        membership_store.add(_TENANT_A, "user1", role="member")
        updated = membership_store.update_role(_TENANT_A, "user1", "admin")
        assert updated.role == "admin"

    def test_update_role_nonexistent(self, membership_store):
        assert membership_store.update_role(_TENANT_A, "nobody", "admin") is None


class TestMembershipStoreCount:
    def test_count(self, membership_store):
        assert membership_store.count_by_tenant(_TENANT_A) == 0
        membership_store.add(_TENANT_A, "user1")
        assert membership_store.count_by_tenant(_TENANT_A) == 1
        membership_store.add(_TENANT_A, "user2")
        assert membership_store.count_by_tenant(_TENANT_A) == 2


# ===========================================================================
# Multi-tenant API Tests
# ===========================================================================


class TestMyTenantsAPI:
    def test_empty_when_no_memberships(self, client):
        response = client.get("/api/v1/auth/my-tenants")
        assert response.status_code == 200
        assert response.json() == []

    def test_lists_memberships(self, client, membership_store):
        membership_store.add(_TENANT_A, "test-user", role="admin")
        membership_store.add(_TENANT_B, "test-user", role="member")

        response = client.get("/api/v1/auth/my-tenants")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        roles = {m["tenant_id"]: m["role"] for m in data}
        assert roles[_TENANT_A] == "admin"
        assert roles[_TENANT_B] == "member"


class TestSelectTenantAPI:
    def test_select_valid_tenant(self, client, membership_store):
        membership_store.add(_TENANT_A, "test-user", role="admin")

        response = client.post(f"/api/v1/auth/select-tenant/{_TENANT_A}")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_select_tenant_not_member(self, client):
        response = client.post(f"/api/v1/auth/select-tenant/{_TENANT_A}")
        assert response.status_code == 403
        assert "Not a member" in response.json()["detail"]

    def test_select_tenant_nonexistent(self, client):
        response = client.post("/api/v1/auth/select-tenant/nonexistent")
        assert response.status_code == 403
