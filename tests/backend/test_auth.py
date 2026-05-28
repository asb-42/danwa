"""Tests for authentication system — JWT, password hashing, UserStore, auth endpoints."""

from __future__ import annotations

import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from backend.models.user import User
from backend.persistence.user_store import UserStore

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "securepassword123"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_hashes_for_same_password(self):
        h1 = hash_password("test")
        h2 = hash_password("test")
        assert h1 != h2  # bcrypt uses random salt


# ---------------------------------------------------------------------------
# JWT tokens
# ---------------------------------------------------------------------------


def _make_user(user_id: str = "test-id", role: str = "admin") -> User:
    return User(
        id=user_id,
        email="test@example.com",
        display_name="Test User",
        password_hash="hashed",
        role=role,
        tenant_id="_default",
    )


class TestJWT:
    def test_create_and_decode_access_token(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "test-secret-key-for-testing")
        user = _make_user()
        token = create_access_token(user)
        data = decode_token(token)
        assert data.user_id == "test-id"
        assert data.email == "test@example.com"
        assert data.role == "admin"
        assert data.token_type == "access"

    def test_create_and_decode_refresh_token(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "test-secret-key-for-testing")
        user = _make_user()
        token = create_refresh_token(user)
        data = decode_token(token)
        assert data.user_id == "test-id"
        assert data.token_type == "refresh"

    def test_expired_token_raises(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "test-secret-key-for-testing")
        user = _make_user()
        token = create_access_token(user, expires_delta=timedelta(seconds=-1))
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token(token)

    def test_invalid_token_raises(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "test-secret-key-for-testing")
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token("not.a.valid.token")

    def test_wrong_secret_raises(self, monkeypatch):
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "secret-1")
        user = _make_user()
        token = create_access_token(user)
        monkeypatch.setattr("backend.core.security.settings.jwt_secret_key", "secret-2")
        from jose import JWTError

        with pytest.raises(JWTError):
            decode_token(token)


# ---------------------------------------------------------------------------
# UserStore
# ---------------------------------------------------------------------------


class TestUserStore:
    def _make_store(self):
        tmpdir = tempfile.mkdtemp()
        return UserStore(db_path=Path(tmpdir) / "test_auth.db")

    def test_create_and_get(self):
        store = self._make_store()
        user = store.create("a@b.com", "Alice", "hashed_pw", role="admin")
        assert user.email == "a@b.com"
        assert user.display_name == "Alice"
        assert user.role == "admin"
        assert user.is_active is True

        fetched = store.get(user.id)
        assert fetched is not None
        assert fetched.email == "a@b.com"

    def test_get_by_email(self):
        store = self._make_store()
        store.create("x@y.com", "X", "h")
        found = store.get_by_email("x@y.com")
        assert found is not None
        assert found.email == "x@y.com"

        assert store.get_by_email("nonexistent@z.com") is None

    def test_unique_email_constraint(self):
        store = self._make_store()
        store.create("dup@test.com", "First", "h")
        import sqlite3

        with pytest.raises(sqlite3.IntegrityError):
            store.create("dup@test.com", "Second", "h")

    def test_list_by_tenant(self):
        store = self._make_store()
        store.create("a@t.com", "A", "h", tenant_id="t1")
        store.create("b@t.com", "B", "h", tenant_id="t1")
        store.create("c@t.com", "C", "h", tenant_id="t2")
        assert len(store.list_by_tenant("t1")) == 2
        assert len(store.list_by_tenant("t2")) == 1

    def test_update(self):
        store = self._make_store()
        user = store.create("u@t.com", "Old", "h")
        updated = store.update(user.id, display_name="New", role="editor")
        assert updated.display_name == "New"
        assert updated.role == "editor"

    def test_update_last_login(self):
        store = self._make_store()
        user = store.create("l@t.com", "L", "h")
        assert user.last_login_at is None
        store.update_last_login(user.id)
        updated = store.get(user.id)
        assert updated.last_login_at is not None

    def test_delete(self):
        store = self._make_store()
        user = store.create("d@t.com", "D", "h")
        assert store.get(user.id) is not None
        store.delete(user.id)
        assert store.get(user.id) is None

    def test_count(self):
        store = self._make_store()
        assert store.count() == 0
        store.create("1@t.com", "1", "h")
        assert store.count() == 1
        store.create("2@t.com", "2", "h")
        assert store.count() == 2


# ---------------------------------------------------------------------------
# Seed admin
# ---------------------------------------------------------------------------


class TestSeedAdmin:
    def test_ensure_admin_creates_first_user(self, monkeypatch):
        tmpdir = tempfile.mkdtemp()

        from backend.core import seed

        monkeypatch.setattr(seed, "UserStore", lambda: UserStore(db_path=Path(tmpdir) / "auth.db"))

        from backend.core.seed import ensure_admin_user

        ensure_admin_user()

        store = UserStore(db_path=Path(tmpdir) / "auth.db")
        assert store.count() == 1
        admin = store.get_by_email("admin@danwa.local")
        assert admin is not None
        assert admin.role == "admin"

    def test_ensure_admin_is_idempotent(self, monkeypatch):
        tmpdir = tempfile.mkdtemp()

        from backend.core import seed

        monkeypatch.setattr(seed, "UserStore", lambda: UserStore(db_path=Path(tmpdir) / "auth.db"))

        from backend.core.seed import ensure_admin_user

        ensure_admin_user()
        ensure_admin_user()  # Second call should be no-op

        store = UserStore(db_path=Path(tmpdir) / "auth.db")
        assert store.count() == 1
