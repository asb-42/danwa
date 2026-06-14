"""Tests for backend/api/routers/auth.py — authentication endpoints.

The router had 39 % coverage.  These tests cover:

  * registration (first-user-admin promotion, duplicate email 409, error 500)
  * login (success, unknown email, wrong password, deactivated user)
  * refresh (success, JWTError, wrong type, missing user, deactivated)
  * /me, PUT /me, PUT /password
  * admin-only user list, invite, delete (incl. self-delete guard)
  * my-tenants and select-tenant (auth disabled dev-mode paths + membership path)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.deps import get_current_user
from backend.core.security import create_access_token, hash_password
from backend.persistence.membership_store import MembershipStore
from backend.persistence.user_store import UserStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def user_store(tmp_path):
    """Isolated UserStore with temp database."""
    return UserStore(db_path=tmp_path / "test_auth.db")


@pytest.fixture()
def membership_store(tmp_path):
    """Isolated MembershipStore with temp database (shares file with user_store)."""
    return MembershipStore(db_path=tmp_path / "test_auth.db")


@pytest.fixture()
def admin_user(user_store):
    """Seed an admin user (in the user_store, so it can be looked up)."""
    return user_store.create(
        email="admin@example.com",
        display_name="Admin",
        password_hash=hash_password("adminpass"),
        role="admin",
        tenant_id="_default",
    )


@pytest.fixture()
def regular_user(user_store):
    """Seed a regular viewer user."""
    return user_store.create(
        email="user@example.com",
        display_name="User",
        password_hash=hash_password("userpass"),
        role="viewer",
        tenant_id="_default",
    )


@pytest.fixture()
def app_with_auth(app, user_store, membership_store, admin_user):
    """App with overridden user_store + membership_store + get_current_user.

    We override ``get_current_user`` to return the seeded admin user so
    that /me, /password, delete-self, and membership-based tests see
    the right principal.  Test functions can re-override if needed.
    """
    from backend.api.deps import get_membership_store, get_user_store

    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_membership_store] = lambda: membership_store
    app.dependency_overrides[get_current_user] = lambda: admin_user
    # Clear any cached references
    get_user_store.cache_clear()
    get_membership_store.cache_clear()
    yield app
    app.dependency_overrides.pop(get_user_store, None)
    app.dependency_overrides.pop(get_membership_store, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture()
def client_auth(app_with_auth) -> TestClient:
    return TestClient(app_with_auth)


@pytest.fixture()
def app_empty_store(app, user_store, membership_store):
    """App with overridden stores but no seeded admin user.

    Used for tests that need an empty user_store -- e.g. verifying the
    first-user-becomes-admin promotion logic.
    """
    from backend.api.deps import get_membership_store, get_user_store

    app.dependency_overrides[get_user_store] = lambda: user_store
    app.dependency_overrides[get_membership_store] = lambda: membership_store
    get_user_store.cache_clear()
    get_membership_store.cache_clear()
    yield app
    app.dependency_overrides.pop(get_user_store, None)
    app.dependency_overrides.pop(get_membership_store, None)


@pytest.fixture()
def client_empty_store(app_empty_store) -> TestClient:
    return TestClient(app_empty_store)


# ---------------------------------------------------------------------------
# /register
# ---------------------------------------------------------------------------


class TestRegister:
    def test_first_user_becomes_admin(self, client_empty_store: TestClient):
        """When the user_store is empty, the first registered user is auto-promoted to admin."""
        resp = client_empty_store.post(
            "/api/v1/auth/register",
            json={
                "email": "first@example.com",
                "display_name": "First",
                "password": "supersecret",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "first@example.com"
        assert data["role"] == "admin"
        assert "password" not in data
        assert "password_hash" not in data

    def test_duplicate_email_returns_409(self, client_auth: TestClient, admin_user):
        resp = client_auth.post(
            "/api/v1/auth/register",
            json={
                "email": admin_user.email,
                "display_name": "X",
                "password": "p4ssw0rd",
            },
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    def test_second_user_becomes_viewer(self, client_auth: TestClient, admin_user):
        resp = client_auth.post(
            "/api/v1/auth/register",
            json={
                "email": "second@example.com",
                "display_name": "Second",
                "password": "p4ssw0rd",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "viewer"

    def test_short_password_rejected(self, client_auth: TestClient):
        resp = client_auth.post(
            "/api/v1/auth/register",
            json={
                "email": "x@example.com",
                "display_name": "X",
                "password": "short",
            },
        )
        # Pydantic validation rejects short passwords
        assert resp.status_code in (422, 400)

    def test_register_internal_error_returns_500(self, client_empty_store: TestClient, user_store, monkeypatch):
        """When user_store.create raises, /register returns 500."""

        def _boom(**kwargs):
            raise RuntimeError("db connection lost")

        monkeypatch.setattr(user_store, "create", _boom)
        resp = client_empty_store.post(
            "/api/v1/auth/register",
            json={
                "email": "boom@example.com",
                "display_name": "Boom",
                "password": "longenough",
            },
        )
        assert resp.status_code == 500
        assert "Failed to create user" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /login
# ---------------------------------------------------------------------------


class TestLogin:
    def test_login_success(self, client_auth: TestClient, regular_user):
        resp = client_auth.post(
            "/api/v1/auth/login",
            json={"email": regular_user.email, "password": "userpass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == regular_user.email

    def test_login_unknown_email(self, client_auth: TestClient):
        resp = client_auth.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "whatever"},
        )
        assert resp.status_code == 401

    def test_login_wrong_password(self, client_auth: TestClient, regular_user):
        resp = client_auth.post(
            "/api/v1/auth/login",
            json={"email": regular_user.email, "password": "WRONG"},
        )
        assert resp.status_code == 401

    def test_login_deactivated_user(self, client_auth: TestClient, user_store, regular_user):
        # Deactivate the user
        user_store.update(regular_user.id, is_active=False)
        resp = client_auth.post(
            "/api/v1/auth/login",
            json={"email": regular_user.email, "password": "userpass"},
        )
        assert resp.status_code == 403
        assert "deactivated" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /refresh
# ---------------------------------------------------------------------------


class TestRefresh:
    def test_refresh_success(self, client_auth: TestClient, regular_user):
        from backend.core.security import create_refresh_token

        token = create_refresh_token(regular_user)
        resp = client_auth.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client_auth: TestClient):
        resp = client_auth.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt"})
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(self, client_auth: TestClient, regular_user):
        """An access token is not a refresh token."""
        access = create_access_token(regular_user)
        resp = client_auth.post("/api/v1/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401
        assert "not a refresh token" in resp.json()["detail"]

    def test_refresh_user_not_found(self, client_auth: TestClient):
        from backend.core.security import create_refresh_token

        # Create a fake user object
        from backend.models.user import User

        fake_user = User(
            id="ghost-user-id",
            email="g@example.com",
            display_name="G",
            password_hash="",
            role="viewer",
            tenant_id="_default",
        )
        token = create_refresh_token(fake_user)
        resp = client_auth.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 401
        assert "User not found" in resp.json()["detail"]

    def test_refresh_deactivated_user(self, client_auth: TestClient, user_store, regular_user):
        """A deactivated user holding a valid refresh token is rejected with 403."""
        from backend.core.security import create_refresh_token

        # Deactivate the user, then try to use the refresh token issued
        # before deactivation.
        token = create_refresh_token(regular_user)
        user_store.update(regular_user.id, is_active=False)
        resp = client_auth.post("/api/v1/auth/refresh", json={"refresh_token": token})
        assert resp.status_code == 403
        assert "deactivated" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------


class TestMe:
    def test_get_me(self, client_auth: TestClient, admin_user):
        resp = client_auth.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == admin_user.email
        assert data["role"] == "admin"

    def test_update_me(self, client_auth: TestClient, admin_user):
        resp = client_auth.put(
            "/api/v1/auth/me",
            json={"display_name": "Renamed Admin"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Renamed Admin"

    def test_update_me_fails_when_update_returns_none(self, client_auth: TestClient, admin_user, user_store, monkeypatch):
        """When user_store.update returns None, PUT /me returns 500."""
        # Patch update to return None, simulating a deletion race.
        monkeypatch.setattr(user_store, "update", lambda uid, **kw: None)
        resp = client_auth.put(
            "/api/v1/auth/me",
            json={"display_name": "Ghost"},
        )
        assert resp.status_code == 500
        assert "Failed to update profile" in resp.json()["detail"]

    def test_change_password(self, client_auth: TestClient, admin_user, user_store):
        resp = client_auth.put(
            "/api/v1/auth/password",
            json={
                "current_password": "adminpass",
                "new_password": "newadminpass",
            },
        )
        assert resp.status_code == 200
        # Verify the password was actually changed
        updated = user_store.get(admin_user.id)
        assert updated.password_hash != admin_user.password_hash
        # Login with the new password
        resp = client_auth.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "newadminpass"},
        )
        assert resp.status_code == 200

    def test_change_password_wrong_current(self, client_auth: TestClient, admin_user):
        resp = client_auth.put(
            "/api/v1/auth/password",
            json={
                "current_password": "WRONG",
                "new_password": "anything",
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /users (admin)
# ---------------------------------------------------------------------------


class TestAdminUsers:
    def test_list_users(self, client_auth: TestClient, admin_user, regular_user):
        resp = client_auth.get("/api/v1/auth/users")
        assert resp.status_code == 200
        data = resp.json()
        emails = {u["email"] for u in data}
        assert {admin_user.email, regular_user.email} <= emails

    def test_invite_user(self, client_auth: TestClient, admin_user):
        resp = client_auth.post(
            "/api/v1/auth/users/invite",
            json={
                "email": "invited@example.com",
                "display_name": "Invited",
                "password": "invitedpass",
                "role": "viewer",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["email"] == "invited@example.com"

    def test_invite_duplicate(self, client_auth: TestClient, admin_user, regular_user):
        resp = client_auth.post(
            "/api/v1/auth/users/invite",
            json={
                "email": regular_user.email,
                "display_name": "Dup",
                "password": "dupdup1234",
                "role": "viewer",
            },
        )
        assert resp.status_code == 409

    def test_invite_internal_error_returns_500(self, client_auth: TestClient, admin_user, user_store, monkeypatch):
        """When user_store.create raises, /users/invite returns 500."""

        def _boom(**kwargs):
            raise RuntimeError("db connection lost")

        monkeypatch.setattr(user_store, "create", _boom)
        resp = client_auth.post(
            "/api/v1/auth/users/invite",
            json={
                "email": "invitee@example.com",
                "display_name": "Invitee",
                "password": "inviteepass",
                "role": "viewer",
            },
        )
        assert resp.status_code == 500
        assert "Failed to create user" in resp.json()["detail"]

    def test_delete_user(self, client_auth: TestClient, admin_user, regular_user):
        resp = client_auth.delete(f"/api/v1/auth/users/{regular_user.id}")
        assert resp.status_code == 204

    def test_delete_self_rejected(self, client_auth: TestClient, admin_user):
        resp = client_auth.delete(f"/api/v1/auth/users/{admin_user.id}")
        assert resp.status_code == 400
        assert "Cannot delete yourself" in resp.json()["detail"]

    def test_delete_unknown_user(self, client_auth: TestClient, admin_user):
        resp = client_auth.delete("/api/v1/auth/users/ghost-id")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /my-tenants
# ---------------------------------------------------------------------------


class TestMyTenants:
    def test_dev_mode_returns_all_tenants(
        self,
        client_auth: TestClient,
        admin_user,
        tenant_store,
        default_tenant,
    ):
        # _disable_auth in conftest sets auth_enabled=False, so dev mode kicks in.
        # The dev user has no memberships, so all tenants should be returned.
        resp = client_auth.get("/api/v1/auth/my-tenants")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # All returned tenants should be marked admin in dev mode
        for m in data:
            assert m["role"] == "admin"

    def test_with_memberships(self, client_auth: TestClient, admin_user, membership_store):
        # Add a membership for the admin_user (the get_current_user target)
        membership_store.add("_default", admin_user.id, role="member")
        resp = client_auth.get("/api/v1/auth/my-tenants")
        assert resp.status_code == 200
        data = resp.json()
        # Membership-based branch: returns the user's actual memberships
        assert any(m["role"] == "member" for m in data)


# ---------------------------------------------------------------------------
# /select-tenant/{tid}
# ---------------------------------------------------------------------------


class TestSelectTenant:
    def test_dev_mode_select_any_tenant(self, client_auth: TestClient, admin_user, default_tenant):
        resp = client_auth.post(f"/api/v1/auth/select-tenant/{default_tenant}")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        # Dev mode -> role_override is admin
        # Decode to check claims
        from jose import jwt as jose_jwt

        payload = jose_jwt.get_unverified_claims(data["access_token"])
        assert payload.get("tenant_id") == default_tenant
        assert payload.get("role") == "admin"

    def test_with_membership_uses_membership_role(self, client_auth: TestClient, admin_user, membership_store, default_tenant):
        # Add membership for admin_user (the get_current_user target)
        membership_store.add(default_tenant, admin_user.id, role="member")
        resp = client_auth.post(f"/api/v1/auth/select-tenant/{default_tenant}")
        assert resp.status_code == 200
        from jose import jwt as jose_jwt

        data = resp.json()
        payload = jose_jwt.get_unverified_claims(data["access_token"])
        # The token role reflects the membership role, not the global role
        assert payload.get("role") == "member"

    def test_unknown_membership_and_auth_enabled(self, admin_user, client_auth, default_tenant):
        """When auth is enabled and user is not a member, returns 403.

        We override ``get_settings`` to return a Settings with
        ``auth_enabled=True`` so the dev-mode bypass is disabled.
        """
        from backend.api.deps import get_settings

        class _S:
            def __init__(self):
                self.auth_enabled = True

        # Replace the override for the duration of this test
        original_override = client_auth.app.dependency_overrides.get(get_settings)
        client_auth.app.dependency_overrides[get_settings] = lambda: _S()
        try:
            resp = client_auth.post(f"/api/v1/auth/select-tenant/{default_tenant}")
            assert resp.status_code == 403
        finally:
            if original_override is not None:
                client_auth.app.dependency_overrides[get_settings] = original_override
            else:
                client_auth.app.dependency_overrides.pop(get_settings, None)
