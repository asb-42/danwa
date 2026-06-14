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
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.models.schemas import AuditLogQuery

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class AuditLogger:
    """Append-only audit logger for workflow execution events.

    Uses the ``audit_log`` table (migration v6+).  Thread-safe via a
    shared ``sqlite3.Connection`` cached on the instance (one connection
    per ``AuditLogger``) and serialised through an ``RLock`` — see
    :meth:`_get_conn`.  Concurrent reads benefit from WAL journal mode
    (enabled on first connect) and the lock is reentrant so callers that
    already hold it (e.g. nested helpers) do not deadlock.

    Stores both SHA-256 hashes (for integrity verification) AND full
    content strings (for replay, debugging, and auditing).
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise AuditLogger."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        # P4.5+ §4.5 — counters that make audit-insert failures visible
        # without spamming the log on every call.  See ``_insert``.
        self._insert_failures: int = 0
        self._session_error_logged: set[str] = set()

    # ------------------------------------------------------------------
    # Connection helper
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        """Return the cached connection, opening + WAL-initialising on first use.

        The first call opens the connection with ``check_same_thread=False``
        and a 30s busy timeout so other threads wait rather than raising.
        WAL journal mode is enabled (best-effort — ignored on filesystems
        that do not support it) so concurrent readers do not block writers.

        Subsequent calls return the same connection — the connect overhead
        is paid once per instance, not once per audit event.  This fixes
        audit M10 (100 connect/open cycles per 100 audit events).
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

    def _connect(self) -> sqlite3.Connection:
        """Backwards-compatible alias — returns the cached connection.

        Older call sites used ``with self._connect() as conn:``.  That
        pattern still works (the connection has ``__enter__``/``__exit__``)
        but the "with" block is now a no-op for close — the connection
        is reused for the next call.  Callers must ``commit()`` explicitly
        if they need durability before the next event.
        """
        return self._get_conn()

    def close(self) -> None:
        """Close the cached connection.  Safe to call multiple times.

        Mostly useful for tests that swap the DB path or for graceful
        shutdown.  Subsequent calls to ``_get_conn`` will lazily reopen.
        """
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    # P4.5+ §4.5 — promote from ``debug`` to ``warning``.
                    # A close failure almost always means the DB file
                    # was already removed or the process is in a bad
                    # state; the operator should know.
                    logger.warning("Error closing audit logger connection", exc_info=True)
                self._conn = None

    def get_insert_failure_count(self) -> int:
        """Return the number of failed ``_insert`` calls (P4.5+ §4.5).

        Exposed for tests and health checks.  A non-zero value means
        some audit events have been lost \u2014 typically because the
        audit DB was unreachable at the time of the insert.
        """
        return self._insert_failures

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
        """Insert a single audit log row with full content.

        Acquires the per-instance lock so concurrent writers serialise
        against each other and the cached connection is never used
        from two threads at once.  Commits after the insert so the
        row is durable before the call returns.

        Failure handling (P4.5+ §4.5):
            A failing insert does **not** raise.  The first failure
            per ``session_id`` is logged at ``error`` level with the
            underlying exception; subsequent failures for the same
            session drop to ``debug``.  The cached connection is
            dropped on every failure so the next call reopens (which
            recovers from transient file-lock / WAL / rotation
            errors).  The failure counter is exposed via
            :meth:`get_insert_failure_count` for tests and health
            checks.
        """
        now = datetime.now(UTC).isoformat()
        with self._lock:
            try:
                conn = self._get_conn()
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
                conn.commit()
            except Exception as exc:  # noqa: BLE001 — see docstring
                # P4.5+ §4.5 — a dead DB must not crash the workflow
                # node.  We:
                #   1. increment the failure counter (visible to
                #      tests / health checks via
                #      ``get_insert_failure_count``);
                #   2. drop the cached connection so the next call
                #      reopens (recovers from a transient file-lock
                #      or rotation);
                #   3. log a single ``error`` per workflow session —
                #      subsequent failures for the same session drop
                #      to ``debug`` so the operator gets one loud
                #      signal per session, not one per node.
                self._insert_failures += 1
                self._conn = None
                if session_id in self._session_error_logged:
                    logger.debug(
                        "AuditLogger: insert failed for session %s (suppressed; see the first error above): %s",
                        session_id,
                        exc,
                    )
                else:
                    self._session_error_logged.add(session_id)
                    logger.error(
                        "AuditLogger: insert failed for session %s; "
                        "dropping cached connection and continuing. "
                        "All further events for this session will be "
                        "logged at debug level. Underlying error: %s",
                        session_id,
                        exc,
                        exc_info=True,
                    )
                # Intentionally do NOT re-raise: the workflow runner
                # and node bodies rely on audit failures being
                # non-fatal.  The counter above is the only durable
                # signal that audit is degraded.

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

    def log_gate_decision(
        self,
        *,
        session_id: str,
        workflow_id: str,
        workflow_version: int,
        gate_node_id: str,
        condition: str,
        result: bool,
        chosen_target: str,
        fallback_used: bool,
        all_evaluations: list[dict[str, Any]] | None = None,
    ) -> None:
        """Record a gate routing decision with full evaluation details."""
        output_data = {
            "condition": condition,
            "result": result,
            "chosen_target": chosen_target,
            "fallback_used": fallback_used,
            "all_evaluations": all_evaluations or [],
        }
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type="gate_decision",
            node_id=gate_node_id,
            actor="gate",
            input_hash=self._compute_hash({"condition": condition}),
            output_hash=self._compute_hash(output_data),
            input_content=condition,
            output_content=self._sanitize_content(output_data),
        )
        logger.debug(
            "Audit: gate_decision session=%s gate=%s condition=%s result=%s target=%s",
            session_id,
            gate_node_id,
            condition,
            result,
            chosen_target,
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
        draft_version: int = 0,
        constructivity_score: float | None = None,
    ) -> None:
        """Record a workflow lifecycle event.

        For transactional drafting events (``builder_iteration``,
        ``pragmatist_evaluation``) the *draft_version* and
        *constructivity_score* are stored in dedicated columns.
        """
        self._insert(
            session_id=session_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            event_type=event_type,
            actor=actor,
            output_hash=self._compute_hash(metadata) if metadata else "",
            output_content=self._sanitize_content(metadata),
            draft_version=draft_version,
            constructivity_score=constructivity_score,
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

        with self._lock:
            conn = self._get_conn()
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
        with self._lock:
            conn = self._get_conn()
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
        with self._lock:
            conn = self._get_conn()
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
    ``node_failed`` after execution, including full content and SHA-256
    hashes.

    All synchronous SQLite writes are dispatched via
    :func:`asyncio.to_thread` so the I/O never blocks the event loop.
    This is critical in multi-workflow deployments where several agent
    nodes run concurrently on the same loop.

    Args:
        audit_log: The ``AuditLogger`` instance to write events to.
        node_id: The workflow node ID being decorated.
        actor: The actor label for audit entries (default ``"system"``).

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
            """Wrapper the instance."""
            import asyncio

            session_id = state.get("session_id", "")
            workflow_id = state.get("workflow_id", "")
            workflow_version = state.get("workflow_version", 1)

            # 4.1: Run synchronous audit writes off the event loop
            # thread via asyncio.to_thread() so the SQLite I/O doesn't
            # block other coroutines in multi-workflow deployments.

            # --- Log: node started ---
            await asyncio.to_thread(
                audit_log.log_node_started,
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
                await asyncio.to_thread(
                    audit_log.log_node_execution,
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
                await asyncio.to_thread(
                    audit_log.log_node_failed,
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
