"""Tests for F-05 — deterministic tie-breaker in the ``_ensure_loaded`` query.

The L6 (Sprint 49) ``_ensure_loaded`` query used
``ORDER BY created_at ASC``.  ``created_at`` is populated with
``datetime.now(UTC).isoformat()`` (microsecond resolution), so
two submits in the same microsecond produce identical timestamps
and SQLite falls back to rowid order — which can shift across a
process restart after a VACUUM.  The fix adds ``interjection_id``
(an uniformly-distributed 12-hex-char string) as a deterministic
tie-breaker so the re-delivery order after a restart is stable.

These tests insert rows with an explicit identical ``created_at``
and verify the SELECT returns them in ``interjection_id`` ascending
order, not in the rowid order of the underlying B-tree.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from backend.state.pubsub import reset_pubsub_cache
from backend.workflow.interjection import (
    InterjectionService,
)


def _insert_row(
    db: Path,
    interjection_id: str,
    session_id: str,
    content: str,
    created_at: str,
) -> None:
    """Insert a row directly into the SQLite mirror with a fixed ``created_at``."""
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            "INSERT INTO interjections (interjection_id, session_id, content, source, metadata, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                interjection_id,
                session_id,
                content,
                "user",
                json.dumps({}),
                "pending",
                created_at,
            ),
        )
        conn.commit()


class TestEnsureLoadedTieBreaker:
    """Verify ``_ensure_loaded`` uses ``interjection_id`` as a tie-breaker."""

    def test_identical_created_at_returns_interjection_id_ascending(self, tmp_path: Path) -> None:
        """Rows with the *same* ``created_at`` must come back ordered by id.

        The insertion order is deliberately non-alphabetic
        (``ccc``, ``aaa``, ``bbb``) so a rowid-ordered SELECT would
        return them in that order.  The F-05 fix re-orders them to
        ``aaa``, ``bbb``, ``ccc`` because that is the
        ``interjection_id`` ascending order, which is the
        deterministic tie-breaker the report mandates.
        """
        db = tmp_path / "i.db"

        reset_pubsub_cache()
        try:
            service = InterjectionService(db_path=db)
            # Force the schema to be created by touching the
            # connection, then insert via the now-existing table.
            conn = service._get_conn()
            assert conn is not None
            fixed_ts = "2026-06-07T10:23:45.123456+00:00"
            _insert_row(db, "inj-ccc-1111", "sess-tb-1", "third", fixed_ts)
            _insert_row(db, "inj-aaa-2222", "sess-tb-1", "first", fixed_ts)
            _insert_row(db, "inj-bbb-3333", "sess-tb-1", "second", fixed_ts)
            # Force a re-hydration: clear the version marker so the
            # next ``_ensure_loaded`` runs the SELECT.
            service._hydration_version.pop("sess-tb-1", None)
            service._ensure_loaded("sess-tb-1")

            queue = service._queues.get("sess-tb-1", [])
            ids = [ij.interjection_id for ij in queue]
            assert ids == [
                "inj-aaa-2222",
                "inj-bbb-3333",
                "inj-ccc-1111",
            ], f"Got {ids}, expected id-ascending order"
        finally:
            reset_pubsub_cache()

    def test_mixed_timestamps_keep_created_at_order_with_tie_break(self, tmp_path: Path) -> None:
        """Different ``created_at`` values are still the primary sort key.

        The tie-breaker only kicks in for *ties* on ``created_at``.
        Rows with different timestamps must still come back in
        ``created_at`` order; ``interjection_id`` only disambiguates
        rows that share a timestamp.
        """
        db = tmp_path / "i.db"

        reset_pubsub_cache()
        try:
            service = InterjectionService(db_path=db)
            _ = service._get_conn()  # ensure schema
            _insert_row(db, "inj-zzz-0001", "sess-tb-2", "newest", "2026-06-07T10:23:46.000000+00:00")
            _insert_row(db, "inj-aaa-0002", "sess-tb-2", "oldest", "2026-06-07T10:23:44.000000+00:00")
            _insert_row(db, "inj-bbb-0003", "sess-tb-2", "middle", "2026-06-07T10:23:45.000000+00:00")
            service._hydration_version.pop("sess-tb-2", None)
            service._ensure_loaded("sess-tb-2")

            ids = [ij.interjection_id for ij in service._queues.get("sess-tb-2", [])]
            assert ids == [
                "inj-aaa-0002",  # oldest
                "inj-bbb-0003",  # middle
                "inj-zzz-0001",  # newest
            ], f"Got {ids}, expected created_at order"
        finally:
            reset_pubsub_cache()

    def test_tie_break_within_a_shared_timestamp_group(self, tmp_path: Path) -> None:
        """Mix of unique and shared timestamps — tie-breaker applies
        only to the shared-timestamp group.
        """
        db = tmp_path / "i.db"

        reset_pubsub_cache()
        try:
            service = InterjectionService(db_path=db)
            _ = service._get_conn()  # ensure schema
            shared_ts = "2026-06-07T10:23:45.100000+00:00"
            _insert_row(db, "inj-ccc-shared", "sess-tb-3", "shared-c", shared_ts)
            _insert_row(db, "inj-aaa-shared", "sess-tb-3", "shared-a", shared_ts)
            _insert_row(db, "inj-bbb-shared", "sess-tb-3", "shared-b", shared_ts)
            _insert_row(db, "inj-zzz-newer", "sess-tb-3", "newer", "2026-06-07T10:23:46.000000+00:00")
            _insert_row(db, "inj-aaa-older", "sess-tb-3", "older", "2026-06-07T10:23:44.000000+00:00")
            service._hydration_version.pop("sess-tb-3", None)
            service._ensure_loaded("sess-tb-3")

            ids = [ij.interjection_id for ij in service._queues.get("sess-tb-3", [])]
            # Older → tie-broken [aaa, bbb, ccc] → newer
            assert ids == [
                "inj-aaa-older",
                "inj-aaa-shared",
                "inj-bbb-shared",
                "inj-ccc-shared",
                "inj-zzz-newer",
            ], f"Got {ids}"
        finally:
            reset_pubsub_cache()
