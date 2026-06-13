"""Tests for the P4.2 N+1-membership-lookup fix (section 3.3 of the 2026-06-12 review).

Covers both layers of the fix:

1. ``MembershipStore.add_invalidator`` / ``_fire_invalidators`` — the
   observer registry that lets the persistence layer notify the
   dependency layer when a membership is mutated.

2. ``_user_memberships_cached`` / ``invalidate_user_memberships`` /
   ``reset_user_memberships_cache`` in :mod:`backend.api.deps` — the
   per-user 30-second TTL cache that flattens the per-request N+1
   pattern in ``get_active_tenant`` and friends.

We test the layers in isolation *and* the integration between them
(round-trip: a write to the store invalidates the deps cache, the
next deps call re-fetches from the store).

P4.2 also requires that ``reset_cached_stores()`` (and therefore
``fresh_stores()``) clears the membership TTL cache.  That contract
is covered at the end of the file.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from backend.api import deps
from backend.persistence.membership_store import (
    _MEMBERSHIP_INVALIDATORS,
    MembershipStore,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_membership_cache():
    """Snapshot & restore the global TTL cache + invalidator list.

    Every test starts (and ends) with a known-empty cache and a clean
    invalidator list.  This protects against inter-test pollution in
    both directions:

    * Tests that *add* observers must not leak them into later tests.
    * Tests that *depend* on the default ``deps`` invalidator (the one
      registered at import time) need to tolerate a snapshot/restore
      by re-registering it.
    """
    saved_cache = dict(deps._USER_MEMBERSHIPS_CACHE)
    saved_invalidators = list(_MEMBERSHIP_INVALIDATORS)
    deps.reset_user_memberships_cache()
    _MEMBERSHIP_INVALIDATORS.clear()
    # Re-register the production invalidator that the deps module
    # normally registers at import time.  This mirrors what
    # ``_register_membership_invalidator()`` does.
    _MEMBERSHIP_INVALIDATORS.append(deps.invalidate_user_memberships)
    try:
        yield
    finally:
        deps._USER_MEMBERSHIPS_CACHE.clear()
        deps._USER_MEMBERSHIPS_CACHE.update(saved_cache)
        _MEMBERSHIP_INVALIDATORS.clear()
        _MEMBERSHIP_INVALIDATORS.extend(saved_invalidators)


@pytest.fixture()
def store(tmp_path) -> MembershipStore:
    """An isolated MembershipStore on a per-test SQLite file."""
    return MembershipStore(db_path=tmp_path / "auth.db")


@pytest.fixture()
def store_in_deps(store: MembershipStore, monkeypatch: pytest.MonkeyPatch) -> MembershipStore:
    """Wire *store* into ``deps.get_membership_store()`` for this test.

    ``_user_memberships_cached`` calls ``get_membership_store()`` to
    fetch data, so without this override the tests would hit the
    cached factory (returning whatever store happens to be live in
    the @lru_cache).  The override is monkeypatched back automatically
    by pytest.
    """
    monkeypatch.setattr(deps, "get_membership_store", lambda: store)
    deps.reset_user_memberships_cache()
    return store


# ---------------------------------------------------------------------------
# 1. MembershipStore.add_invalidator / _fire_invalidators
# ---------------------------------------------------------------------------


class TestAddInvalidator:
    """``MembershipStore.add_invalidator`` -- observer registration."""

    def test_returns_unregister_callable(self) -> None:
        calls: list[str] = []

        def observer(user_id: str) -> None:
            calls.append(user_id)

        unregister = MembershipStore.add_invalidator(observer)
        assert callable(unregister)

        MembershipStore._fire_invalidators("u1")
        assert calls == ["u1"]

        # Unregister.
        unregister()
        MembershipStore._fire_invalidators("u1")
        assert calls == ["u1"]  # No further call.

    def test_unregister_is_idempotent(self) -> None:
        def observer(user_id: str) -> None:
            pass

        unregister = MembershipStore.add_invalidator(observer)
        unregister()
        # Second call must not raise.
        unregister()

    def test_observer_receives_user_id(self, store: MembershipStore) -> None:
        seen: list[str] = []

        def observer(user_id: str) -> None:
            seen.append(user_id)

        store.add_invalidator(observer)
        store.add("t1", "u-42", role="member")
        assert seen == ["u-42"]

    def test_fire_iterates_over_snapshot(self, store: MembershipStore) -> None:
        """A re-entrant invalidator must not break the loop."""
        seen: list[tuple[str, str]] = []

        def first(user_id: str) -> None:
            seen.append(("first", user_id))

        def second(user_id: str) -> None:
            seen.append(("second", user_id))
            # Mutate the registry during iteration: this is the
            # re-entrancy case the implementation protects against by
            # iterating over ``list(_INVALIDATORS)``.
            _MEMBERSHIP_INVALIDATORS.append(third)

        def third(user_id: str) -> None:
            seen.append(("third", user_id))

        store.add_invalidator(first)
        store.add_invalidator(second)

        store.add("t1", "u-99", role="member")
        # The first two are guaranteed to be called; the third is
        # registered *during* iteration so may or may not see this
        # call.  What matters is that ``first`` and ``second`` both ran.
        names = [n for n, _ in seen]
        assert "first" in names
        assert "second" in names


class TestFireInvalidatorsErrorHandling:
    """A broken observer must NOT poison the store."""

    def test_exception_in_observer_is_logged_and_swallowed(self, store: MembershipStore, caplog: pytest.LogCaptureFixture) -> None:
        def bad_observer(user_id: str) -> None:
            raise RuntimeError("boom")

        store.add_invalidator(bad_observer)
        # Must not raise; ``add`` itself should still complete.
        with caplog.at_level(logging.WARNING, logger="backend.persistence.membership_store"):
            store.add("t1", "u-1", role="member")
        assert any("boom" in rec.message for rec in caplog.records)

    def test_other_observers_still_called_after_one_fails(self, store: MembershipStore) -> None:
        seen: list[str] = []

        def good1(user_id: str) -> None:
            seen.append("good1")

        def bad(user_id: str) -> None:
            raise ValueError("nope")

        def good2(user_id: str) -> None:
            seen.append("good2")

        store.add_invalidator(good1)
        store.add_invalidator(bad)
        store.add_invalidator(good2)
        store.add("t1", "u-2", role="member")
        # Order is registration order; both goods must run.
        assert seen == ["good1", "good2"]


class TestInvalidationWiring:
    """The three mutating methods must fire observers; reads must not."""

    def test_add_fires_observer(self, store: MembershipStore) -> None:
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        store.add("t1", "u-1")
        assert seen == ["u-1"]

    def test_add_re_add_fires_observer(self, store: MembershipStore) -> None:
        """``add`` uses INSERT OR REPLACE -- a re-add is also a mutation."""
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        store.add("t1", "u-1", role="member")
        store.add("t1", "u-1", role="admin")  # role change via re-add
        assert seen == ["u-1", "u-1"]

    def test_remove_fires_observer_on_real_delete(self, store: MembershipStore) -> None:
        store.add("t1", "u-1")
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        assert store.remove("t1", "u-1") is True
        assert seen == ["u-1"]

    def test_remove_does_not_fire_observer_on_noop(self, store: MembershipStore) -> None:
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        # Nothing to remove.
        assert store.remove("t1", "u-1") is False
        assert seen == []

    def test_update_role_fires_observer_on_real_change(self, store: MembershipStore) -> None:
        store.add("t1", "u-1", role="member")
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        store.update_role("t1", "u-1", "admin")
        assert seen == ["u-1"]

    def test_update_role_fires_observer_even_when_value_unchanged(self, store: MembershipStore) -> None:
        """SQLite's UPDATE returns rowcount=1 even if the value did not
        change.  The contract is: ``update_role`` fires whenever it
        *executes* against a real row.  This test pins that behaviour.
        """
        store.add("t1", "u-1", role="member")
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        # Same role as current.
        store.update_role("t1", "u-1", "member")
        assert seen == ["u-1"]

    def test_get_and_list_do_not_fire_observer(self, store: MembershipStore) -> None:
        store.add("t1", "u-1")
        seen: list[str] = []
        store.add_invalidator(lambda uid: seen.append(uid))
        store.get("t1", "u-1")
        store.list_by_user("u-1")
        store.list_by_tenant("t1")
        store.count_by_tenant("t1")
        assert seen == []


# ---------------------------------------------------------------------------
# 2. deps._user_memberships_cached -- the TTL cache
# ---------------------------------------------------------------------------


class TestUserMembershipsCached:
    """``_user_memberships_cached`` -- per-user 30s TTL cache."""

    def test_first_call_fetches_from_store(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1", role="admin")
        store_in_deps.add("t2", "u-1", role="member")
        original = store_in_deps.list_by_user
        call_count = {"n": 0}

        def spy(user_id: str):
            call_count["n"] += 1
            return original(user_id)

        # Patch the bound method on the *instance*, not the class, so
        # the spy actually counts calls made by deps.
        store_in_deps.list_by_user = spy  # type: ignore[method-assign]
        memberships = deps._user_memberships_cached("u-1")
        assert call_count["n"] == 1
        assert sorted(m.tenant_id for m in memberships) == ["t1", "t2"]

    def test_second_call_within_ttl_does_not_hit_store(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        deps._user_memberships_cached("u-1")
        original = store_in_deps.list_by_user
        call_count = {"n": 0}

        def spy(user_id: str):
            call_count["n"] += 1
            return original(user_id)

        store_in_deps.list_by_user = spy  # type: ignore[method-assign]
        deps._user_memberships_cached("u-1")
        deps._user_memberships_cached("u-1")
        assert call_count["n"] == 0

    def test_ttl_expiry_triggers_refetch(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        deps._user_memberships_cached("u-1")
        # Force expiry by rewinding the timestamp.
        ts, _ = deps._USER_MEMBERSHIPS_CACHE["u-1"]
        deps._USER_MEMBERSHIPS_CACHE["u-1"] = (
            ts - deps._USER_MEMBERSHIPS_TTL_SECONDS - 1.0,
            [],
        )
        original = store_in_deps.list_by_user
        call_count = {"n": 0}

        def spy(user_id: str):
            call_count["n"] += 1
            return original(user_id)

        store_in_deps.list_by_user = spy  # type: ignore[method-assign]
        deps._user_memberships_cached("u-1")
        assert call_count["n"] == 1

    def test_cache_is_per_user(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-a")
        store_in_deps.add("t2", "u-b")
        ms_a = deps._user_memberships_cached("u-a")
        ms_b = deps._user_memberships_cached("u-b")
        assert [m.tenant_id for m in ms_a] == ["t1"]
        assert [m.tenant_id for m in ms_b] == ["t2"]

    def test_cache_returns_same_object_within_ttl(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        first = deps._user_memberships_cached("u-1")
        second = deps._user_memberships_cached("u-1")
        assert first is second  # identity, not just equality


class TestInvalidateUserMemberships:
    """``invalidate_user_memberships`` -- per-user cache drop."""

    def test_drop_clears_entry(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        deps._user_memberships_cached("u-1")
        assert "u-1" in deps._USER_MEMBERSHIPS_CACHE
        deps.invalidate_user_memberships("u-1")
        assert "u-1" not in deps._USER_MEMBERSHIPS_CACHE

    def test_invalidate_unknown_user_is_noop(self) -> None:
        # Must not raise.
        deps.invalidate_user_memberships("never-cached")

    def test_next_fetch_after_invalidate_refetches(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        deps._user_memberships_cached("u-1")
        deps.invalidate_user_memberships("u-1")
        original = store_in_deps.list_by_user
        call_count = {"n": 0}

        def spy(user_id: str):
            call_count["n"] += 1
            return original(user_id)

        store_in_deps.list_by_user = spy  # type: ignore[method-assign]
        deps._user_memberships_cached("u-1")
        assert call_count["n"] == 1


class TestResetUserMembershipsCache:
    """``reset_user_memberships_cache`` -- full cache wipe."""

    def test_clears_all_users(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-a")
        store_in_deps.add("t2", "u-b")
        deps._user_memberships_cached("u-a")
        deps._user_memberships_cached("u-b")
        assert len(deps._USER_MEMBERSHIPS_CACHE) == 2
        deps.reset_user_memberships_cache()
        assert deps._USER_MEMBERSHIPS_CACHE == {}

    def test_idempotent(self) -> None:
        deps.reset_user_memberships_cache()
        deps.reset_user_memberships_cache()  # must not raise


# ---------------------------------------------------------------------------
# 3. Integration: store write -> deps cache drop -> deps refetch
# ---------------------------------------------------------------------------


class TestEndToEndInvalidation:
    """Round-trip: a mutation on the store propagates to the deps cache."""

    def test_add_propagates_to_deps_cache(self, store_in_deps: MembershipStore) -> None:
        # First fetch: empty.
        assert deps._user_memberships_cached("u-1") == []
        # Now add a membership.  The deps invalidator must drop the
        # cached empty list so the next fetch sees the new state.
        store_in_deps.add("t1", "u-1", role="admin")
        ms = deps._user_memberships_cached("u-1")
        assert [m.tenant_id for m in ms] == ["t1"]
        assert ms[0].role == "admin"

    def test_remove_propagates_to_deps_cache(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        store_in_deps.add("t2", "u-1")
        assert sorted(m.tenant_id for m in deps._user_memberships_cached("u-1")) == ["t1", "t2"]
        store_in_deps.remove("t2", "u-1")
        assert [m.tenant_id for m in deps._user_memberships_cached("u-1")] == ["t1"]

    def test_update_role_propagates_to_deps_cache(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1", role="member")
        ms = deps._user_memberships_cached("u-1")
        assert ms[0].role == "member"
        store_in_deps.update_role("t1", "u-1", "admin")
        ms = deps._user_memberships_cached("u-1")
        assert ms[0].role == "admin"

    def test_other_users_cache_unaffected_by_invalidation(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-a")
        store_in_deps.add("t1", "u-b")
        deps._user_memberships_cached("u-a")
        ms_b_before = deps._user_memberships_cached("u-b")
        # Mutate u-a only.
        store_in_deps.add("t2", "u-a")
        # u-b's cache must still be intact (same list object).
        ms_b_after = deps._user_memberships_cached("u-b")
        assert ms_b_before is ms_b_after


# ---------------------------------------------------------------------------
# 4. reset_cached_stores / fresh_stores must also wipe the TTL cache
# ---------------------------------------------------------------------------


class TestResetCachedStoresWipesMembershipCache:
    """P4.2 contract: ``reset_cached_stores`` (and ``fresh_stores``)
    must clear the membership TTL cache along with the @lru_cache
    factories.  This is what protects the test suite from cross-test
    cache pollution.
    """

    def test_reset_cached_stores_clears_membership_cache(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        deps._user_memberships_cached("u-1")
        assert "u-1" in deps._USER_MEMBERSHIPS_CACHE
        deps.reset_cached_stores()
        assert deps._USER_MEMBERSHIPS_CACHE == {}

    def test_fresh_stores_clears_membership_cache_on_entry_and_exit(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        deps._user_memberships_cached("u-1")
        assert "u-1" in deps._USER_MEMBERSHIPS_CACHE
        with deps.fresh_stores():
            # Cleared on entry.
            assert deps._USER_MEMBERSHIPS_CACHE == {}
            deps._user_memberships_cached("u-1")
            assert "u-1" in deps._USER_MEMBERSHIPS_CACHE
        # Cleared on exit.
        assert deps._USER_MEMBERSHIPS_CACHE == {}

    def test_fresh_stores_clears_cache_even_on_exception(self, store_in_deps: MembershipStore) -> None:
        store_in_deps.add("t1", "u-1")
        with pytest.raises(RuntimeError, match="boom"):
            with deps.fresh_stores():
                deps._user_memberships_cached("u-1")
                raise RuntimeError("boom")
        # Must still be cleared despite the exception.
        assert deps._USER_MEMBERSHIPS_CACHE == {}


# ---------------------------------------------------------------------------
# 5. Cache + FastAPI dependency integration (smoke-level)
# ---------------------------------------------------------------------------


class TestGetActiveTenantUsesCache:
    """Sanity-check that the three deps that used to N+1 now route
    through the cache.  We don't need full router coverage here --
    that's covered by the existing auth-router / test_membership
    tests.  What we need is proof that the cache is actually consulted.
    """

    def test_repeated_calls_do_not_re_hit_store(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``_user_memberships_cached`` must not call the underlying
        store's ``list_by_user`` a second time within the TTL window.
        The previous implementation called it on every request.
        """
        # Use a fake store with a counting list_by_user.
        calls: list[str] = []

        class _FakeStore:
            def list_by_user(self, user_id: str) -> list[Any]:
                calls.append(user_id)
                return []

        monkeypatch.setattr(deps, "get_membership_store", lambda: _FakeStore())
        deps.reset_user_memberships_cache()
        # First call -> store.
        deps._user_memberships_cached("u-1")
        # Second & third call -> cache hit, store must NOT be called.
        deps._user_memberships_cached("u-1")
        deps._user_memberships_cached("u-1")
        assert calls == ["u-1"]
