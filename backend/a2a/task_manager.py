"""A2A Task State Management — SQLite-backed persistent store.

Tracks the lifecycle of A2A tasks (submitted → working → completed/failed/canceled).
Follows the same sqlite3 pattern as ``backend.persistence.audit.AuditService``.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from backend.core.config import settings

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """A2A task lifecycle states."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskManager:
    """Persistent A2A task store backed by SQLite.

    Thread-safe for concurrent access from async debate coroutines.
    Tasks survive server restarts.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialise TaskManager."""
        self._db_path = db_path or (settings.db_path.parent / "a2a_tasks.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the a2a_tasks table if it does not exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS a2a_tasks (
                    id          TEXT PRIMARY KEY,
                    status      TEXT NOT NULL DEFAULT 'submitted',
                    created_at  TEXT NOT NULL,
                    updated_at  TEXT NOT NULL,
                    debate_id   TEXT,
                    result      TEXT,
                    error       TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_a2a_tasks_status
                ON a2a_tasks (status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_a2a_tasks_debate
                ON a2a_tasks (debate_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        """Return a new SQLite connection."""
        return sqlite3.connect(str(self._db_path))

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def create_task(
        self,
        task_id: str,
        status: TaskStatus = TaskStatus.SUBMITTED,
    ) -> dict:
        """Create a new A2A task record.

        Returns the created task as a dict.
        """
        now = datetime.now(UTC).isoformat()
        task = {
            "id": task_id,
            "status": status,
            "created_at": now,
            "updated_at": now,
            "debate_id": None,
            "result": None,
            "error": None,
        }
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO a2a_tasks
                        (id, status, created_at, updated_at, debate_id, result, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        status.value,
                        now,
                        now,
                        None,
                        None,
                        None,
                    ),
                )
        logger.info("A2A task created: %s (status=%s)", task_id, status.value)
        return task

    def update_task(self, task_id: str, **kwargs) -> dict | None:
        """Update fields of an existing A2A task.

        Supported keyword arguments: status, debate_id, result, error.
        Always bumps ``updated_at`` to the current time.

        Returns the updated task dict, or ``None`` if the task was not found.
        """
        now = datetime.now(UTC).isoformat()

        # Build SET clauses dynamically from provided kwargs
        allowed = {"status", "debate_id", "result", "error"}
        updates: list[str] = []
        values: list = []
        for key, value in kwargs.items():
            if key not in allowed:
                continue
            if key == "status" and isinstance(value, TaskStatus):
                value = value.value
            updates.append(f"{key} = ?")
            values.append(value)

        if not updates:
            # Nothing to update besides updated_at
            updates = []
        updates.append("updated_at = ?")
        values.append(now)
        values.append(task_id)

        set_clause = ", ".join(updates)

        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    f"UPDATE a2a_tasks SET {set_clause} WHERE id = ?",
                    values,
                )
                if cursor.rowcount == 0:
                    return None

        return self.get_task(task_id)

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_task(self, task_id: str) -> dict | None:
        """Return a single task by ID, or ``None`` if not found."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM a2a_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_tasks(self, status: TaskStatus | None = None) -> list[dict]:
        """Return all tasks, optionally filtered by status."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            if status:
                rows = conn.execute(
                    "SELECT * FROM a2a_tasks WHERE status = ? ORDER BY created_at DESC",
                    (status.value,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM a2a_tasks ORDER BY created_at DESC",
                ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """Remove tasks older than *max_age_hours*.

        Returns the number of deleted tasks.
        """
        datetime.now(UTC).isoformat()
        # Calculate cutoff timestamp
        from datetime import timedelta

        cutoff_dt = datetime.now(UTC) - timedelta(hours=max_age_hours)
        cutoff_str = cutoff_dt.isoformat()

        with self._lock:
            with self._connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM a2a_tasks WHERE created_at < ?",
                    (cutoff_str,),
                )
                deleted = cursor.rowcount

        if deleted:
            logger.info("Cleaned up %d old A2A tasks (older than %dh)", deleted, max_age_hours)
        return deleted

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a SQLite Row to a dict with proper types."""
        data = dict(row)
        # Deserialize status enum
        status_str = data.get("status", "submitted")
        try:
            data["status"] = TaskStatus(status_str)
        except ValueError:
            data["status"] = TaskStatus.SUBMITTED
        return data
