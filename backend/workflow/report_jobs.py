"""Report job store — async report generation job tracking.

Manages the ``report_jobs`` table created by migration v6.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class ReportJobStore:
    """SQLite-backed store for async report generation jobs."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise ReportJobStore."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def create_job(
        self,
        session_id: str,
        fmt: str,
    ) -> str:
        """Create a new report job and return its ID.

        Args:
            session_id: The workflow session ID.
            fmt: Output format (``"docx"``, ``"pdf"``, ``"odf"``).

        Returns:
            The newly created job ID.
        """
        job_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO report_jobs
                    (id, session_id, format, status, created_at)
                VALUES (?, ?, ?, 'pending', ?)
                """,
                (job_id, session_id, fmt, now),
            )
        logger.info("Report job %s created for session %s (format=%s)", job_id, session_id, fmt)
        return job_id

    def update_job(
        self,
        job_id: str,
        status: str,
        file_path: str | None = None,
        error: str | None = None,
    ) -> None:
        """Update the status of a report job.

        Args:
            job_id: The job ID.
            status: New status (``"pending"``, ``"running"``, ``"completed"``, ``"failed"``).
            file_path: Path to the generated report file (for completed jobs).
            error: Error message (for failed jobs).
        """
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE report_jobs
                SET status = ?, file_path = ?, error = ?, completed_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    file_path,
                    error,
                    now if status in ("completed", "failed") else None,
                    job_id,
                ),
            )
        logger.info("Report job %s → %s", job_id, status)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Return the job record for *job_id*, or ``None`` if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM report_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_jobs(
        self,
        session_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List report jobs, optionally filtered by session."""
        with self._connect() as conn:
            if session_id:
                rows = conn.execute(
                    """
                    SELECT * FROM report_jobs
                    WHERE session_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (session_id, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM report_jobs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()
        return [dict(r) for r in rows]
