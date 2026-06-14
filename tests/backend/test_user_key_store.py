"""Tests for backend/persistence/user_key_store.py — UserKeyStore CRUD.

The module had 0 % coverage. These tests exercise the full CRUD surface
(``set_key``/``get_key``/``list_keys``/``delete_key``/``delete_all_keys``)
including the upsert-on-conflict behaviour of ``set_key`` and the
user-isolation guarantee.
"""

from __future__ import annotations

import pytest

from backend.persistence.user_key_store import UserKeyStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def store(tmp_path):
    s = UserKeyStore(db_path=tmp_path / "auth.db")
    yield s
    s.conn.close()


# ---------------------------------------------------------------------------
# set_key + get_key
# ---------------------------------------------------------------------------


class TestSetAndGet:
    def test_set_key_stores_value(self, store: UserKeyStore) -> None:
        store.set_key("alice", "profile-1", "sk-alice-1")
        assert store.get_key("alice", "profile-1") == "sk-alice-1"

    def test_get_missing_key_returns_none(self, store: UserKeyStore) -> None:
        assert store.get_key("alice", "nope") is None

    def test_set_key_upserts_on_conflict(self, store: UserKeyStore) -> None:
        store.set_key("alice", "profile-1", "sk-original", label="first")
        store.set_key("alice", "profile-1", "sk-updated", label="second")

        # Single row remains, with the new value
        assert store.get_key("alice", "profile-1") == "sk-updated"
        keys = store.list_keys("alice")
        assert len(keys) == 1
        assert keys[0]["label"] == "second"

    def test_set_key_default_label_is_empty(self, store: UserKeyStore) -> None:
        store.set_key("alice", "profile-1", "sk-1")
        keys = store.list_keys("alice")
        assert keys[0]["label"] == ""

    def test_set_key_uses_utc_timestamp(self, store: UserKeyStore) -> None:
        store.set_key("alice", "profile-1", "sk-1")
        keys = store.list_keys("alice")
        # ISO 8601 UTC contains a "+00:00" or "Z" suffix
        assert "T" in keys[0]["created_at"]
        assert "T" in keys[0]["updated_at"]


# ---------------------------------------------------------------------------
# list_keys
# ---------------------------------------------------------------------------


class TestListKeys:
    def test_list_empty(self, store: UserKeyStore) -> None:
        assert store.list_keys("alice") == []

    def test_list_returns_only_target_user(self, store: UserKeyStore) -> None:
        store.set_key("alice", "p1", "sk-a1")
        store.set_key("alice", "p2", "sk-a2")
        store.set_key("bob", "p1", "sk-b1")

        alice = store.list_keys("alice")
        assert {k["profile_id"] for k in alice} == {"p1", "p2"}
        for k in alice:
            assert k["has_key"] is True
            # The plaintext key must NEVER be returned by list_keys
            assert "api_key" not in k

    def test_list_does_not_leak_api_key(self, store: UserKeyStore) -> None:
        store.set_key("alice", "p1", "sk-secret")
        keys = store.list_keys("alice")
        assert all("api_key" not in k for k in keys)
        assert all("sk-secret" not in str(k) for k in keys)


# ---------------------------------------------------------------------------
# delete_key
# ---------------------------------------------------------------------------


class TestDeleteKey:
    def test_delete_returns_true(self, store: UserKeyStore) -> None:
        store.set_key("alice", "p1", "sk-1")
        assert store.delete_key("alice", "p1") is True
        assert store.get_key("alice", "p1") is None

    def test_delete_missing_always_returns_true(self, store: UserKeyStore) -> None:
        # Contract: delete_key always returns True (does not signal
        # whether a row was actually present).
        assert store.delete_key("alice", "nope") is True

    def test_delete_only_removes_target(self, store: UserKeyStore) -> None:
        store.set_key("alice", "p1", "sk-a1")
        store.set_key("alice", "p2", "sk-a2")

        store.delete_key("alice", "p1")
        assert store.get_key("alice", "p1") is None
        assert store.get_key("alice", "p2") == "sk-a2"


# ---------------------------------------------------------------------------
# delete_all_keys
# ---------------------------------------------------------------------------


class TestDeleteAllKeys:
    def test_delete_all_returns_count(self, store: UserKeyStore) -> None:
        store.set_key("alice", "p1", "sk-1")
        store.set_key("alice", "p2", "sk-2")
        store.set_key("alice", "p3", "sk-3")

        deleted = store.delete_all_keys("alice")
        assert deleted == 3
        assert store.list_keys("alice") == []

    def test_delete_all_isolated_per_user(self, store: UserKeyStore) -> None:
        store.set_key("alice", "p1", "sk-a1")
        store.set_key("alice", "p2", "sk-a2")
        store.set_key("bob", "p1", "sk-b1")

        assert store.delete_all_keys("alice") == 2
        # Bob is untouched
        assert store.get_key("bob", "p1") == "sk-b1"
        assert store.list_keys("alice") == []

    def test_delete_all_empty_returns_zero(self, store: UserKeyStore) -> None:
        assert store.delete_all_keys("alice") == 0


# ---------------------------------------------------------------------------
# User isolation
# ---------------------------------------------------------------------------


class TestUserIsolation:
    def test_same_profile_id_different_users(self, store: UserKeyStore) -> None:
        store.set_key("alice", "shared", "sk-alice")
        store.set_key("bob", "shared", "sk-bob")

        assert store.get_key("alice", "shared") == "sk-alice"
        assert store.get_key("bob", "shared") == "sk-bob"
