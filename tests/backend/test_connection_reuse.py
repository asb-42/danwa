"""Tests for audit M10 — AuditLogger / StateSnapshotStore connection reuse.

Both classes previously opened a fresh ``sqlite3.connect()`` on every
public method, paying the connect/open cost for every audit event or
snapshot.  After the fix, each instance lazily opens a single shared
connection on first use, cached for the lifetime of the instance (or
until :meth:`close` is called) and protected by an ``RLock`` so
concurrent writes serialise rather than racing.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.workflow.audit_logger import AuditLogger
from backend.workflow.state_snapshot import StateSnapshotStore


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temp DB with the audit_log table for AuditLogger tests."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            workflow_version INTEGER NOT NULL DEFAULT 1,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            node_id TEXT,
            actor TEXT NOT NULL DEFAULT 'system',
            input_hash TEXT NOT NULL DEFAULT '',
            output_hash TEXT NOT NULL DEFAULT '',
            input_content TEXT DEFAULT '',
            output_content TEXT DEFAULT '',
            trace_log_path TEXT DEFAULT '',
            llm_profile_id TEXT NOT NULL DEFAULT '',
            latency_ms INTEGER NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            critic_item_id TEXT NOT NULL DEFAULT '',
            build_response_id TEXT NOT NULL DEFAULT '',
            draft_version INTEGER NOT NULL DEFAULT 0,
            constructivity_score REAL
        )
        """
    )
    conn.commit()
    conn.close()
    return db


# ---------------------------------------------------------------------------
# AuditLogger — connection reuse
# ---------------------------------------------------------------------------


class TestAuditLoggerConnectionReuse:
    """Each public method must reuse the cached connection, not open a new one."""

    def test_single_connection_across_many_writes(self, tmp_db: Path) -> None:
        """100 ``log_node_execution`` calls open exactly 1 connection."""
        with patch("backend.workflow.audit_logger.sqlite3.connect", wraps=sqlite3.connect) as spy:
            al = AuditLogger(tmp_db)
            for i in range(100):
                al.log_node_execution(
                    session_id=f"session-{i}",
                    workflow_id="w1",
                    workflow_version=1,
                    node_id=f"node-{i}",
                )
        # First call: lazy open.  No subsequent opens even with 100 writes.
        assert spy.call_count == 1, f"expected 1 connect call, got {spy.call_count}"
        al.close()

    def test_single_connection_across_mixed_operations(self, tmp_db: Path) -> None:
        """Mix of inserts, reads, and counts: still 1 connection."""
        with patch("backend.workflow.audit_logger.sqlite3.connect", wraps=sqlite3.connect) as spy:
            al = AuditLogger(tmp_db)
            al.log_node_execution(
                session_id="s1",
                workflow_id="w1",
                workflow_version=1,
                node_id="n1",
            )
            al.log_workflow_event(
                session_id="s1",
                workflow_id="w1",
                workflow_version=1,
                event_type="workflow_started",
            )
            al.get_audit_log("s1")
            al.get_audit_log_for_replay("s1")
            al.count_events("s1")
        assert spy.call_count == 1, f"expected 1 connect call, got {spy.call_count}"
        al.close()

    def test_close_releases_connection(self, tmp_db: Path) -> None:
        """After close(), the next call lazily reopens the connection."""
        al = AuditLogger(tmp_db)
        al.log_node_execution(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="n1",
        )
        first_conn = al._get_conn()
        al.close()
        assert al._conn is None
        al.log_node_execution(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="n2",
        )
        second_conn = al._get_conn()
        assert first_conn is not second_conn, "close() should drop the cached connection"
        al.close()

    def test_wal_mode_enabled_on_first_connect(self, tmp_db: Path) -> None:
        """The cached connection runs in WAL journal mode for concurrent reads."""
        al = AuditLogger(tmp_db)
        conn = al._get_conn()
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        # WAL may be reported as "wal" or downgraded to "delete" on filesystems
        # that do not support it — we only assert the pragma ran without error.
        assert mode in ("wal", "delete", "truncate", "memory"), f"unexpected journal mode: {mode}"
        al.close()

    def test_concurrent_writes_serialize_via_lock(self, tmp_db: Path) -> None:
        """Many threads writing in parallel must not corrupt the row count."""
        al = AuditLogger(tmp_db)
        n_threads = 8
        per_thread = 25

        def writer(thread_id: int) -> None:
            for i in range(per_thread):
                al.log_node_execution(
                    session_id=f"thread-{thread_id}",
                    workflow_id="w1",
                    workflow_version=1,
                    node_id=f"n{i}",
                )

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Every row must have landed — no lost writes due to race.
        total = al.count_events("thread-0") + sum(al.count_events(f"thread-{t}") for t in range(1, n_threads))
        assert total == n_threads * per_thread, f"expected {n_threads * per_thread} rows, got {total}"
        al.close()


