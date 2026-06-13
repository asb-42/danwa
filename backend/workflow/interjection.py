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
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.state.pubsub import get_pubsub
from backend.state.wait_event import WaitEvent, get_wait_event

logger = logging.getLogger(__name__)


_DEFAULT_DB_PATH = Path("data/blueprints.db")


# Channel-name prefix for cross-process wake-up.  Same session_id →
# same channel → submit() in worker A wakes consume_blocking() in
# worker B (via the pub/sub backend in ``backend.state.pubsub``).
# The full channel name is ``f"danwa:interjection:wake:{session_id}"``.
_WAKE_CHANNEL_PREFIX = "danwa:interjection:wake:"


# ---------------------------------------------------------------------------
# Bounded in-process state
# ---------------------------------------------------------------------------
#
# P4.4 fix: the per-process dedup set (``_queued_ids``) and the
# session-keyed dicts (``_queues``, ``_hydration_version``,
# ``_wake_events``) used to grow without bound for the lifetime of
# the worker.  Even though consume() and clear() remove the obvious
# references, a misbehaving caller that submits faster than it drains
# could push memory usage up over time.  We cap each structure with
# a process-wide LRU.  Eviction never raises: the oldest entries are
# simply dropped, which is safe because every id / session is also
# mirrored to SQLite, so a re-hydration after a long pause can
# always re-populate the in-memory state.
_MAX_QUEUED_IDS: int = 50_000  # cap on dedup set (per worker)
_MAX_SESSION_KEYS: int = 5_000  # cap on per-session dicts
_QUEUED_IDS_EVICT_LOG_EVERY: int = 1_000  # log every N evictions to avoid log spam


class BoundedSet:
    """A set with a hard cap, backed by an LRU ``OrderedDict``.

    Exposes the ``set`` protocol actually used by InterjectionService
    (``add``, ``discard``, ``difference_update``, ``clear``,
    ``__contains__``, ``__len__``, ``__iter__``, ``__bool__``).
    Eviction is silent except for a throttled ``logger.debug``.

    The LRU is insertion-ordered — every ``add`` of an *existing*
    key is a no-op (the value is re-inserted to the back, which
    refreshes its position in the LRU).  The set's purpose is
    "is this id present?", not "what is the most recently used
    id?", so the LRU ordering is incidental: the cap is the
    important part.

    Eviction policy: when ``add`` would push the size over
    ``maxlen``, the *oldest* ``maxlen - size + 1`` keys are popped
    from the front and discarded.  This is bounded by ``maxlen``,
    not by the size of the new addition, so the worst-case cost
    of a single ``add`` is O(``maxlen``) which is fine for
    ``maxlen=50_000``.
    """

    __slots__ = ("_data", "_maxlen", "_evict_log_counter", "_evictions_total")

    def __init__(self, maxlen: int) -> None:
        if maxlen <= 0:
            raise ValueError("BoundedSet maxlen must be > 0")
        self._data: OrderedDict[str, None] = OrderedDict()
        self._maxlen = maxlen
        self._evict_log_counter: int = 0
        self._evictions_total: int = 0

    @property
    def maxlen(self) -> int:
        return self._maxlen

    @property
    def evictions_total(self) -> int:
        return self._evictions_total

    def add(self, value: str) -> None:
        # Insertion-order refresh: re-inserting an existing key bumps
        # it to the back of the LRU.
        if value in self._data:
            self._data.move_to_end(value)
            return
        self._data[value] = None
        # Trim from the front until we're at the cap.  The cap is
        # inclusive: a set of size N holds N distinct values.
        overflow = len(self._data) - self._maxlen
        if overflow > 0:
            for _ in range(overflow):
                evicted = self._data.popitem(last=False)
                self._evictions_total += 1
                self._evict_log_counter += 1
                if self._evict_log_counter >= _QUEUED_IDS_EVICT_LOG_EVERY:
                    self._evict_log_counter = 0
                    logger.debug(
                        "BoundedSet eviction: dropped %r (size=%d cap=%d evictions_total=%d)",
                        evicted[0],
                        len(self._data),
                        self._maxlen,
                        self._evictions_total,
                    )

    def discard(self, value: str) -> None:
        self._data.pop(value, None)

    def difference_update(self, values: Iterable[str]) -> None:
        # ``self._data`` is an OrderedDict[str, None]; using
        # ``difference_update`` would force an intermediate set.  A
        # loop with ``pop(value, None)`` is O(k) on the argument and
        # stays on the underlying data structure.
        for v in values:
            self._data.pop(v, None)

    def clear(self) -> None:
        self._data.clear()

    def __contains__(self, value: object) -> bool:
        return value in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._data)

    def __bool__(self) -> bool:
        return bool(self._data)

    def __eq__(self, other: object) -> bool:
        # Compare against any iterable of hashable elements so that
        # ``BoundedSet({"a", "b"}) == {"a", "b"}`` works as users
        # expect.  We intentionally do *not* check ``type(other)`` to
        # stay duck-typed; this is for tests and debug output, not
        # for production identity checks.
        if isinstance(self, type(other)):
            return set(self._data) == set(other._data)  # type: ignore[attr-defined]
        try:
            return set(self._data) == set(other)  # type: ignore[arg-type]
        except TypeError:
            return NotImplemented

    def __hash__(self) -> int:  # pragma: no cover - sets are unhashable
        # Sets are unhashable by contract; declaring __eq__ above
        # would otherwise make Python set __hash__ to None, but
        # being explicit is clearer.
        raise TypeError("BoundedSet is unhashable")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"BoundedSet(size={len(self._data)}, cap={self._maxlen}, evictions={self._evictions_total})"


