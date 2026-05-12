"""State snapshot store — SQLite persistence for workflow execution state.

Stores snapshots of WorkflowState after each node execution, enabling
replay, debugging, and resume-after-restart capabilities.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class StateSnapshotStore:
    """SQLite-backed storage for workflow execution state snapshots.

    Uses the same database file as BlueprintRepository.
    """

    def __init__(self, db_path: Path | str = _DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_table(self) -> None:
        """Create the state_snapshots table if it doesn't exist."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    node_type TEXT NOT NULL DEFAULT '',
                    round_number INTEGER NOT NULL DEFAULT 0,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_locked INTEGER NOT NULL DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_snapshots_session
                ON state_snapshots(session_id)
            """)
            # Safe migration: add is_locked column for existing databases
            try:
                conn.execute("ALTER TABLE state_snapshots ADD COLUMN is_locked INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # column already exists
            conn.commit()

    def save(
        self,
        session_id: str,
        workflow_id: str,
        node_id: str,
        node_type: str,
        round_number: int,
        state_dict: dict[str, Any],
    ) -> None:
        """Insert a state snapshot.

        Args:
            session_id: The workflow session ID.
            workflow_id: The workflow definition ID.
            node_id: The node that just executed.
            node_type: The type of the node.
            round_number: Current round number.
            state_dict: Serialized WorkflowState dict.
        """
        state_json = json.dumps(state_dict, default=str)
        now = datetime.now(UTC).isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO state_snapshots
                    (session_id, workflow_id, node_id, node_type, round_number, state_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, workflow_id, node_id, node_type, round_number, state_json, now),
            )
            conn.commit()

        logger.debug(
            "Saved state snapshot for session=%s node=%s round=%d",
            session_id,
            node_id,
            round_number,
        )

    def get_latest(self, session_id: str) -> dict[str, Any] | None:
        """Get the most recent state snapshot for a session.

        Args:
            session_id: The workflow session ID.

        Returns:
            The latest snapshot dict, or None if no snapshots exist.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM state_snapshots
                WHERE session_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id,),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_dict(row)

    def get_history(self, session_id: str) -> list[dict[str, Any]]:
        """Get all state snapshots for a session, ordered by creation.

        Args:
            session_id: The workflow session ID.

        Returns:
            List of snapshot dicts in chronological order.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM state_snapshots
                WHERE session_id = ?
                ORDER BY id ASC
                """,
                (session_id,),
            ).fetchall()

        return [self._row_to_dict(row) for row in rows]

    def get_by_node(self, session_id: str, node_id: str) -> dict[str, Any] | None:
        """Get the state snapshot for a specific node in a session.

        Args:
            session_id: The workflow session ID.
            node_id: The node ID to look up.

        Returns:
            The snapshot dict for the node, or None.
        """
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM state_snapshots
                WHERE session_id = ? AND node_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (session_id, node_id),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a SQLite Row to a dict, parsing the state_json."""
        d = dict(row)
        state_json = d.get("state_json", "{}")
        try:
            d["state"] = json.loads(state_json)
        except (json.JSONDecodeError, TypeError):
            d["state"] = {}
        d.pop("state_json", None)
        return d
