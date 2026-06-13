"""MembershipStore — SQLite-backed tenant membership persistence.

Stores user-to-tenant assignments with roles in the shared ``data/auth.db``.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from backend.models.membership import TenantMembership

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/auth.db")

# Module-level invalidation observer registry.
#
# Resolves the N+1-lookup problem flagged in the 2026-06-12 code review
# (section 3.3). The dependency layer in ``backend.api.deps`` caches the
# per-user membership list for a short TTL, but the cache must be
# invalidated when a membership is *added*, *removed*, or *role-changed*
# so that the next request sees the new state immediately rather than
# after the TTL expires.
#
# Rather than have the store reach up and import the deps module (which
# would create a circular import), the store accepts zero or more
# ``Callable[[str], None]`` observers that are invoked on every
# mutating call.  The deps module registers its observer at import time
# via ``MembershipStore.add_invalidator()``.
#
# Observers must be idempotent and cheap — they will be called on every
# membership write.  Bad observers (exceptions, blocking I/O) are logged
# and swallowed so they cannot poison the store.
_MEMBERSHIP_INVALIDATORS: list[Callable[[str], None]] = []


class MembershipStore:
    """CRUD operations for tenant memberships in the auth SQLite database."""

    # ------------------------------------------------------------------
    # Invalidation observers (section 3.3 of the 2026-06-12 code review)
    # ------------------------------------------------------------------

    @classmethod
    def add_invalidator(cls, fn: Callable[[str], None]) -> Callable[[], None]:
        """Register an observer to be called on every mutating operation.

        The observer is invoked with the affected ``user_id`` as its
        single argument. Observers must be idempotent and cheap;
        exceptions are logged and swallowed.

        Returns a callable that removes the observer.  This is mainly
        useful in tests, where observer leakage between test files would
        cause cross-test pollution.
        """
        _MEMBERSHIP_INVALIDATORS.append(fn)

        def _unregister() -> None:
            try:
                _MEMBERSHIP_INVALIDATORS.remove(fn)
            except ValueError:  # pragma: no cover - already gone
                pass

        return _unregister

    @classmethod
    def _fire_invalidators(cls, user_id: str) -> None:
        """Notify all registered observers that *user_id* changed."""
        for fn in list(_MEMBERSHIP_INVALIDATORS):
            try:
                fn(user_id)
            except Exception as exc:  # noqa: BLE001
                # Bad observer: log it but do NOT let it poison the
                # store. A failing cache invalidation is a
                # *correctness* problem (stale read for up to TTL), not
                # a *crash* problem.
                logger.warning(
                    "MembershipStore invalidator %r raised %s: %s",
                    fn,
                    type(exc).__name__,
                    exc,
                )

    def __init__(self, db_path: Path | str | None = None):
        """Initialise MembershipStore."""
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        """Init db the instance."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memberships (
                tenant_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'member',
                invited_by TEXT,
                joined_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, user_id)
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)")
        self.conn.commit()

    def add(self, tenant_id: str, user_id: str, role: str = "member", invited_by: str | None = None) -> TenantMembership:
        """Add a user to a tenant with the given role."""
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """INSERT OR REPLACE INTO memberships (tenant_id, user_id, role, invited_by, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (tenant_id, user_id, role, invited_by, now),
        )
        self.conn.commit()
        logger.info("Added membership: user=%s tenant=%s role=%s", user_id, tenant_id, role)
        # Fire-and-forget: notify observers that this user's membership
        # set has changed.  ``add`` uses INSERT OR REPLACE so a re-add
        # is also a mutation that observers must see.
        self._fire_invalidators(user_id)
        return TenantMembership(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            invited_by=invited_by,
            joined_at=datetime.fromisoformat(now),
        )

    def remove(self, tenant_id: str, user_id: str) -> bool:
        """Remove a user from a tenant. Returns True if a row was deleted."""
        cursor = self.conn.execute(
            "DELETE FROM memberships WHERE tenant_id = ? AND user_id = ?",
            (tenant_id, user_id),
        )
        self.conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Removed membership: user=%s tenant=%s", user_id, tenant_id)
            # Fire invalidator only on a real delete so that no-op
            # ``remove`` calls do not thrash the cache.
            self._fire_invalidators(user_id)
        return deleted

    def get(self, tenant_id: str, user_id: str) -> TenantMembership | None:
        """Get a specific membership. Returns None if not found."""
        cursor = self.conn.execute(
            "SELECT * FROM memberships WHERE tenant_id = ? AND user_id = ?",
            (tenant_id, user_id),
        )
        row = cursor.fetchone()
        return self._row_to_membership(row) if row else None

    def list_by_user(self, user_id: str) -> list[TenantMembership]:
        """List all memberships for a user."""
        cursor = self.conn.execute(
            "SELECT * FROM memberships WHERE user_id = ? ORDER BY joined_at",
            (user_id,),
        )
        return [self._row_to_membership(row) for row in cursor.fetchall()]

    def list_by_tenant(self, tenant_id: str) -> list[TenantMembership]:
        """List all members of a tenant."""
        cursor = self.conn.execute(
            "SELECT * FROM memberships WHERE tenant_id = ? ORDER BY joined_at",
            (tenant_id,),
        )
        return [self._row_to_membership(row) for row in cursor.fetchall()]

    def update_role(self, tenant_id: str, user_id: str, role: str) -> TenantMembership | None:
        """Update a user's role within a tenant."""
        cursor = self.conn.execute(
            "UPDATE memberships SET role = ? WHERE tenant_id = ? AND user_id = ?",
            (role, tenant_id, user_id),
        )
        self.conn.commit()
        if cursor.rowcount > 0:
            # Role changes affect ``is_admin`` etc. in downstream code,
            # so notify observers even though the membership *set* has
            # not changed.
            self._fire_invalidators(user_id)
        return self.get(tenant_id, user_id)

    def count_by_tenant(self, tenant_id: str) -> int:
        """Count members in a tenant."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM memberships WHERE tenant_id = ?",
            (tenant_id,),
        )
        return cursor.fetchone()[0]

    def _row_to_membership(self, row: sqlite3.Row) -> TenantMembership:
        """Row to membership the instance."""
        d = dict(row)
        return TenantMembership(
            tenant_id=d["tenant_id"],
            user_id=d["user_id"],
            role=d["role"],
            invited_by=d.get("invited_by"),
            joined_at=datetime.fromisoformat(d["joined_at"]),
        )
