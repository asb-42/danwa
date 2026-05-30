"""Workflow AuditLogger — append-only audit trail for workflow execution.

Records node executions, interjections, and workflow lifecycle events
into the ``audit_log`` table created by migration v6.

Updated Sprint 3: Stores full input/output content (not just hashes)
for complete reproducibility, debugging, and replay capability.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.models.schemas import AuditLogQuery

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class AuditLogger:
    """Append-only audit logger for workflow execution events.

    Uses the ``audit_log`` table (migration v6+).  Thread-safe via a new
    ``sqlite3.connect()`` per call, matching the pattern in
    :class:`backend.persistence.audit.AuditService`.

    Stores both SHA-256 hashes (for integrity verification) AND full
    content strings (for replay, debugging, and auditing).
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Hash helper
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_hash(data: Any) -> str:
        """Return the SHA-256 hex digest of *data*."""
        if data is None:
            return ""
        if isinstance(data, (dict, list)):
            payload = json.dumps(data, sort_keys=True, default=str)
        else:
            payload = str(data)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _sanitize_content(data: Any, max_len: int = 50000) -> str:
        """Convert arbitrary data to a string for storage, with length cap."""
        if data is None:
            return ""
        if isinstance(data, str):
            return data[:max_len]
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False, default=str)[:max_len]
        return str(data)[:max_len]

    # ------------------------------------------------------------------
    # Write helpers (append-only)
    # ------------------------------------------------------------------

    def _insert(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        event_type: str,
        node_id: str | None = None,
        actor: str = "system",
        input_hash: str = "",
        output_hash: str = "",
        input_content: str = "",
        output_content: str = "",
        trace_log_path: str = "",
        llm_profile_id: str = "",
        latency_ms: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        critic_item_id: str = "",
        build_response_id: str = "",
        draft_version: int = 0,
        constructivity_score: float | None = None,
    ) -> None:
        """Insert a single audit log row with full content."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                    (session_id, workflow_id, workflow_version, timestamp,
                     event_type, node_id, actor,
                     input_hash, output_hash,
                     input_content, output_content, trace_log_path,
                     llm_profile_id, latency_ms, prompt_tokens, completion_tokens,
                     critic_item_id, build_response_id, draft_version, constructivity_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    workflow_id,
                    workflow_version,
                    now,
                    event_type,
                    node_id,
                    actor,
                    input_hash,
                    output_hash,
                    input_content,
                    output_content,
                    trace_log_path,
                    llm_profile_id,
                    latency_ms,
                    prompt_tokens,
                    completion_tokens,
                    critic_item_id,
                    build_response_id,
                    draft_version,
                    constructivity_score,
                ),
            )

    # ------------------------------------------------------------------
    # Public API — log events
    # ------------------------------------------------------------------

    def log_node_execution(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        node_id: str,
        actor: str = "system",
        input_data: Any = None,
        output_data: Any = None,
        llm_profile_id: str = "",
        latency_ms: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        trace_log_path: str = "",
        critic_item_id: str = "",
        build_response_id: str = "",
        draft_version: int = 0,
        constructivity_score: float | None = None,
    ) -> None:
        """Record a node execution event with full input/output content."""
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type="node_completed",
            node_id=node_id,
            actor=actor,
            input_hash=self._compute_hash(input_data),
            output_hash=self._compute_hash(output_data),
            input_content=self._sanitize_content(input_data),
            output_content=self._sanitize_content(output_data),
            trace_log_path=trace_log_path,
            llm_profile_id=llm_profile_id,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            critic_item_id=critic_item_id,
            build_response_id=build_response_id,
            draft_version=draft_version,
            constructivity_score=constructivity_score,
        )
        logger.debug(
            "Audit: node_completed session=%s node=%s latency=%dms",
            session_id,
            node_id,
            latency_ms,
        )

    def log_node_started(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        node_id: str,
        actor: str = "system",
        input_data: Any = None,
    ) -> None:
        """Record that a node has started execution."""
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type="node_started",
            node_id=node_id,
            actor=actor,
            input_hash=self._compute_hash(input_data),
            input_content=self._sanitize_content(input_data),
        )

    def log_node_failed(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        node_id: str,
        actor: str = "system",
        error: str = "",
    ) -> None:
        """Record that a node execution failed."""
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type="node_failed",
            node_id=node_id,
            actor=actor,
            output_hash=self._compute_hash(error) if error else "",
            output_content=error,
        )

    def log_interjection(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        node_id: str | None = None,
        actor: str = "user",
        content: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an interjection event with full content."""
        combined = {"content": content, **(metadata or {})}
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type="interjection_submitted",
            node_id=node_id,
            actor=actor,
            input_hash=self._compute_hash(combined),
            input_content=content,
        )
        logger.debug(
            "Audit: interjection_submitted session=%s actor=%s",
            session_id,
            actor,
        )

    def log_workflow_event(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        event_type: str,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record a workflow lifecycle event."""
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type=event_type,
            actor=actor,
            output_hash=self._compute_hash(metadata) if metadata else "",
            output_content=self._sanitize_content(metadata),
        )
        logger.debug(
            "Audit: %s session=%s",
            event_type,
            session_id,
        )

    # ------------------------------------------------------------------
    # Read API
    # ------------------------------------------------------------------

    def get_audit_log(
        self,
        session_id: str,
        filters: AuditLogQuery | None = None,
    ) -> list[dict[str, Any]]:
        """Query audit log entries for a session with optional filters."""
        clauses: list[str] = ["session_id = ?"]
        params: list[Any] = [session_id]

        if filters is not None:
            if filters.workflow_id:
                clauses.append("workflow_id = ?")
                params.append(filters.workflow_id)
            if filters.event_type:
                clauses.append("event_type = ?")
                params.append(filters.event_type)
            if filters.date_from:
                clauses.append("timestamp >= ?")
                params.append(filters.date_from)
            if filters.date_to:
                clauses.append("timestamp <= ?")
                params.append(filters.date_to)

        where = " AND ".join(clauses)
        limit = filters.limit if filters else 100
        offset = filters.offset if filters else 0

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM audit_log
                WHERE {where}
                ORDER BY timestamp ASC
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()
        return [dict(r) for r in rows]

    def get_audit_log_for_replay(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Return all audit log entries for *session_id* ordered by timestamp."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM audit_log
                WHERE session_id = ?
                ORDER BY timestamp ASC
                """,
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def count_events(self, session_id: str) -> int:
        """Count audit log entries for a session."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM audit_log WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return row[0] if row else 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_audit_logger: AuditLogger | None = None


def get_audit_logger(db_path: Path | str | None = None) -> AuditLogger:
    """Return the module-level AuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(db_path)
    return _audit_logger


def reset_audit_logger() -> None:
    """Reset the module-level singleton (for testing)."""
    global _audit_logger
    _audit_logger = None


# ---------------------------------------------------------------------------
# Audit decorator for node functions
# ---------------------------------------------------------------------------


def audit_decorator(
    audit_log: AuditLogger,
    node_id: str,
    actor: str = "system",
):
    """Decorator that wraps an async node function with audit logging.

    Records ``node_started`` before execution and ``node_completed`` or
    ``node_failed`` after execution, including full content and SHA-256 hashes.

    Usage::

        @audit_decorator(get_audit_logger(), node_id="node_1", actor="strategist")
        async def my_node(state: WorkflowState) -> dict:
            ...
    """
    import functools
    import time

    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(state: dict) -> dict:
            session_id = state.get("session_id", "")
            workflow_id = state.get("workflow_id", "")
            workflow_version = state.get("workflow_version", 1)

            # --- Log: node started ---
            audit_log.log_node_started(
                session_id=session_id,
                workflow_id=workflow_id,
                workflow_version=workflow_version,
                node_id=node_id,
                actor=actor,
                input_data=state,
            )

            start = time.monotonic()
            try:
                result = await fn(state)
                elapsed_ms = int((time.monotonic() - start) * 1000)

                # --- Log: node completed ---
                audit_log.log_node_execution(
                    session_id=session_id,
                    workflow_id=workflow_id,
                    workflow_version=workflow_version,
                    node_id=node_id,
                    actor=actor,
                    input_data=state,
                    output_data=result,
                    latency_ms=elapsed_ms,
                )
                return result

            except Exception as exc:
                elapsed_ms = int((time.monotonic() - start) * 1000)

                # --- Log: node failed ---
                audit_log.log_node_failed(
                    session_id=session_id,
                    workflow_id=workflow_id,
                    workflow_version=workflow_version,
                    node_id=node_id,
                    actor=actor,
                    error=str(exc),
                )
                raise

        return wrapper

    return decorator
