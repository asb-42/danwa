"""ArtifactStore — SQLite-backed storage for DebateArtifact objects.

Persists debate artifacts at workflow completion and loads them for
rendering by the Output Composer.  Follows the same connection pattern
as :class:`backend.blueprints.repository.BlueprintRepository`.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from backend.models.artifact import DebateArtifact

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class ArtifactStore:
    """SQLite-backed storage for ``DebateArtifact`` objects.

    Maps to the ``debate_artifacts`` table created in migration v11.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise ArtifactStore."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, artifact: DebateArtifact) -> None:
        """Insert or replace a ``DebateArtifact``.

        Args:
            artifact: The artifact to persist.
        """
        now = datetime.now(UTC).isoformat()
        data = artifact.model_dump_json()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO debate_artifacts
                    (session_id, workflow_id, data, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (artifact.session_id, artifact.workflow_id, data, now),
            )
        logger.info(
            "DebateArtifact saved for session %s (workflow=%s)",
            artifact.session_id,
            artifact.workflow_id,
        )

    def get(self, session_id: str) -> DebateArtifact | None:
        """Load a ``DebateArtifact`` by session ID.

        Args:
            session_id: The workflow session ID.

        Returns:
            The artifact, or ``None`` if not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data FROM debate_artifacts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return DebateArtifact.model_validate_json(row["data"])

    def delete(self, session_id: str) -> None:
        """Delete a ``DebateArtifact`` by session ID.

        Args:
            session_id: The workflow session ID.
        """
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM debate_artifacts WHERE session_id = ?",
                (session_id,),
            )
        logger.info("DebateArtifact deleted for session %s", session_id)

    def exists(self, session_id: str) -> bool:
        """Return ``True`` if an artifact exists for *session_id*."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM debate_artifacts WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row is not None
