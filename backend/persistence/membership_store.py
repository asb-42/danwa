"""MembershipStore — SQLite-backed tenant membership persistence.

Stores user-to-tenant assignments with roles in the shared ``data/auth.db``.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.models.membership import TenantMembership

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/auth.db")


class MembershipStore:
    """CRUD operations for tenant memberships in the auth SQLite database."""

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
        self.conn.execute(
            "UPDATE memberships SET role = ? WHERE tenant_id = ? AND user_id = ?",
            (role, tenant_id, user_id),
        )
        self.conn.commit()
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
