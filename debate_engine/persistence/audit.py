"""Append-only SQLite audit trail. No UPDATE, no DELETE."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from debate_engine.core.config import settings
from debate_engine.models.schemas import AuditEvent


class AuditService:
    """Immutable audit event store backed by SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id          TEXT PRIMARY KEY,
                    debate_id   TEXT NOT NULL,
                    round       INTEGER NOT NULL,
                    agent       TEXT NOT NULL,
                    action      TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    input_hash  TEXT NOT NULL DEFAULT '',
                    output_hash TEXT NOT NULL DEFAULT '',
                    llm_model   TEXT NOT NULL DEFAULT 'dummy',
                    tokens_used INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_debate
                ON audit_events (debate_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    # ------------------------------------------------------------------
    # Write (append-only)
    # ------------------------------------------------------------------

    def record(self, event: AuditEvent) -> None:
        """Insert a single audit event. Idempotent on (id)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO audit_events
                    (id, debate_id, round, agent, action, timestamp,
                     input_hash, output_hash, llm_model, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.debate_id,
                    event.round,
                    event.agent.value,
                    event.action,
                    event.timestamp.isoformat(),
                    event.input_hash,
                    event.output_hash,
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

    def count_events(self, debate_id: str) -> int:
        """Count events for a debate."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM audit_events WHERE debate_id = ?",
                (debate_id,),
            ).fetchone()
        return row[0] if row else 0
