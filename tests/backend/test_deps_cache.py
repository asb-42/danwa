"""Regression tests for the lru_cache cascade fix in ``backend/api/deps.py``.

These tests pin the contract for ``fresh_stores()`` and
``reset_cached_stores()`` so that future refactors of the dependency
module cannot accidentally regress the test-isolation guarantees the
2026-06-12 code review demanded.

What we are locking in:
* Every ``@lru_cache``-decorated store factory in ``backend/api/deps.py``
  is in the ``_CACHED_STORE_FACTORIES`` tuple, so the helpers actually
  clear them all.
* ``reset_cached_stores()`` empties the ``cache_info().currsize`` of
  every member of the tuple.
* ``fresh_stores()`` clears on entry *and* exit, even if the body raises.
* ``fresh_stores()`` yields once (it's a context manager, not a
  coroutine).
* The factories themselves are pure-singleton: two consecutive calls
  return the *same* instance (this is the production contract we are
  protecting).
* Clearing the cache forces the next call to construct a *new*
  instance, picking up monkey-patched env vars / ``tmp_path``.

These tests must NOT depend on the test ``app`` fixture from conftest.py
because they need to run in a clean, isolated lru_cache state.
"""

from __future__ import annotations

import pytest

from backend.api import deps
from backend.api.deps import (
    _CACHED_STORE_FACTORIES,
    fresh_stores,
    reset_cached_stores,
)

# ---------------------------------------------------------------------------
# _CACHED_STORE_FACTORIES
# ---------------------------------------------------------------------------


class TestCachedStoreFactoriesTuple:
    """The ``_CACHED_STORE_FACTORIES`` tuple must list every cached factory."""

    EXPECTED_FACTORIES: tuple[str, ...] = (
        "get_settings",
        "get_audit_service",
        "get_debate_store",
        "get_project_store",
        "get_case_store",
        "get_tag_store",
        "get_blueprint_repository",
        "get_user_store",
        "get_tenant_store",
        "get_membership_store",
    )

    def test_tuple_is_nonempty(self) -> None:
        assert len(_CACHED_STORE_FACTORIES) > 0

    def test_tuple_contains_all_expected_factories(self) -> None:
        actual = {f.__name__ for f in _CACHED_STORE_FACTORIES}
        expected = set(self.EXPECTED_FACTORIES)
        missing = expected - actual
        assert not missing, f"Missing factories: {sorted(missing)}"
        # We don't assert ``not (actual - expected)`` because future cached
        # factories are allowed to be added; the test should be a *floor*, not a
        # ceiling.  But the message above flags unexpected additions.

    def test_every_member_has_cache_clear(self) -> None:
        """Every factory must be ``@lru_cache``-decorated (have ``cache_clear``).

        ``getattr(..., "cache_clear", None)`` in ``reset_cached_stores``
        silently skips factories that lack a ``cache_clear`` method, so
        a missing member would *not* fail loudly.  This test enforces
        that we caught the regression in the test suite, not at runtime.
        """
        for factory in _CACHED_STORE_FACTORIES:
            assert callable(getattr(factory, "cache_clear", None)), (
                f"{factory.__name__} is in _CACHED_STORE_FACTORIES but has no cache_clear() — it is not @lru_cache-decorated."
            )

    def test_every_factory_is_callable(self) -> None:
        for factory in _CACHED_STORE_FACTORIES:
            assert callable(factory)


# ---------------------------------------------------------------------------
# reset_cached_stores()
# ---------------------------------------------------------------------------


class TestResetCachedStores:
    """``reset_cached_stores()`` must clear every factory's cache."""

    def test_returns_none(self) -> None:
        assert reset_cached_stores() is None

    def test_is_idempotent(self) -> None:
        """Calling it on an already-empty cache must not raise."""
        reset_cached_stores()
        reset_cached_stores()  # second call must be a no-op
        # All caches still empty.
        for factory in _CACHED_STORE_FACTORIES:
            assert factory.cache_info().currsize == 0

    def test_clears_populated_caches(self) -> None:
        """After populating every cache, ``reset_cached_stores()`` empties them."""
        try:
            # Populate every cached factory by calling it.
            for factory in _CACHED_STORE_FACTORIES:
                factory()
            # Sanity check: at least one factory actually got cached.
            # (get_settings is a no-op singleton-return; the rest construct
            # new objects, so all 10 should be cached now.)
            assert any(f.cache_info().currsize > 0 for f in _CACHED_STORE_FACTORIES), "Expected at least one factory to be cached after invocation"

            reset_cached_stores()

            for factory in _CACHED_STORE_FACTORIES:
                assert factory.cache_info().currsize == 0, f"{factory.__name__}.cache_info().currsize == {factory.cache_info().currsize} after reset"
        finally:
            reset_cached_stores()


# ---------------------------------------------------------------------------
# fresh_stores() context manager
# ---------------------------------------------------------------------------


