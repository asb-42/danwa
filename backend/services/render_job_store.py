"""RenderJobStore — SQLite-backed store for render job lifecycle tracking.

Maps to the ``render_jobs`` table created in migration v11.
Follows the same connection pattern as
:class:`backend.workflow.report_jobs.ReportJobStore`.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.models.render_job import RenderJob, RenderJobStatus

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class RenderJobStore:
    """SQLite-backed store for ``RenderJob`` objects."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise RenderJobStore."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None

    def _get_conn(self) -> sqlite3.Connection:
        """Return the cached connection, opening + WAL-initialising on first use.

        Follows the same pattern as AuditLogger._get_conn() — a single
        connection is reused across operations to avoid repeated
        connect/open cycles (N-03 fix).
        """
        if self._conn is None:
            with self._lock:
                if self._conn is None:
                    conn = sqlite3.connect(
                        str(self._db_path),
                        check_same_thread=False,
                        timeout=30.0,
                    )
                    conn.row_factory = sqlite3.Row
                    try:
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.execute("PRAGMA synchronous=NORMAL")
                    except sqlite3.DatabaseError:
                        logger.debug("WAL mode not available for %s", self._db_path, exc_info=True)
                    self._conn = conn
        return self._conn

    def close(self) -> None:
        """Close the cached connection.  Safe to call multiple times."""
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    logger.debug("Error closing RenderJobStore connection", exc_info=True)
                self._conn = None

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance — returns the cached connection."""
        return self._get_conn()

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> RenderJob:
        """Convert a SQLite row to a ``RenderJob`` model."""
        return RenderJob(
            id=row["id"],
            session_id=row["session_id"],
            status=RenderJobStatus(row["status"]),
            plugin_key=row["plugin_key"],
            config=json.loads(row["config"] or "{}"),
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=(datetime.fromisoformat(row["started_at"]) if row["started_at"] else None),
            completed_at=(datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None),
            error_message=row["error_message"],
            output_files=json.loads(row["output_files"] or "[]"),
            artifact_snapshot_hash=row["artifact_snapshot_hash"] or "",
            progress_current=row["progress_current"] or 0,
            progress_total=row["progress_total"] or 0,
        )

    def create_job(self, job: RenderJob) -> None:
        """Insert a new render job.

        Args:
            job: The render job to persist.
        """
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO render_jobs
                    (id, session_id, plugin_key, config, status,
                     output_files, error_message, artifact_snapshot_hash,
                     created_at, started_at, completed_at,
                     progress_current, progress_total)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.session_id,
                    job.plugin_key,
                    json.dumps(job.config),
                    job.status.value,
                    json.dumps(job.output_files),
                    job.error_message,
                    job.artifact_snapshot_hash,
                    job.created_at.isoformat(),
                    job.started_at.isoformat() if job.started_at else None,
                    job.completed_at.isoformat() if job.completed_at else None,
                    job.progress_current,
                    job.progress_total,
                ),
            )
        logger.info("RenderJob %s created for session %s", job.id, job.session_id)

    def get_job(self, job_id: str) -> RenderJob | None:
        """Return the render job for *job_id*, or ``None`` if not found.

        Args:
            job_id: The render job ID.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM render_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def update_job(
        self,
        job_id: str,
        *,
        status: RenderJobStatus | None = None,
        output_files: list[str] | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        progress_current: int | None = None,
        progress_total: int | None = None,
    ) -> None:
        """Update fields on a render job.

        Only non-``None`` keyword arguments are written.

        Args:
            job_id: The render job ID.
            status: New status value.
            output_files: List of output file paths.
            error_message: Error message (for failed jobs).
            started_at: When execution started.
            completed_at: When execution completed.
            progress_current: Number of items processed so far.
            progress_total: Total number of items to process.
        """
        updates: list[str] = []
        params: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if output_files is not None:
            updates.append("output_files = ?")
            params.append(json.dumps(output_files))
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if started_at is not None:
            updates.append("started_at = ?")
            params.append(started_at.isoformat())
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at.isoformat())
        if progress_current is not None:
            updates.append("progress_current = ?")
            params.append(progress_current)
        if progress_total is not None:
            updates.append("progress_total = ?")
            params.append(progress_total)

        if not updates:
            return

        params.append(job_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE render_jobs SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        logger.info("RenderJob %s updated: %s", job_id, ", ".join(updates))

    def list_jobs(
        self,
        session_id: str | None = None,
        status: RenderJobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RenderJob]:
        """List render jobs with optional filters.

        Args:
            session_id: Filter by session.
            status: Filter by status.
            limit: Maximum results.
            offset: Pagination offset.
        """
        conditions: list[str] = []
        params: list[Any] = []

        if session_id is not None:
            conditions.append("session_id = ?")
            params.append(session_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM render_jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def delete_job(self, job_id: str) -> None:
        """Delete a render job.

        Args:
            job_id: The render job ID.
        """
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM render_jobs WHERE id = ?",
                (job_id,),
            )
        logger.info("RenderJob %s deleted", job_id)