class BoundedLRU:
    """Drop-in replacement for ``dict`` that caps the size with LRU
    eviction.  Exposes the methods used by InterjectionService
    (``__setitem__``, ``__getitem__``, ``get``, ``pop``, ``setdefault``,
    ``__contains__``, ``__len__``, ``__iter__``, ``__delitem__``,
    ``clear``, ``keys``, ``values``, ``items``)."""

    __slots__ = ("_data", "_maxlen")

    def __init__(self, maxlen: int) -> None:  # noqa: D401
        if maxlen <= 0:
            raise ValueError("BoundedLRU maxlen must be > 0")
        self._data: OrderedDict[str, Any] = OrderedDict()
        self._maxlen = maxlen

    @property
    def maxlen(self) -> int:
        return self._maxlen

    def __setitem__(self, key: str, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
            self._data[key] = value
            return
        self._data[key] = value
        overflow = len(self._data) - self._maxlen
        if overflow > 0:
            for _ in range(overflow):
                self._data.popitem(last=False)

    def __getitem__(self, key: str) -> Any:
        value = self._data[key]
        self._data.move_to_end(key)
        return value

    def get(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return default

    def pop(self, key: str, *default: Any) -> Any:
        return self._data.pop(key, *default)

    def setdefault(self, key: str, default: Any = None) -> Any:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        self._data[key] = default
        overflow = len(self._data) - self._maxlen
        if overflow > 0:
            for _ in range(overflow):
                self._data.popitem(last=False)
        return default

    def __contains__(self, key: object) -> bool:
        return key in self._data

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self._data)

    def __delitem__(self, key: str) -> None:
        del self._data[key]

    def clear(self) -> None:
        self._data.clear()

    def keys(self):  # type: ignore[no-untyped-def]
        return self._data.keys()

    def values(self):  # type: ignore[no-untyped-def]
        return self._data.values()

    def items(self):  # type: ignore[no-untyped-def]
        return self._data.items()

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"BoundedLRU(size={len(self._data)}, cap={self._maxlen})"


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
        """Initialise InterjectionService."""
        # P4.4 fix: cap every per-process collection with a process-
        # wide LRU so a misbehaving caller cannot grow memory without
        # bound across the worker's lifetime.  ``_MAX_SESSION_KEYS``
        # is generous (5 000) — production traffic tops out at a few
        # hundred concurrent sessions.
        self._queues: dict[str, list[Interjection]] = BoundedLRU(maxlen=_MAX_SESSION_KEYS)
        # session_id → WaitEvent that is set when new items are queued
        # and cleared again after they are consumed.  Used by
        # consume_blocking() to suspend callers without polling.
        # F-01 fix: WaitEvent (from backend.state.wait_event) is
        # backed by the shared pub/sub backend — Redis in production,
        # in-memory for single-process tests — so a submit() in worker A
        # wakes a consume_blocking() in worker B.  The previous
        # asyncio.Event was bound to a single event loop and never
        # crossed process boundaries.
        self._wake_events: dict[str, WaitEvent] = BoundedLRU(maxlen=_MAX_SESSION_KEYS)
        self._lock = asyncio.Lock()

        self._db_path: Path | None = Path(db_path) if db_path else None
        self._db_lock: threading.RLock | None = threading.RLock() if self._db_path else None
        self._conn: sqlite3.Connection | None = None
        # Track the channel ``_set_count`` at the time we last hydrated
        # each session from SQLite.  Re-hydrate when the count has
        # advanced — this catches cross-process submissions that arrive
        # via the wake-up signal (F-01) without forcing a redundant
        # SELECT on every operation in the common case.
        # P4.4 fix: capped with the same LRU as ``_queues`` and
        # ``_wake_events``.
        self._hydration_version: dict[str, int] = BoundedLRU(maxlen=_MAX_SESSION_KEYS)
        # Set of interjection_ids currently in some in-memory queue.
        # Used by ``_ensure_loaded`` to skip DB rows that are already
        # represented in memory — a row the same process just submitted
        # would otherwise show up twice after a re-hydration triggered
        # by the wake event.
        # P4.4 fix: previously a plain ``set`` that grew for the
        # process lifetime.  Now a :class:`BoundedSet` capped at
        # ``_MAX_QUEUED_IDS`` (50 000) with LRU eviction; if a
        # misbehaving caller ever fills it, the *oldest* ids are
        # dropped.  A dropped id can no longer suppress a re-hydration
        # of the same row, which is fine because the SQLite mirror
        # already stores the row as ``pending`` — the next
        # ``_ensure_loaded`` will just re-add it.
        self._queued_ids: set[str] = BoundedSet(maxlen=_MAX_QUEUED_IDS)
        # F-04 counter — number of times a ``_persist_*`` call failed.
        # Operations can poll this attribute (or call
        # :meth:`get_persist_failure_count`) to detect a chronically
        # broken DB (disk full, permissions, corrupt file) that would
        # otherwise be invisible because each failing call is
        # best-effort and only logs a warning.  Reset to 0 only at
        # process restart; the counter accumulates over the worker's
        # lifetime so a deploy will not lose the signal.
        self._persist_failure_count: int = 0

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
        has already been hydrated at the current channel ``_set_count``,
        or when the DB has no pending rows for the session.  Pending
        rows are appended in ``created_at`` order so the wake-up
        semantics match the previous in-memory behaviour (FIFO).

        F-01 cross-process fix: the version is the channel's
        ``_set_count`` at hydration time, not just a "have I seen this
        session" flag.  When a different process sets the wake event
        for this session, the count advances and we re-hydrate — the
        previous per-process ``_loaded_sessions`` set would have left
        a freshly-arrived DB row invisible to the second process.

        F-02 note: this method is still synchronous and runs the
        ``SELECT`` while holding the ``threading.RLock`` (not the
        ``asyncio.Lock``).  It is fast in the common case — the
        version short-circuit is a dict lookup, the slow path only
        fires on first access per session or after a cross-process
        set.  The every-operation disk I/O in the original code was
        the per-row ``INSERT`` / ``UPDATE`` / ``DELETE`` calls
        (``_persist_*``); those have been moved to ``asyncio.to_thread``
        by the submit / ``_drain_pending`` / ``clear`` callers.
        """
        if self._db_path is None or self._db_lock is None:
            return
        channel = get_pubsub().channel(f"{_WAKE_CHANNEL_PREFIX}{session_id}")
        current_version = channel.set_count
        if self._hydration_version.get(session_id) == current_version:
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
                    # F-05 fix: ``interjection_id`` is a UUID-derived
                    # 12-hex-char string, uniformly distributed — a
                    # deterministic tie-breaker for submits that
                    # happened in the same microsecond.  Without it
                    # SQLite falls back to rowid order, which can
                    # shift after a VACUUM and silently re-order
                    # items across a process restart.
                    "ORDER BY created_at ASC, interjection_id ASC",
                    (session_id,),
                ).fetchall()
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to load interjections for session %s from %s",
                    session_id,
                    self._db_path,
                    exc_info=True,
                )
                # Record the version we attempted so we don't keep
                # hammering a broken DB on every wake-up.
                self._hydration_version[session_id] = current_version
                return
            for row in rows:
                if row["interjection_id"] in self._queued_ids:
                    # Same process already has this row in memory —
                    # the re-hydration triggered by a wake event
                    # must not duplicate it.
                    continue
                try:
                    metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                except json.JSONDecodeError:
                    metadata = {}
                if not isinstance(metadata, dict):
                    metadata = {}
                self._queued_ids.add(row["interjection_id"])
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
            self._hydration_version[session_id] = current_version

    def _persist_insert(self, interjection: Interjection) -> bool:
        """Write a new pending row to the SQLite mirror.

        F-04 fix: returns ``True`` on success and ``False`` if the
        DB write failed.  The ``_persist_failure_count`` counter is
        incremented on every failure so operations can detect a
        chronically broken DB (disk full, permissions, corrupt file)
        that would otherwise be invisible because each failing call
        is best-effort and only logs a warning.

        The in-memory queue is the source of truth for the running
        session — even on ``False`` the caller keeps the
        ``interjection_id`` and the workflow continues.  The data is
        simply lost on the next process restart unless operations
        notices the counter going up.
        """
        if self._db_path is None or self._db_lock is None:
            return True
        conn = self._get_conn()
        if conn is None:
            return True
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
                        self._safe_json_dumps(interjection.metadata),
                        interjection.status,
                        datetime.now(UTC).isoformat(),
                    ),
                )
                conn.commit()
                return True
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to persist interjection %s to %s",
                    interjection.interjection_id,
                    self._db_path,
                    exc_info=True,
                )
                self._persist_failure_count += 1
                return False

    def _persist_mark_consumed(self, ids: list[str]) -> bool:
        """Mark the given interjection rows as ``consumed`` in SQLite.

        F-04 fix: returns ``True`` on success and ``False`` on DB
        failure.  The caller (currently :meth:`_drain_pending`) uses
        the ``False`` return to roll back the in-memory status of
        the affected items back to ``pending`` so a process restart
        does not silently re-deliver rows the running session
        considered already consumed.
        """
        if not ids or self._db_path is None or self._db_lock is None:
            return True
        conn = self._get_conn()
        if conn is None:
            return True
        with self._db_lock:
            try:
                now = datetime.now(UTC).isoformat()
                for iid in ids:
                    conn.execute(
                        "UPDATE interjections SET status='consumed', consumed_at=? WHERE interjection_id=?",
                        (now, iid),
                    )
                conn.commit()
                return True
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to mark %d interjections as consumed in %s",
                    len(ids),
                    self._db_path,
                    exc_info=True,
                )
                self._persist_failure_count += 1
                return False

    @staticmethod
    def _safe_json_dumps(obj: Any) -> str:
        """Serialize *obj* to JSON, returning ``"{}"`` on any error.

        F-07 fix: ``json.dumps`` can raise ``TypeError`` or
        ``ValueError`` (e.g. circular references, non-serializable
        values).  Callers should never see a 500 because of bad
        metadata — degrade to an empty object instead.
        """
        try:
            return json.dumps(obj or {})
        except (TypeError, ValueError):
            logger.warning("Failed to serialize metadata — falling back to '{}'", exc_info=True)
            return "{}"

    def _persist_delete_session(self, session_id: str) -> bool:
        """Delete every interjection row for ``session_id`` from SQLite.

        F-04 fix: returns ``True`` on success and ``False`` on DB
        failure.  The caller continues even on failure (the in-memory
        queue is the source of truth) but the counter is bumped so
        operations sees the broken DB.
        """
        if self._db_path is None or self._db_lock is None:
            return True
        conn = self._get_conn()
        if conn is None:
            return True
        with self._db_lock:
            try:
                conn.execute("DELETE FROM interjections WHERE session_id = ?", (session_id,))
                conn.commit()
                return True
            except sqlite3.DatabaseError:
                logger.warning(
                    "Failed to delete interjections for session %s in %s",
                    session_id,
                    self._db_path,
                    exc_info=True,
                )
                self._persist_failure_count += 1
                return False

    # ------------------------------------------------------------------
    # Wake-event helper
    # ------------------------------------------------------------------
    # Wake-event helper
    # ------------------------------------------------------------------

    def _get_wake_event(self, session_id: str) -> WaitEvent:
        """Return the wake-up event for ``session_id``, creating it on demand.

        The event is a ``WaitEvent`` from :mod:`backend.state.wait_event`,
        which is backed by the module-level pub/sub backend
        (``get_pubsub()``).  In production with ``settings.redis_url``
        set, the wake-up signal crosses worker boundaries; in single-
        process mode (tests, dev) it falls back to in-memory pub/sub
        with identical single-loop semantics.

        The channel name is deterministic per session_id, so two
        InterjectionService instances in different processes share the
        same channel and the same set/clear state.  New sessions are
        primed with ``set()`` so the first ``consume_blocking()`` call
        falls through the fast-path and consults the in-memory queue
        before waiting — this preserves the previous
        "check queue first, then wait" semantics.
        """
        event = self._wake_events.get(session_id)
        if event is None:
            event = get_wait_event(f"{_WAKE_CHANNEL_PREFIX}{session_id}")
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
        # F-07: sanitize metadata — reject non-dict values to prevent
        # serialization failures and data loss on reload.
        if not isinstance(metadata, dict):
            if metadata is not None:
                logger.warning(
                    "submit(): metadata is %s (expected dict), coercing to {}",
                    type(metadata).__name__,
                )
            metadata = {}

        interjection_id = f"inj-{uuid.uuid4().hex[:12]}"
        interjection = Interjection(
            interjection_id=interjection_id,
            session_id=session_id,
            content=content,
            source=source,
            metadata=metadata,
        )

        async with self._lock:
            # Make sure any rows the DB already holds for this session
            # are mirrored in-memory first, otherwise the new entry
            # would be ordered incorrectly relative to rows a previous
            # process left behind.
            self._ensure_loaded(session_id)
            self._queued_ids.add(interjection.interjection_id)
            self._queues.setdefault(session_id, []).append(interjection)
            queue_size = len(self._queues[session_id])

        # Mirror to SQLite *outside* the asyncio.Lock so a slow
        # ``conn.commit()`` (EBS throttle, NFS hiccup, fsync spike)
        # cannot block the event loop and wedge every other coroutine
        # in this worker — see reports/2026-06-07_code-review.md F-02.
        # We ``await`` the thread rather than fire-and-forget so
        # callers keep the existing "sofort persistiert" semantics;
        # the only thing that changes is *where* the I/O runs.
        if self._db_path is not None:
            await asyncio.to_thread(self._persist_insert, interjection)

        # Wake any consumer waiting in consume_blocking() *after* the
        # DB write completes so a cross-process consumer that wakes
        # up and runs ``_ensure_loaded`` is guaranteed to find the
        # row it just got woken for.  Wake timing is in-memory (no
        # I/O on this path), so moving it here does not regress the
        # event-loop responsiveness the F-02 fix is supposed to buy.
        self._get_wake_event(session_id).set()

        logger.debug(
            "submit(): interjection=%s session=%s source=%s queue_size=%d",
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

        Polling-free: waits on a per-session :class:`WaitEvent` that
        :meth:`submit` sets when it enqueues an item.  Cancels early
        if ``timeout`` elapses with no activity.

        F-01 fix: the wake event is backed by the module-level
        pub/sub backend (``backend.state.pubsub.get_pubsub()``), so
        a ``submit()`` in worker A wakes a ``consume_blocking()`` in
        worker B in a multi-worker deployment.  The previous
        ``asyncio.Event`` was bound to a single event loop and
        silently never crossed process boundaries — the consumer
        would only see its own worker's submits.

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
        # and have to wait for the next submit.  ``WaitEvent.wait``
        # handles its own ``asyncio.wait_for`` so a single timeout
        # call covers the whole blocking call.
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                logger.info(
                    "consume_blocking: timeout session=%s node=%s after %.1fs",
                    session_id,
                    node_id,
                    timeout,
                )
                return []
            woken = await event.wait(timeout=remaining)
            if not woken:
                # Timed out before any wake-up — same exit as above.
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

        # Unreachable: the loop above always returns.
        _ = queue_size  # keep linter happy
        return []

    async def _drain_pending(self, session_id: str, node_id: str | None) -> tuple[list[dict[str, Any]], int]:
        """Mark all pending items for ``session_id`` as consumed and return them.

        Returns ``(results, queue_size)``.  When ``queue_size`` is zero
        after the call, the wake-up event is reset so that the next
        :meth:`consume_blocking` call will block.

        F-02 fix: the in-memory drain runs under the asyncio.Lock as
        before, but the SQLite ``UPDATE`` that mirrors the consumed
        rows runs on a worker thread via ``asyncio.to_thread`` after
        the lock is released.  A slow ``conn.commit()`` can no longer
        block every other coroutine in the worker process.

        F-04 fix: if the persist call returns ``False`` the in-memory
        status of the affected items is rolled back to ``pending``
        and the dedup set is restored, so a process restart that
        re-reads the DB will not silently re-deliver rows the
        running session considered already consumed.  The garbage
        collection of fully consumed queues is also deferred to
        after the persist so the rollback can find the items.
        """
        consumed_ids: list[str] = []
        results: list[dict[str, Any]] = []
        queue_size_after: int
        pending: list[Interjection]
        async with self._lock:
            # Re-hydrate the in-memory cache from SQLite in case this
            # is the first operation after a server restart and a
            # user is still waiting for a response.
            self._ensure_loaded(session_id)
            queue = self._queues.get(session_id, [])
            queue_size = len(queue)
            pending = [ij for ij in queue if ij.status == "pending"]

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
            if consumed_ids:
                self._queued_ids.difference_update(consumed_ids)
            # Snapshot the post-drain queue length but defer the
            # actual garbage collection until *after* the persist so
            # the F-04 rollback path can still find the items to
            # re-mark as pending.
            queue_size_after = len(self._queues.get(session_id, []))

        # Mirror the consumed rows to SQLite *outside* the lock so
        # the ``UPDATE … consumed_at = ?`` plus the ``commit()`` run
        # on a worker thread (F-02).  We snapshot ``consumed_ids``
        # above so this section has no in-memory dependencies on the
        # queue state.
        persisted_ok = True
        if consumed_ids and self._db_path is not None:
            persisted_ok = await asyncio.to_thread(self._persist_mark_consumed, list(consumed_ids))

        # F-04 rollback / GC — both run under the lock because they
        # touch ``_queues`` and ``_queued_ids``.
        async with self._lock:
            if not persisted_ok:
                # Persist failed: re-mark the items as ``pending`` so
                # the next drain (or a process restart that reads
                # the DB) re-delivers them.  Without this rollback
                # the in-memory queue would say ``consumed`` while
                # the DB still has the rows as ``pending``, and a
                # restart would re-deliver them *while* the running
                # session had already considered them done — a
                # silent divergence.
                for iid in consumed_ids:
                    self._queued_ids.add(iid)
                    for ij in self._queues.get(session_id, []):
                        if ij.interjection_id == iid:
                            ij.status = "pending"
                            break
                queue_size_after = len(self._queues.get(session_id, []))
            else:
                # Persist succeeded: GC the queue if every item is
                # now consumed.
                queue = self._queues.get(session_id)
                if queue and all(ij.status == "consumed" for ij in queue):
                    self._queues.pop(session_id, None)
                    queue_size_after = 0

        # Reset the wake-up event when the queue is empty so the next
        # consume_blocking() call will block.  Done outside the lock to
        # avoid mixing asyncio primitives with the asyncio.Lock.
        if queue_size_after == 0:
            event = self._wake_events.get(session_id)
            if event is not None:
                event.clear()

        logger.debug(
            "consume(): session=%s node=%s | queue_size=%d pending=%d consumed=%d persisted_ok=%s",
            session_id,
            node_id,
            queue_size,
            len(pending),
            len(results),
            persisted_ok,
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

    def get_persist_failure_count(self) -> int:
        """Return the cumulative number of failed ``_persist_*`` calls.

        F-04 observability: increments on every ``_persist_insert``,
        ``_persist_mark_consumed``, and ``_persist_delete_session``
        failure.  Operations can poll this (e.g. expose it on a
        ``/healthz``-style endpoint or wire it into Prometheus) to
        detect a chronically broken DB (disk full, permissions,
        corrupt file) that would otherwise be invisible because
        each failing call is best-effort and only logs a warning.

        The counter is per-instance (one per worker process); for
        an aggregate view across the 4-worker Gunicorn deployment,
        sum the values from every worker's
        ``interjection_service`` instance — they share the same
        underlying DB, so a chronically broken DB will show up on
        every worker.
        """
        return self._persist_failure_count

    async def clear(self, session_id: str) -> None:
        """Remove all interjections for a session.

        Args:
            session_id: The workflow session ID.
        """
        async with self._lock:
            # Capture the IDs that belong to this session *before*
            # removing the queue so we can drop them from the dedup
            # set without re-iterating the now-empty queue.
            session_ids = {ij.interjection_id for ij in self._queues.get(session_id, [])}
            self._queues.pop(session_id, None)
            # Forget the hydration marker so a later submit on the
            # same session id starts with a clean slate if the user
            # re-uses the id.
            self._hydration_version.pop(session_id, None)
            self._queued_ids.difference_update(session_ids)
            # F-06 fix: Clear the wake event while still holding the
            # lock.  The old code cleared it *after* releasing the
            # lock, which created a window where a concurrent submit()
            # could set the event, then we would clear its signal —
            # causing the consumer to miss the new item until the
            # next interaction.  Clearing inside the lock guarantees
            # that no submit() can race with our clear.
            event = self._wake_events.get(session_id)
            if event is not None:
                event.clear()
        # Mirror to SQLite *outside* the lock so the ``DELETE`` plus
        # ``commit()`` runs on a worker thread (F-02).  In-memory state
        # is the source of truth for the running session; the DB is a
        # restart-resilience backup, so a slow DELETE just delays
        # cleanup — it does not block the event loop.
        if self._db_path is not None:
            await asyncio.to_thread(self._persist_delete_session, session_id)
        logger.info("Cleared interjection queue for session %s", session_id)


# Module-level singleton — shared across the application and configured
# with the production default DB path so user input survives a server
# restart.  Tests that need an isolated service instantiate their own
# ``InterjectionService()`` without arguments.
interjection_service = InterjectionService(db_path=_DEFAULT_DB_PATH)
