"""TenantStore — SQLite-backed tenant persistence."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.models.tenant import Tenant

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/auth.db")


class TenantStore:
    """CRUD operations for tenants in the auth SQLite database."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialise TenantStore."""
        self.db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=10)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        """Init db the instance."""
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tenants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                max_projects INTEGER DEFAULT 5,
                max_concurrent_debates INTEGER DEFAULT 2,
                max_documents INTEGER DEFAULT 50,
                max_storage_mb INTEGER DEFAULT 500,
                settings_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1
            )
        """)
        self.conn.commit()

    def create(self, name: str, plan: str = "free", tenant_id: str | None = None) -> Tenant:
        """Create a new tenant."""
        import uuid

        tid = tenant_id or str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        self.conn.execute(
            """INSERT INTO tenants (id, name, plan, max_projects, max_concurrent_debates,
            max_documents, max_storage_mb, settings_json, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (tid, name, plan, 5, 2, 50, 500, "{}", now),
        )
        self.conn.commit()
        return self.get(tid)  # type: ignore[return-value]

    def get(self, tenant_id: str) -> Tenant | None:
        """Retrieve a tenant by ID. Returns None if not found."""
        cursor = self.conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,))
        row = cursor.fetchone()
        return self._row_to_tenant(row) if row else None

    def list_all(self) -> list[Tenant]:
        """List all tenants, ordered by creation date."""
        cursor = self.conn.execute("SELECT * FROM tenants ORDER BY created_at")
        return [self._row_to_tenant(row) for row in cursor.fetchall()]

    def update(self, tenant_id: str, **kwargs) -> Tenant | None:
        """Update specific fields on a tenant."""
        allowed = {
            "name",
            "plan",
            "max_projects",
            "max_concurrent_debates",
            "max_documents",
            "max_storage_mb",
            "settings",
            "is_active",
        }
        updates = {}
        for k, v in kwargs.items():
            if k in allowed and v is not None:
                if k == "settings":
                    updates["settings_json"] = json.dumps(v)
                else:
                    updates[k] = v
        if not updates:
            return self.get(tenant_id)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [tenant_id]
        self.conn.execute(f"UPDATE tenants SET {set_clause} WHERE id = ?", values)
        self.conn.commit()
        return self.get(tenant_id)

    def delete(self, tenant_id: str) -> bool:
        """Delete a tenant by ID. Returns True."""
        self.conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_id,))
        self.conn.commit()
        return True

    def count(self) -> int:
        """Total number of tenants."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM tenants")
        return cursor.fetchone()[0]

    def _row_to_tenant(self, row: sqlite3.Row) -> Tenant:
        """Row to tenant the instance."""
        d = dict(row)
        return Tenant(
            id=d["id"],
            name=d["name"],
            plan=d["plan"],
            max_projects=d["max_projects"],
            max_concurrent_debates=d["max_concurrent_debates"],
            max_documents=d["max_documents"],
            max_storage_mb=d["max_storage_mb"],
            settings=json.loads(d.get("settings_json") or "{}"),
            created_at=datetime.fromisoformat(d["created_at"]),
            is_active=bool(d["is_active"]),
        )
