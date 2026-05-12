"""Tests for Phase 7 Group A — Migration v6."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.blueprints.migrations import SCHEMA_VERSION, run_migrations


class TestMigrationV6:
    def test_schema_version_is_6(self):
        assert SCHEMA_VERSION >= 6

    def test_migration_applies_cleanly(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert ver >= 6

    def test_audit_log_table_created(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
        conn.close()
        expected = [
            "id",
            "session_id",
            "workflow_id",
            "workflow_version",
            "timestamp",
            "event_type",
            "node_id",
            "actor",
            "input_hash",
            "output_hash",
            "llm_profile_id",
            "latency_ms",
            "prompt_tokens",
            "completion_tokens",
        ]
        for col in expected:
            assert col in cols, f"Missing column: {col}"

    def test_report_jobs_table_created(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(report_jobs)").fetchall()]
        conn.close()
        expected = [
            "id",
            "session_id",
            "format",
            "status",
            "file_path",
            "error",
            "created_at",
            "completed_at",
        ]
        for col in expected:
            assert col in cols, f"Missing column: {col}"

    def test_workflow_sessions_has_is_locked(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(workflow_sessions)").fetchall()]
        conn.close()
        assert "is_locked" in cols
        assert "is_archived" in cols

    def test_state_snapshots_has_is_locked(self, tmp_path: Path):
        """state_snapshots is created lazily by StateSnapshotStore, not by migrations.
        The is_locked column is added via ALTER TABLE in _init_table()."""
        db = tmp_path / "test.db"
        run_migrations(db)
        # Create the table the way StateSnapshotStore does
        from backend.workflow.state_snapshot import StateSnapshotStore

        StateSnapshotStore(db)
        conn = sqlite3.connect(str(db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(state_snapshots)").fetchall()]
        conn.close()
        assert "is_locked" in cols

    def test_migration_is_idempotent(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        run_migrations(db)  # second call should not fail
        conn = sqlite3.connect(str(db))
        ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert ver >= 9

    def test_audit_log_indexes_created(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        indexes = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='audit_log'").fetchall()]
        conn.close()
        assert "idx_audit_log_session" in indexes
        assert "idx_audit_log_workflow" in indexes
        assert "idx_audit_log_event_type" in indexes
        assert "idx_audit_log_timestamp" in indexes
