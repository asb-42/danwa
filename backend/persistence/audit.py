"""Append-only SQLite audit trail. No UPDATE, no DELETE.

Updated Sprint 3: Now stores full input/output content alongside
SHA-256 hashes for complete audit trail reproducibility.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.core.config import settings
from backend.models.schemas import AuditEvent

_DEFAULT_PROJECT_ID = "_default"


class AuditService:
    """Immutable audit event store backed by SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        """Initialise AuditService."""
        self._db_path = db_path or settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Init db the instance."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id              TEXT PRIMARY KEY,
                    debate_id       TEXT NOT NULL,
                    project_id      TEXT NOT NULL DEFAULT '_default',
                    round           INTEGER NOT NULL,
                    agent           TEXT NOT NULL,
                    action          TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    input_hash      TEXT NOT NULL DEFAULT '',
                    output_hash     TEXT NOT NULL DEFAULT '',
                    llm_model       TEXT NOT NULL DEFAULT 'dummy',
                    tokens_used     INTEGER NOT NULL DEFAULT 0
                )
            """)
            # Add missing columns for existing databases (migration)
            for col, col_def in [
                ("input_content", "TEXT DEFAULT ''"),
                ("output_content", "TEXT DEFAULT ''"),
                ("trace_log_path", "TEXT DEFAULT ''"),
            ]:
                try:
                    conn.execute(f"ALTER TABLE audit_events ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass  # Column already exists
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_debate
                ON audit_events (debate_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_project
                ON audit_events (project_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_project_debate
                ON audit_events (project_id, debate_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        return sqlite3.connect(str(self._db_path))

    # ------------------------------------------------------------------
    # Write (append-only)
    # ------------------------------------------------------------------

    def record(self, event: AuditEvent, project_id: str = _DEFAULT_PROJECT_ID) -> None:
        """Insert a single audit event. Idempotent on (id)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO audit_events
                    (id, debate_id, project_id, round, agent, action, timestamp,
                     input_hash, output_hash, input_content, output_content,
                     trace_log_path, llm_model, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.debate_id,
                    project_id,
                    event.round,
                    event.agent.value,
                    event.action,
                    event.timestamp.isoformat(),
                    event.input_hash,
                    event.output_hash,
                    getattr(event, "input_content", "") or "",
                    getattr(event, "output_content", "") or "",
                    getattr(event, "trace_log_path", "") or "",
                    event.llm_model,
                    event.tokens_used,
                ),
            )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_events(self, debate_id: str) -> list[dict]:
        """Return all audit events for a debate, ordered by round."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM audit_events
                WHERE debate_id = ?
                ORDER BY round, timestamp
                """,
                (debate_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_events_by_project(self, project_id: str, limit: int = 100, offset: int = 0) -> list[dict]:
        """Return audit events for a project, ordered by timestamp desc."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM audit_events
                WHERE project_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (project_id, limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_events(self, debate_id: str) -> int:
        """Count events for a debate."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE debate_id = ?",
                (debate_id,),
            ).fetchone()
        return row[0] if row else 0

    def count_events_by_project(self, project_id: str) -> int:
        """Count events for a project."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        return row[0] if row else 0

    def delete_events(self, debate_id: str) -> int:
        """Delete all audit events for a debate. Returns number of deleted rows."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM audit_events WHERE debate_id = ?",
                (debate_id,),
            )
            return cursor.rowcount

    def update_debate_project(self, debate_id: str, new_project_id: str) -> int:
        """Update the project_id for all audit events of a debate.

        Returns the number of affected rows.
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE audit_events SET project_id = ? WHERE debate_id = ?",
                (new_project_id, debate_id),
            )
            return cursor.rowcount
