"""InputStore — SQLite-backed storage for DebateInput objects.

Maps to the ``debate_inputs`` table created in migration v12.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.models.debate_input import DebateInput

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class InputStore:
    """SQLite-backed storage for ``DebateInput`` objects."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise InputStore."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        from backend.blueprints.migrations import run_migrations

        run_migrations(self._db_path)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, debate_input: DebateInput) -> None:
        """Insert or replace a ``DebateInput``."""
        now = datetime.now(UTC).isoformat()
        data = debate_input.model_dump_json()
        session_id = debate_input.session_id or f"pending-{debate_input.input_hash[:12]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO debate_inputs
                    (session_id, data, created_at)
                VALUES (?, ?, ?)
                """,
                (session_id, data, now),
            )
        logger.info("DebateInput saved for session %s", session_id)

    def get(self, session_id: str) -> DebateInput | None:
        """Load a ``DebateInput`` by session ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM debate_inputs WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return DebateInput.model_validate_json(row["data"])

    def delete(self, session_id: str) -> None:
        """Delete a ``DebateInput`` by session ID."""
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM debate_inputs WHERE session_id = ?",
                (session_id,),
            )
        logger.info("DebateInput deleted for session %s", session_id)

    def exists(self, session_id: str) -> bool:
        """Return ``True`` if an input exists for *session_id*."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM debate_inputs WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row is not None
