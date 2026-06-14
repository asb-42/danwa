"""Tests for P4.5+ §4.1 — UserKeyStore is process-cached in LLMService.

The previous code instantiated ``UserKeyStore()`` (and therefore opened a
fresh sqlite3 connection + Fernet PRAGMA) on every per-user LLM call.
These tests verify that:

  * the same store is reused across two consecutive calls
  * the cache is transparently rebuilt when the cached store's
    connection is dead (master-key rotation / file swap)
  * the cache stays ``None`` when the BYOK branch is not taken
    (no profile-level api_key, no ``_user_id``)
"""

from __future__ import annotations

import sqlite3
from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_service import LLMService


@pytest.fixture()
def svc() -> LLMService:
    """A bare LLMService with no profile and no user_id.

    We only exercise ``_get_user_key_store`` and the BYOK branch of
    ``_resolve_api_key``, neither of which require a profile to be
    loaded.
    """
    return LLMService()


class TestUserKeyStoreCache:
    """P4.5+ §4.1 — UserKeyStore cache."""

    def test_first_call_builds_store(self, svc: LLMService) -> None:
        assert svc._user_key_store_cache is None
        with patch("backend.persistence.user_key_store.UserKeyStore") as mock_store:  # noqa: N806
            instance = MagicMock(name="UserKeyStoreInstance")
            mock_store.return_value = instance
            store = svc._get_user_key_store()
        assert store is instance
        assert svc._user_key_store_cache is instance
        # _init_db is the alive-probe; it must have been called at least once.
        assert instance._init_db.called

    def test_second_call_reuses_store(self, svc: LLMService) -> None:
        """The second call must NOT re-instantiate UserKeyStore."""
        with patch("backend.persistence.user_key_store.UserKeyStore") as mock_store:  # noqa: N806
            instance = MagicMock(name="UserKeyStoreInstance")
            mock_store.return_value = instance
            store1 = svc._get_user_key_store()
            store2 = svc._get_user_key_store()
        # Same instance — cache hit.
        assert store1 is store2
        # UserKeyStore() was constructed exactly once.
        assert mock_store.call_count == 1

    def test_dead_connection_triggers_rebuild(self, svc: LLMService) -> None:
        """If the cached store's connection raises on the alive-probe,
        ``_get_user_key_store`` must drop the cache and rebuild.

        We simulate a dead connection by making ``_init_db`` raise
        ``OperationalError`` on the first call, and verify that the
        second call gets a fresh ``UserKeyStore`` instance.
        """
        with patch("backend.persistence.user_key_store.UserKeyStore") as mock_store:  # noqa: N806
            dead = MagicMock(name="DeadStore")
            alive = MagicMock(name="AliveStore")
            dead._init_db.side_effect = sqlite3.OperationalError("database is locked")
            mock_store.side_effect = [dead, alive]

            first = svc._get_user_key_store()
            # The dead one was probed and rejected, so the cache should
            # hold the *second* (alive) instance, not the dead one.
            assert first is alive
            assert svc._user_key_store_cache is alive

        # Subsequent call must not re-instantiate — the rebuilt cache
        # is good and its _init_db probe is a no-op success.
        with patch("backend.persistence.user_key_store.UserKeyStore") as mock_store2:  # noqa: N806
            mock_store2.return_value = MagicMock(name="AnotherStore")
            svc._get_user_key_store()
        assert mock_store2.call_count == 0

    def test_get_key_failure_does_not_break_cache(self, svc: LLMService) -> None:
        """A failure in the public ``get_key`` path is still swallowed by
        ``_resolve_api_key`` and the cache stays ``None`` if the BYOK
        branch is not taken.

        This is a regression guard: the BYOK branch in
        ``_resolve_api_key`` is the only caller of
        ``_get_user_key_store`` and we want to make sure the cache
        stays ``None`` when no profile is loaded and no ``_user_id``
        is set — i.e. the BYOK branch is short-circuited before
        touching the cache.
        """
        # No profile loaded → no user_id → BYOK branch skipped.
        assert svc._user_key_store_cache is None
        with patch.dict("os.environ", {}, clear=True):
            try:
                svc._resolve_api_key(required=False)
            except Exception:
                pass  # outcome irrelevant; cache invariant is what matters
        assert svc._user_key_store_cache is None
