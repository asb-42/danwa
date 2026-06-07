"""InputJobStore — SQLite-backed store for input processing jobs.

Maps to the ``input_jobs`` table created in migration v12.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.models.debate_input import DebateInput
from backend.models.input_job import InputJob, InputJobStatus

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class InputJobStore:
    """SQLite-backed store for ``InputJob`` objects."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise InputJobStore."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        # Ensure migrations are applied (following BlueprintRepository pattern)
        from backend.blueprints.migrations import run_migrations

        run_migrations(self._db_path)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> InputJob:
        """Row to job the instance."""
        processed = None
        if row["processed_input"]:
            processed = DebateInput.model_validate_json(row["processed_input"])
        return InputJob(
            id=row["id"],
            status=InputJobStatus(row["status"]),
            plugin_key=row["plugin_key"],
            config=json.loads(row["config"] or "{}"),
            raw_input_data=json.loads(row["raw_input_data"] or "{}"),
            processed_input=processed,
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=(datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None),
        )

    def create_job(self, job: InputJob) -> None:
        """Insert a new input job."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO input_jobs
                    (id, plugin_key, config, raw_input_data, processed_input,
                     status, error_message, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    job.plugin_key,
                    json.dumps(job.config),
                    json.dumps(job.raw_input_data),
                    job.processed_input.model_dump_json() if job.processed_input else None,
                    job.status.value,
                    job.error_message,
                    job.created_at.isoformat(),
                    job.completed_at.isoformat() if job.completed_at else None,
                ),
            )
        logger.info("InputJob %s created (plugin=%s)", job.id, job.plugin_key)

    def get_job(self, job_id: str) -> InputJob | None:
        """Return the job for *job_id*, or ``None`` if not found."""
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM input_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            return None
        return self._row_to_job(row)

    def update_job(
        self,
        job_id: str,
        *,
        status: InputJobStatus | None = None,
        processed_input: DebateInput | None = None,
        error_message: str | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        """Update fields on an input job."""
        updates: list[str] = []
        params: list[Any] = []

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)
        if processed_input is not None:
            updates.append("processed_input = ?")
            params.append(processed_input.model_dump_json())
        if error_message is not None:
            updates.append("error_message = ?")
            params.append(error_message)
        if completed_at is not None:
            updates.append("completed_at = ?")
            params.append(completed_at.isoformat())

        if not updates:
            return

        params.append(job_id)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE input_jobs SET {', '.join(updates)} WHERE id = ?",
                params,
            )
        logger.info("InputJob %s updated", job_id)

    def list_jobs(
        self,
        plugin_key: str | None = None,
        status: InputJobStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InputJob]:
        """List input jobs with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if plugin_key is not None:
            conditions.append("plugin_key = ?")
            params.append(plugin_key)
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM input_jobs
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_job(r) for r in rows]

    def delete_job(self, job_id: str) -> None:
        """Delete an input job."""
        with self._connect() as conn:
            conn.execute("DELETE FROM input_jobs WHERE id = ?", (job_id,))
        logger.info("InputJob %s deleted", job_id)
