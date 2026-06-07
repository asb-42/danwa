"""Interjection service — manages user interjections during workflow execution.

Provides a per-session queue for interjections that workflow nodes can consume
at interjection points.  Thread-safe via :class:`asyncio.Lock`.

Two consumption modes
---------------------
* :meth:`InterjectionService.consume` — non-blocking pull.  Returns
  immediately with whatever is queued, or an empty list.  Used by agent
  nodes that want to opportunistically inject user input as additional
  context.
* :meth:`InterjectionService.consume_blocking` — waits until at least
  one interjection is available, then returns the items.  Used by the
  :func:`backend.workflow.nodes.system_nodes.interjection_node` so a
  workflow actually *pauses* at user-injection points instead of
  continuing with no input.

Persistence (L6 fix)
--------------------
The queue is mirrored to a SQLite database so open interjections
survive a server restart.  The schema lives in the same
``data/blueprints.db`` file used by :mod:`backend.workflow.audit_logger`
and :mod:`backend.workflow.state_snapshot` so the application only has
to manage one file.

In-memory behaviour is kept identical when no ``db_path`` is passed —
existing in-process tests and callers stay in the in-memory mode they
were written for.  The module-level singleton
:data:`interjection_service` is configured with the production default
DB path so the user-facing service is durable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


_DEFAULT_DB_PATH = Path("data/blueprints.db")


@dataclass
class Interjection:
    """A single interjection item in the queue."""

    interjection_id: str
    session_id: str
    content: str
    source: str  # "user" | "system" | "api"
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending" | "consumed"


class InterjectionService:
    """In-memory interjection queue per workflow session, mirrored to SQLite.

    Thread-safe via :class:`asyncio.Lock` for the in-memory state and a
    :class:`threading.RLock` for the SQLite connection.  When ``db_path``
    is ``None`` (default for in-process tests) the service behaves
    exactly like the previous in-memory only implementation: nothing is
    written to disk and nothing is loaded on startup.
    """

    def __init__(self, db_path: Path | str | None = None) -> None:
        # session_id → list of Interjection objects
        self._queues: dict[str, list[Interjection]] = {}
        # session_id → asyncio.Event that is set when new items are queued
        # and cleared again after they are consumed.  Used by
        # consume_blocking() to suspend callers without polling.
        self._wake_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

        self._db_path: Path | None = Path(db_path) if db_path else None
        self._db_lock: threading.RLock | None = threading.RLock() if self._db_path else None
        self._conn: sqlite3.Connection | None = None
        # Track which sessions have been hydrated from the DB so the
        # per-session SELECT only runs once after a process restart.
        self._loaded_sessions: set[str] = set()

    # ------------------------------------------------------------------
    # Connection / persistence helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection | None:
        """Return the cached SQLite connection, opening on first use.

        Mirrors the lazy + RLock + WAL pattern from
        :class:`backend.workflow.audit_logger.AuditLogger` so concurrent
        FastAPI request threads share a single connection rather than
        paying the ``sqlite3.connect`` cost for every submit/consume.
        Returns ``None`` when the service runs in in-memory mode
        (``db_path=None``).
        """
        if self._db_path is None or self._db_lock is None:
            return None
        if self._conn is None:
            with self._db_lock:
                if self._conn is None:
                    self._db_path.parent.mkdir(parents=True, exist_ok=True)
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
                    self._init_schema(conn)
                    self._conn = conn
        return self._conn

    @staticmethod
    def _init_schema(conn: sqlite3.Connection) -> None:
        """Create the ``interjections`` table + supporting index if needed."""
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS interjections (
                interjection_id TEXT PRIMARY KEY,
                session_id      TEXT NOT NULL,
                content         TEXT NOT NULL,
                source          TEXT NOT NULL,
                metadata        TEXT NOT NULL DEFAULT '{}',
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT NOT NULL,
                consumed_at     TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_interjections_session_status ON interjections(session_id, status)")
        conn.commit()

    def close(self) -> None:
        """Close the cached SQLite connection.  Safe to call multiple times."""
        if self._db_lock is None:
            return
        with self._db_lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    logger.debug("Error closing interjection service connection", exc_info=True)
                self._conn = None

    def _ensure_loaded(self, session_id: str) -> None:
        """Hydrate the in-memory queue for ``session_id`` from SQLite.

        No-op when the service runs in in-memory mode, when the session
        has already been hydrated, or when the DB has no pending rows
        for the session.  Pending rows are appended in ``created_at``
        order so the wake-up semantics match the previous in-memory
        behaviour (FIFO).
        """
        if self._db_path is None or self._db_lock is None:
            return
        if session_id in self._loaded_sessions:
            return
        conn = self._get_conn()
        if conn is None:
            return
        with self._db_lock:
            try:
                rows = conn.execute(
                    "SELECT interjection_id, session_id, content, source, "
                    "metadata, status, created_at "
                    "FROM interjections "
                    "WHERE session_id = ? AND status = 'pending' "
                    "ORDER BY created_at ASC",
                    (session_id,),
                ).fetchall()
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to load interjections for session %s from %s",
                    session_id,
                    self._db_path,
                    exc_info=True,
                )
                # Mark as loaded so we don't keep hammering a broken DB.
                self._loaded_sessions.add(session_id)
                return
            for row in rows:
                try:
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                except json.JSONDecodeError:
                    metadata = {}
                if not isinstance(metadata, dict):
                    metadata = {}
                self._queues.setdefault(session_id, []).append(
                    Interjection(
                        interjection_id=row["interjection_id"],
                        session_id=row["session_id"],
                        content=row["content"],
                        source=row["source"],
                        metadata=metadata,
                        status=row["status"],
                    )
                )
            self._loaded_sessions.add(session_id)

    def _persist_insert(self, interjection: Interjection) -> None:
        """Write a new pending row to the SQLite mirror.

        Best-effort: a write failure is logged but does not propagate so
        a transient DB hiccup does not break the in-memory queue that
        the running workflow is actively reading from.
        """
        if self._db_path is None or self._db_lock is None:
            return
        conn = self._get_conn()
        if conn is None:
            return
        with self._db_lock:
            try:
                conn.execute(
                    "INSERT INTO interjections "
                    "(interjection_id, session_id, content, source, "
                    "metadata, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        interjection.interjection_id,
                        interjection.session_id,
                        interjection.content,
                        interjection.source,
                        json.dumps(interjection.metadata or {}),
                        interjection.status,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                conn.commit()
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to persist interjection %s to %s",
                    interjection.interjection_id,
                    self._db_path,
                    exc_info=True,
                )

    def _persist_mark_consumed(self, ids: list[str]) -> None:
        """Mark the given interjection rows as ``consumed`` in SQLite."""
        if not ids or self._db_path is None or self._db_lock is None:
            return
        conn = self._get_conn()
        if conn is None:
            return
        with self._db_lock:
            try:
                now = datetime.now(UTC).isoformat()
                for iid in ids:
                    conn.execute(
                        "UPDATE interjections SET status='consumed', consumed_at=? WHERE interjection_id=?",
                        (now, iid),
                    )
                conn.commit()
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to mark %d interjections as consumed in %s",
                    len(ids),
                    self._db_path,
                    exc_info=True,
                )

    def _persist_delete_session(self, session_id: str) -> None:
        """Delete every interjection row for ``session_id`` from SQLite."""
        if self._db_path is None or self._db_lock is None:
            return
        conn = self._get_conn()
        if conn is None:
            return
        with self._db_lock:
            try:
                conn.execute("DELETE FROM interjections WHERE session_id = ?", (session_id,))
                conn.commit()
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to delete interjections for session %s from %s",
                    session_id,
                    self._db_path,
                    exc_info=True,
                )

    # ------------------------------------------------------------------
    # Wake-event helper
    # ------------------------------------------------------------------

    def _get_wake_event(self, session_id: str) -> asyncio.Event:
        """Return the wake-up event for ``session_id``, creating it on demand."""
        event = self._wake_events.get(session_id)
        if event is None:
            event = asyncio.Event()
            # New sessions start in the "set" state — there is no
            # consumer blocked on this session yet, so the first
            # consume_blocking() call must check the queue first and
            # only wait if it is empty.
            event.set()
            self._wake_events[session_id] = event
        return event

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(
        self,
        session_id: str,
        content: str,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add an interjection to the queue for a session.

        Args:
            session_id: The workflow session ID.
            content: The interjection text content.
            source: Origin of the interjection ("user", "system", "api").
            metadata: Optional metadata dict.

        Returns:
            The generated interjection_id.
        """
        interjection_id = f"inj-{uuid.uuid4().hex[:12]}"
        interjection = Interjection(
            interjection_id=interjection_id,
            session_id=session_id,
            content=content,
            source=source,
            metadata=metadata or {},
        )

        async with self._lock:
            # Make sure any rows the DB already holds for this session
            # are mirrored in-memory first, otherwise the new entry
            # would be ordered incorrectly relative to rows a previous
            # process left behind.
            self._ensure_loaded(session_id)
            self._queues.setdefault(session_id, []).append(interjection)
            queue_size = len(self._queues[session_id])
            # Wake any consumer waiting in consume_blocking().  The
            # event stays "set" until the queue is fully drained by
            # the next consume(); see consume_blocking() for the
            # reset logic.
            self._get_wake_event(session_id).set()
            # Mirror to SQLite so a server restart does not lose the
            # submission.  Done inside the lock so the in-memory queue
            # size we log matches the rows we just inserted.
            self._persist_insert(interjection)

        # DIAGNOSTIC: Log submission with queue size so we can trace if consume() ever picks it up
        logger.info(
            "DIAG submit(): interjection=%s session=%s source=%s queue_size=%d",
            interjection_id,
            session_id,
            source,
            queue_size,
        )
        return interjection_id

    async def consume(self, session_id: str, node_id: str | None = None) -> list[dict[str, Any]]:
        """Pop all pending interjections for a session (non-blocking).

        Marks them as "consumed" and returns their data.  Returns
        immediately even if the queue is empty — use
        :meth:`consume_blocking` to wait for items.

        Args:
            session_id: The workflow session ID.
            node_id: Optional node ID for logging context.

        Returns:
            List of interjection dicts with keys: intervention_id, content,
            source, metadata.
        """
        results, _queue_size = await self._drain_pending(session_id, node_id)
        return results

    async def consume_blocking(
        self,
        session_id: str,
        node_id: str | None = None,
        timeout: float = 300.0,
    ) -> list[dict[str, Any]]:
        """Block until at least one interjection is available, then drain the queue.

        Polling-free: waits on a per-session :class:`asyncio.Event` that
        :meth:`submit` sets when it enqueues an item.  Cancels early
        if ``timeout`` elapses with no activity.

        Args:
            session_id: The workflow session ID.
            node_id: Optional node ID for logging context.
            timeout: Maximum seconds to wait for a submission.  Pass
                ``0`` to skip the wait (useful in tests).  Default is
                5 minutes — long enough to let a human respond
                interactively, short enough that forgotten sessions
                don't block the graph executor indefinitely.

        Returns:
            List of interjection dicts (possibly empty if the timeout
            fired before anything was submitted).
        """
        event = self._get_wake_event(session_id)

        # Cheap fast-path: if items are already queued, drain them
        # without awaiting.  This avoids the overhead of resetting and
        # re-setting the event for the common "submit and immediately
        # consume" pattern.
        results, queue_size = await self._drain_pending(session_id, node_id)
        if results:
            return results

        if timeout <= 0:
            return []

        logger.info(
            "consume_blocking: waiting for interjection session=%s node=%s timeout=%.1fs",
            session_id,
            node_id,
            timeout,
        )

        # Wait for the next submit().  We loop because multiple
        # consumers might race for the same event — the first one to
        # wake up drains the queue, the others find an empty queue
        # and have to wait for the next submit.
        while True:
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout)
            except TimeoutError:
                logger.info(
                    "consume_blocking: timeout session=%s node=%s after %.1fs",
                    session_id,
                    node_id,
                    timeout,
                )
                return []

            results, queue_size = await self._drain_pending(session_id, node_id)
            if results:
                return results

            # Queue was drained by a concurrent consumer; reset the
            # event so we wait for the *next* submit() and try again.
            event.clear()
            # If timeout was reached during the loop, bail out.
            # (We don't track elapsed time precisely here — the outer
            # wait_for is the real timeout enforcement.)

        # Unreachable: the loop above always returns.
        _ = queue_size  # keep linter happy
        return []

    async def _drain_pending(self, session_id: str, node_id: str | None) -> tuple[list[dict[str, Any]], int]:
        """Mark all pending items for ``session_id`` as consumed and return them.

        Returns ``(results, queue_size)``.  When ``queue_size`` is zero
        after the call, the wake-up event is reset so that the next
        :meth:`consume_blocking` call will block.
        """
        consumed_ids: list[str] = []
        async with self._lock:
            # Re-hydrate the in-memory cache from SQLite in case this
            # is the first operation after a server restart and a
            # user is still waiting for a response.
            self._ensure_loaded(session_id)
            queue = self._queues.get(session_id, [])
            queue_size = len(queue)
            pending = [ij for ij in queue if ij.status == "pending"]

            results: list[dict[str, Any]] = []
            for ij in pending:
                ij.status = "consumed"
                consumed_ids.append(ij.interjection_id)
                results.append(
                    {
                        "interjection_id": ij.interjection_id,
                        "content": ij.content,
                        "source": ij.source,
                        "metadata": ij.metadata,
                    }
                )

            # Garbage-collect fully consumed queues so they don't
            # accumulate across many short-lived sessions.
            if queue and all(ij.status == "consumed" for ij in queue):
                self._queues.pop(session_id, None)
                queue_size_after = 0
            else:
                queue_size_after = len(self._queues.get(session_id, []))

            # Mirror the consumed rows to SQLite so the next process
            # restart does not redeliver them.
            if consumed_ids:
                self._persist_mark_consumed(consumed_ids)

        # Reset the wake-up event when the queue is empty so the next
        # consume_blocking() call will block.  Done outside the lock to
        # avoid mixing asyncio primitives with the asyncio.Lock.
        if queue_size_after == 0:
            event = self._wake_events.get(session_id)
            if event is not None:
                event.clear()

        # DIAGNOSTIC: Always log consume calls so we can trace the flow
        logger.info(
            "DIAG consume() called: session=%s node=%s | queue_size=%d pending=%d consumed=%d",
            session_id,
            node_id,
            queue_size,
            len(pending),
            len(results),
        )
        return results, queue_size_after

    async def get_pending(self, session_id: str) -> list[dict[str, Any]]:
        """List pending interjections for a session without consuming them.

        Args:
            session_id: The workflow session ID.

        Returns:
            List of pending interjection dicts.
        """
        async with self._lock:
            # Same lazy hydration rationale as in _drain_pending.
            self._ensure_loaded(session_id)
            queue = self._queues.get(session_id, [])
            return [
                {
                    "interjection_id": ij.interjection_id,
                    "content": ij.content,
                    "source": ij.source,
                    "metadata": ij.metadata,
                    "status": ij.status,
                }
                for ij in queue
                if ij.status == "pending"
            ]

    async def clear(self, session_id: str) -> None:
        """Remove all interjections for a session.

        Args:
            session_id: The workflow session ID.
        """
        async with self._lock:
            self._queues.pop(session_id, None)
            # Forget the hydration marker so a later submit on the
            # same session id starts with a clean slate if the user
            # re-uses the id.
            self._loaded_sessions.discard(session_id)
            # Mirror to SQLite so a restart does not resurrect the
            # cleared rows.
            self._persist_delete_session(session_id)
        # Reset the wake-up event so future consumers block.
        event = self._wake_events.get(session_id)
        if event is not None:
            event.clear()
        logger.info("Cleared interjection queue for session %s", session_id)


# Module-level singleton — shared across the application and configured
# with the production default DB path so user input survives a server
# restart.  Tests that need an isolated service instantiate their own
# ``InterjectionService()`` without arguments.
interjection_service = InterjectionService(db_path=_DEFAULT_DB_PATH)
