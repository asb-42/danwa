"""Tests for Phase 7 Group C — Immutability & Soft Delete."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.workflow.immutability import (
    archive_session,
    guard_locked,
    guard_mutable,
    guard_not_archived,
    lock_session,
    restore_session,
)


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database with workflow_sessions table."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_sessions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            is_locked INTEGER NOT NULL DEFAULT 0,
            is_archived INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS state_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_type TEXT NOT NULL DEFAULT '',
            round_number INTEGER NOT NULL DEFAULT 0,
            state_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            is_locked INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
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
            llm_profile_id TEXT NOT NULL DEFAULT '',
            latency_ms INTEGER NOT NULL DEFAULT 0,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0
        )
    """)
    # Insert a test session
    conn.execute(
        "INSERT INTO workflow_sessions (id, workflow_id, status) VALUES (?, ?, ?)",
        ("sess-1", "wf-1", "completed"),
    )
    conn.execute(
        "INSERT INTO state_snapshots (session_id, workflow_id, node_id, state_json, created_at) VALUES (?, ?, ?, ?, ?)",
        ("sess-1", "wf-1", "n1", "{}", "2024-01-01T00:00:00"),
    )
    conn.commit()
    conn.close()
    return db


class TestLockSession:
    def test_locks_session(self, tmp_db: Path):
        lock_session("sess-1", tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT is_locked FROM workflow_sessions WHERE id = 'sess-1'").fetchone()
        conn.close()
        assert row["is_locked"] == 1

    def test_locks_snapshots(self, tmp_db: Path):
        lock_session("sess-1", tmp_db)
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT is_locked FROM state_snapshots WHERE session_id = 'sess-1'").fetchone()
        conn.close()
        assert row["is_locked"] == 1

    def test_lock_nonexistent_session(self, tmp_db: Path):
        # Should not raise
        lock_session("nonexistent", tmp_db)


class TestArchiveSession:
    def test_archives_session(self, tmp_db: Path):
        result = archive_session("sess-1", tmp_db)
        assert result is True
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT is_archived FROM workflow_sessions WHERE id = 'sess-1'").fetchone()
        conn.close()
        assert row["is_archived"] == 1

    def test_archive_nonexistent(self, tmp_db: Path):
        result = archive_session("nonexistent", tmp_db)
        assert result is False


class TestRestoreSession:
    def test_restores_session(self, tmp_db: Path):
        archive_session("sess-1", tmp_db)
        result = restore_session("sess-1", tmp_db)
        assert result is True
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT is_archived FROM workflow_sessions WHERE id = 'sess-1'").fetchone()
        conn.close()
        assert row["is_archived"] == 0

    def test_restore_nonexistent(self, tmp_db: Path):
        result = restore_session("nonexistent", tmp_db)
        assert result is False


class TestGuardLocked:
    def test_passes_for_unlocked(self, tmp_db: Path):
        guard_locked("sess-1", tmp_db)  # should not raise

    def test_raises_403_for_locked(self, tmp_db: Path):
        lock_session("sess-1", tmp_db)
        with pytest.raises(Exception) as exc_info:
            guard_locked("sess-1", tmp_db)
        assert exc_info.value.status_code == 403

    def test_passes_for_nonexistent(self, tmp_db: Path):
        guard_locked("nonexistent", tmp_db)  # should not raise (graceful)


class TestGuardNotArchived:
    def test_passes_for_not_archived(self, tmp_db: Path):
        guard_not_archived("sess-1", tmp_db)  # should not raise

    def test_raises_404_for_archived(self, tmp_db: Path):
        archive_session("sess-1", tmp_db)
        with pytest.raises(Exception) as exc_info:
            guard_not_archived("sess-1", tmp_db)
        assert exc_info.value.status_code == 404

    def test_passes_for_nonexistent(self, tmp_db: Path):
        guard_not_archived("nonexistent", tmp_db)  # should not raise (graceful)


class TestGuardMutable:
    def test_passes_for_mutable(self, tmp_db: Path):
        guard_mutable("sess-1", tmp_db)  # should not raise

    def test_raises_for_locked(self, tmp_db: Path):
        lock_session("sess-1", tmp_db)
        with pytest.raises(Exception):
            guard_mutable("sess-1", tmp_db)

    def test_raises_for_archived(self, tmp_db: Path):
        archive_session("sess-1", tmp_db)
        with pytest.raises(Exception):
            guard_mutable("sess-1", tmp_db)