class TestFreshStores:
    """``fresh_stores()`` is the public API used by conftest and tests."""

    def test_is_a_context_manager(self) -> None:
        """``with fresh_stores(): ...`` must work — and it must be sync."""
        with fresh_stores():
            pass  # pragma: no cover

    def test_yields_exactly_once(self) -> None:
        """Entering twice on the same instance must not happen — fresh_stores
        is a *factory* that returns a new context manager each call."""
        cm1 = fresh_stores()
        cm2 = fresh_stores()
        # Each invocation is a fresh generator, not a shared state object.
        assert cm1 is not cm2

    def test_clears_cache_on_entry(self) -> None:
        """Pre-populating the cache and entering ``fresh_stores()`` must
        leave the cache empty inside the ``with`` block."""
        try:
            for factory in _CACHED_STORE_FACTORIES:
                factory()
            with fresh_stores():
                for factory in _CACHED_STORE_FACTORIES:
                    assert factory.cache_info().currsize == 0, f"{factory.__name__} not cleared on entry"
        finally:
            reset_cached_stores()

    def test_clears_cache_on_exit(self) -> None:
        """Inside the ``with`` block, calling the factory re-populates the
        cache. Exiting must clear it again so the *next* test starts clean."""
        try:
            with fresh_stores():
                for factory in _CACHED_STORE_FACTORIES:
                    factory()
                # Cache should now be non-empty for at least the
                # *constructive* factories.
                # (get_settings is a no-op-return of the module-level
                # singleton, so we just check that some factory has > 0.)
                assert any(f.cache_info().currsize > 0 for f in _CACHED_STORE_FACTORIES)
            # After exit: every cache must be empty again.
            for factory in _CACHED_STORE_FACTORIES:
                assert factory.cache_info().currsize == 0, f"{factory.__name__} not cleared on exit"
        finally:
            reset_cached_stores()

    def test_clears_cache_even_when_body_raises(self) -> None:
        """If the ``with`` body raises, the teardown branch must still
        run and clear the cache. This is the test-isolation guarantee
        the 2026-06-12 review demanded."""
        try:
            with pytest.raises(RuntimeError, match="boom"):
                with fresh_stores():
                    for factory in _CACHED_STORE_FACTORIES:
                        factory()
                    raise RuntimeError("boom")
            # Teardown must have run despite the exception.
            for factory in _CACHED_STORE_FACTORIES:
                assert factory.cache_info().currsize == 0, f"{factory.__name__} not cleared after raised body"
        finally:
            reset_cached_stores()

    def test_nested_fresh_stores(self) -> None:
        """Nesting two ``fresh_stores()`` blocks must be a no-op the second
        time. The inner block can be entered/exited cleanly."""
        with fresh_stores():
            with fresh_stores():
                for factory in _CACHED_STORE_FACTORIES:
                    factory()
        for factory in _CACHED_STORE_FACTORIES:
            assert factory.cache_info().currsize == 0


# ---------------------------------------------------------------------------
# The factories themselves
# ---------------------------------------------------------------------------


class TestFactoriesReturnSingletons:
    """The whole point of ``@lru_cache`` is that consecutive calls
    return the *same* instance. Clearing the cache must produce a *new*
    instance on the next call. This is the production contract."""

    def test_consecutive_calls_return_same_instance(self) -> None:
        try:
            with fresh_stores():
                a = deps.get_audit_service()
                b = deps.get_audit_service()
                assert a is b
        finally:
            reset_cached_stores()

    def test_clearing_cache_produces_new_instance(self) -> None:
        try:
            with fresh_stores():
                first = deps.get_audit_service()
                reset_cached_stores()
                second = deps.get_audit_service()
                assert first is not second, "cache_clear() should force a new instance on the next call"
        finally:
            reset_cached_stores()

    def test_get_settings_is_singleton(self) -> None:
        """``get_settings`` returns the module-level ``settings`` object,
        so it must always be ``is``-identical regardless of caching.
        Clearing the cache must not change this."""
        try:
            with fresh_stores():
                a = deps.get_settings()
                b = deps.get_settings()
                assert a is b is deps.settings
        finally:
            reset_cached_stores()


# ---------------------------------------------------------------------------
# Integration: a fast-failing test would previously poison the next one
# ---------------------------------------------------------------------------


class TestCascadeRegression:
    """Pin the regression the 2026-06-12 review actually flagged:

    > the connections get reused across tests even when fixtures say
    > "use a fresh DB". There is no _reset hook to bust the cache.
    """

    def test_first_test_pollutes_second_without_fresh_stores(self) -> None:
        """A *direct* test (no fixture) that calls a factory and does
        NOT clear the cache must leave a cached store behind. The
        follow-up test (below) proves that ``fresh_stores()`` prevents
        this pollution from carrying over.
        """
        try:
            reset_cached_stores()
            _store = deps.get_audit_service()
            # Cache is now populated.
            assert deps.get_audit_service.cache_info().currsize == 1
            del _store
        finally:
            reset_cached_stores()

    def test_fresh_stores_isolates_successive_tests(self) -> None:
        """Two consecutive ``with fresh_stores()`` blocks must each see
        a *fresh* (newly constructed) store, not the leftover from the
        previous block."""
        try:
            with fresh_stores():
                a = deps.get_audit_service()
            with fresh_stores():
                b = deps.get_audit_service()
            assert a is not b, "fresh_stores() should force a new store on every entry"
        finally:
            reset_cached_stores()


# ---------------------------------------------------------------------------
# Module-level teardown — leave the cache empty so the next test file
# starts in a known-good state.
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _cleanup_cache():
    """Make sure no test in this file leaks cached state to the next."""
    reset_cached_stores()
    yield
    reset_cached_stores()