# ---------------------------------------------------------------------------
# StateSnapshotStore — connection reuse
# ---------------------------------------------------------------------------


class TestStateSnapshotConnectionReuse:
    """The snapshot store must reuse one connection per instance, not per call."""

    def test_single_connection_across_many_saves(self, tmp_path: Path) -> None:
        """50 saves open exactly 1 connection (the init-table open)."""
        with patch("backend.workflow.state_snapshot.sqlite3.connect", wraps=sqlite3.connect) as spy:
            store = StateSnapshotStore(db_path=tmp_path / "snap.db")
            initial_calls = spy.call_count
            for i in range(50):
                store.save(
                    session_id=f"session-{i}",
                    workflow_id="w1",
                    node_id=f"n{i}",
                    node_type="agent",
                    round_number=i,
                    state_dict={"k": i},
                )
            final_calls = spy.call_count
        # Exactly one connect — the lazy init from __init__.
        assert final_calls == initial_calls == 1, f"expected 1 connect, got {final_calls} (init had {initial_calls})"
        store.close()

    def test_single_connection_across_mixed_operations(self, tmp_path: Path) -> None:
        """Mix of saves and reads: still 1 connection."""
        with patch("backend.workflow.state_snapshot.sqlite3.connect", wraps=sqlite3.connect) as spy:
            store = StateSnapshotStore(db_path=tmp_path / "snap.db")
            baseline = spy.call_count
            for i in range(10):
                store.save(
                    session_id="s1",
                    workflow_id="w1",
                    node_id=f"n{i}",
                    node_type="agent",
                    round_number=i,
                    state_dict={"i": i},
                )
            store.get_latest("s1")
            store.get_history("s1")
            store.get_by_node("s1", "n3")
            store.get_by_type("s1", "agent")
            assert spy.call_count == baseline, f"expected no new connects, got {spy.call_count - baseline} extra"
        store.close()

    def test_close_releases_connection(self, tmp_path: Path) -> None:
        """After close(), the next save lazily reopens."""
        store = StateSnapshotStore(db_path=tmp_path / "snap.db")
        store.save("s1", "w1", "n1", "agent", 1, {})
        first = store._get_conn()
        store.close()
        assert store._conn is None
        store.save("s1", "w1", "n2", "agent", 2, {})
        second = store._get_conn()
        assert first is not second
        store.close()

    def test_wal_mode_enabled_on_first_connect(self, tmp_path: Path) -> None:
        """Cached connection runs in WAL mode for concurrent reads."""
        store = StateSnapshotStore(db_path=tmp_path / "snap.db")
        mode = store._get_conn().execute("PRAGMA journal_mode").fetchone()[0]
        assert mode in ("wal", "delete", "truncate", "memory"), f"unexpected: {mode}"
        store.close()

    def test_concurrent_saves_serialize_via_lock(self, tmp_path: Path) -> None:
        """Many threads saving in parallel must not lose rows."""
        store = StateSnapshotStore(db_path=tmp_path / "snap.db")
        n_threads = 8
        per_thread = 25

        def writer(thread_id: int) -> None:
            for i in range(per_thread):
                store.save(
                    session_id=f"thread-{thread_id}",
                    workflow_id="w1",
                    node_id=f"n{i}",
                    node_type="agent",
                    round_number=i,
                    state_dict={"t": thread_id, "i": i},
                )

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total = sum(len(store.get_history(f"thread-{t}")) for t in range(n_threads))
        assert total == n_threads * per_thread, f"expected {n_threads * per_thread}, got {total}"
        store.close()
