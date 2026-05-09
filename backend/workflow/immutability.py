"""Immutability guards for workflow sessions.

Provides guard functions that prevent mutation of locked or archived
sessions.  Used by mutation endpoints (interject, pause, resume, cancel).
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a connection to the blueprint database."""
    path = Path(db_path) if db_path else _DEFAULT_DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _get_session_flags(
    session_id: str,
    db_path: Path | str | None = None,
) -> dict[str, int] | None:
    """Return ``is_locked`` and ``is_archived`` for a session row.

    Returns ``None`` if the session does not exist or the table is missing.
    """
    try:
        with _connect(db_path) as conn:
            row = conn.execute(
                "SELECT is_locked, is_archived FROM workflow_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
    except sqlite3.OperationalError:
        # Table does not exist yet (e.g. in tests without migration v6)
        return None
    if row is None:
        return None
    return {"is_locked": row["is_locked"], "is_archived": row["is_archived"]}


def guard_locked(
    session_id: str,
    db_path: Path | str | None = None,
) -> None:
    """Raise HTTP 403 if the session is locked (completed/failed).

    If the session is not found in the database (e.g. running from in-memory
    store only), the guard passes — the session is treated as mutable.

    Args:
        session_id: The workflow session ID.
        db_path: Optional database path override.

    Raises:
        HTTPException: 403 if the session is locked.
    """
    flags = _get_session_flags(session_id, db_path)
    if flags is None:
        return  # Session not in DB yet → treat as mutable
    if flags["is_locked"]:
        raise HTTPException(
            status_code=403,
            detail=f"Session {session_id} is locked and cannot be modified",
        )


def guard_not_archived(
    session_id: str,
    db_path: Path | str | None = None,
) -> None:
    """Raise HTTP 404 if the session is archived (soft-deleted).

    If the session is not found in the database, the guard passes.

    Args:
        session_id: The workflow session ID.
        db_path: Optional database path override.

    Raises:
        HTTPException: 404 if the session is archived.
    """
    flags = _get_session_flags(session_id, db_path)
    if flags is None:
        return  # Session not in DB yet → treat as mutable
    if flags["is_archived"]:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")


def guard_mutable(
    session_id: str,
    db_path: Path | str | None = None,
) -> None:
    """Combined guard: session must not be locked or archived.

    If the session is not found in the database, the guard passes.

    Args:
        session_id: The workflow session ID.
        db_path: Optional database path override.

    Raises:
        HTTPException: 404 if archived, 403 if locked.
    """
    guard_not_archived(session_id, db_path)
    guard_locked(session_id, db_path)


def lock_session(
    session_id: str,
    db_path: Path | str | None = None,
) -> None:
    """Set ``is_locked = 1`` on the session and related records.

    Locks:
    - ``workflow_sessions.is_locked``
    - ``state_snapshots.is_locked`` for all snapshots of this session
    - ``audit_log`` rows are inherently immutable (append-only), no column needed
    """
    try:
        with _connect(db_path) as conn:
            conn.execute(
                "UPDATE workflow_sessions SET is_locked = 1 WHERE id = ?",
                (session_id,),
            )
            conn.execute(
                "UPDATE state_snapshots SET is_locked = 1 WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
        logger.info("Session %s locked", session_id)
    except sqlite3.OperationalError:
        logger.debug("lock_session: table not found (test env)", exc_info=True)


def archive_session(
    session_id: str,
    db_path: Path | str | None = None,
) -> bool:
    """Set ``is_archived = 1`` on the session (soft delete).

    Returns ``True`` if a row was updated.
    """
    try:
        with _connect(db_path) as conn:
            cursor = conn.execute(
                "UPDATE workflow_sessions SET is_archived = 1 WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            updated = cursor.rowcount > 0
        if updated:
            logger.info("Session %s archived", session_id)
        return updated
    except sqlite3.OperationalError:
        logger.debug("archive_session: table not found (test env)", exc_info=True)
        return False


def restore_session(
    session_id: str,
    db_path: Path | str | None = None,
) -> bool:
    """Set ``is_archived = 0`` on the session (un-archive).

    Returns ``True`` if a row was updated.
    """
    try:
        with _connect(db_path) as conn:
            cursor = conn.execute(
                "UPDATE workflow_sessions SET is_archived = 0 WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            updated = cursor.rowcount > 0
        if updated:
            logger.info("Session %s restored", session_id)
        return updated
    except sqlite3.OperationalError:
        logger.debug("restore_session: table not found (test env)", exc_info=True)
        return False
