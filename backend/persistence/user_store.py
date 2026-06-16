"""UserStore — SQLite-backed user persistence for authentication."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from backend.models.user import User

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/auth.db")


class UserStore:
    """CRUD operations for users in a dedicated auth SQLite database."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialise UserStore."""
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        """Init db the instance."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'viewer',
                tenant_id TEXT NOT NULL DEFAULT '_default',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT,
                last_workspace TEXT
            )
        """)
        # Idempotent migration for pre-existing DBs that don't have the column yet
        try:
            self.conn.execute("ALTER TABLE users ADD COLUMN last_workspace TEXT")
        except Exception:  # noqa: BLE001
            pass
        # Per-tenant last-workspace mapping.  See the comment block on
        # ``get_last_workspace`` below for the cross-tenant-leak rationale.
        # The table is created in a separate try/except so older DBs
        # without it still boot (the accessors fall back to the legacy
        # ``users.last_workspace`` column when the table is missing).
        try:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS user_last_workspace (
                    user_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    case_id TEXT,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, tenant_id)
                )
            """)
        except Exception:  # noqa: BLE001
            pass
        # 2026-06-16 Bug A: NO backfill from the legacy single-value
        # column.  Pre-migration rows in ``users.last_workspace`` were
        # stored without a tenant_id, so we have no idea which tenant
        # they belong to.  Conservatively using the user's primary
        # ``tenant_id`` silently leaks case ids into the wrong tenant.
        #
        # The safe behaviour is: leave the legacy column read-only
        # (the back-compat read path in get_last_workspace still
        # honours it when called without a tenant_id), and require
        # the user to explicitly save their workspace per tenant
        # via ``PUT /api/v1/auth/me/last-workspace`` with the
        # X-Tenant-Id header.  Until then, no per-tenant row exists
        # and the Workspace shows the case-picker (safe default).
        #
        # The legacy column can be cleared in a one-time data
        # migration once we are confident no production user still
        # relies on the back-compat read path; see plans/2026-06-16
        # _last-workspace-cross-tenant-bug.md.
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id)")
        self.conn.commit()

    def create(
        self,
        email: str,
        display_name: str,
        password_hash: str,
        role: str = "viewer",
        tenant_id: str = "_default",
    ) -> User:
        """Create a new user. Raises sqlite3.IntegrityError if email exists."""
        user_id = str(uuid.uuid4())
        now = datetime.now().isoformat()
        self.conn.execute(
            """INSERT INTO users (id, email, display_name, password_hash, role, tenant_id, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
            (user_id, email, display_name, password_hash, role, tenant_id, now, now),
        )
        self.conn.commit()
        return self.get(user_id)  # type: ignore[return-value]

    def get(self, user_id: str) -> User | None:
        """Retrieve a user by ID. Returns None if not found."""
        cursor = self.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def get_by_email(self, email: str) -> User | None:
        """Retrieve a user by email address. Returns None if not found."""
        cursor = self.conn.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return self._row_to_user(row) if row else None

    def list_by_tenant(self, tenant_id: str) -> list[User]:
        """List all users belonging to a specific tenant, ordered by creation date."""
        cursor = self.conn.execute("SELECT * FROM users WHERE tenant_id = ? ORDER BY created_at", (tenant_id,))
        return [self._row_to_user(row) for row in cursor.fetchall()]

    def list_all(self) -> list[User]:
        """List all users across all tenants, ordered by creation date."""
        cursor = self.conn.execute("SELECT * FROM users ORDER BY created_at")
        return [self._row_to_user(row) for row in cursor.fetchall()]

    def count(self) -> int:
        """Total number of users."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM users")
        return cursor.fetchone()[0]

    def update(self, user_id: str, **kwargs) -> User | None:
        """Update specific fields on a user."""
        allowed = {"display_name", "role", "is_active", "tenant_id", "password_hash", "last_login_at"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        if not updates:
            return self.get(user_id)
        updates["updated_at"] = datetime.now().isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [user_id]
        self.conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return self.get(user_id)

    def update_last_login(self, user_id: str) -> None:
        """Set last_login_at to now for the given user."""
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user_id),
        )
        self.conn.commit()

    def has_admin(self) -> bool:
        """Check whether at least one active admin user exists."""
        cursor = self.conn.execute("SELECT 1 FROM users WHERE role = 'admin' AND is_active = 1 LIMIT 1")
        return cursor.fetchone() is not None

    def delete(self, user_id: str) -> bool:
        """Delete a user by ID. Returns True."""
        self.conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.conn.commit()
        return True

    def _row_to_user(self, row: sqlite3.Row) -> User:
        """Row to user the instance."""
        d = dict(row)
        return User(
            id=d["id"],
            email=d["email"],
            display_name=d["display_name"],
            password_hash=d["password_hash"],
            role=d["role"],
            tenant_id=d["tenant_id"],
            is_active=bool(d["is_active"]),
            created_at=datetime.fromisoformat(d["created_at"]),
            updated_at=datetime.fromisoformat(d["updated_at"]),
            last_login_at=datetime.fromisoformat(d["last_login_at"]) if d.get("last_login_at") else None,
        )

    # ─── Last-workspace setting (Case-Space Phase 1.3) ─────────────
    #
    # Phase 1.3 originally stored a single ``users.last_workspace``
    # string per user.  That design was a cross-tenant leak: when a
    # user switched tenants and re-mounted the Workspace view, the
    # restoreLastWorkspace() flow pulled back a case id from a tenant
    # that was no longer active.  The fix is to make the per-tenant
    # mapping explicit via a dedicated ``user_last_workspace`` table
    # keyed on (user_id, tenant_id).
    #
    # The legacy single-column is still kept on the ``users`` table for
    # backwards compatibility (and as a one-shot backfill source) but
    # is no longer the authoritative read source.

    def get_last_workspace(self, user_id: str, tenant_id: str | None = None) -> str | None:
        """Return the case id the user last opened in ``tenant_id``, or None.

        Args:
            user_id:   The user whose setting to look up.
            tenant_id: The active tenant.  When None, falls back to the
                       legacy single-value column (so older callers that
                       pass only ``user_id`` keep working during the
                       transition).

        Returns:
            The persisted case id, or None when no per-tenant setting
            exists.  Falls back to the legacy column only when no
            tenant-specific row is found AND the call did not specify
            a tenant — never silently mixes tenants.
        """
        # Tenant-aware path: the new ``user_last_workspace`` table.
        if tenant_id is not None:
            try:
                row = self.conn.execute(
                    "SELECT case_id FROM user_last_workspace "
                    "WHERE user_id = ? AND tenant_id = ?",
                    (user_id, tenant_id),
                ).fetchone()
            except Exception:  # noqa: BLE001
                row = None
            if row is not None:
                return row[0]
            return None
        # Legacy fallback: only honoured when the caller did not
        # specify a tenant.  Used by the pre-fix auth router shape.
        try:
            row = self.conn.execute(
                "SELECT last_workspace FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        except Exception:  # noqa: BLE001
            return None
        if row is None:
            return None
        return row[0]

    def set_last_workspace(
        self,
        user_id: str,
        case_id: str | None,
        tenant_id: str | None = None,
    ) -> bool:
        """Persist the case id the user last opened (or clear it).

        When ``tenant_id`` is given, the value is written to the
        per-tenant mapping.  When omitted, the call falls back to the
        legacy single-column update (used by older callers during
        the transition).
        """
        now = datetime.now().isoformat()
        if tenant_id is not None:
            try:
                self.conn.execute(
                    """
                    INSERT INTO user_last_workspace
                        (user_id, tenant_id, case_id, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, tenant_id) DO UPDATE SET
                        case_id = excluded.case_id,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, tenant_id, case_id, now),
                )
                self.conn.commit()
                return True
            except Exception:  # noqa: BLE001
                # Schema not migrated yet or DB lock — fall through
                # to the legacy column write so the user's intent is
                # at least recorded somewhere.
                try:
                    self.conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
        # Legacy single-value path (kept as a safety net).
        try:
            cur = self.conn.execute(
                "UPDATE users SET last_workspace = ?, updated_at = ? WHERE id = ?",
                (case_id, now, user_id),
            )
            self.conn.commit()
            if cur.rowcount > 0:
                return True
            existing = self.conn.execute(
                "SELECT 1 FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            return existing is not None
        except Exception:  # noqa: BLE001
            try:
                self.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            return False
