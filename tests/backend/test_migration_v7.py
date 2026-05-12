"""Tests for Phase 8 Group A — Migration v7."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.blueprints.migrations import SCHEMA_VERSION, run_migrations


class TestMigrationV7:
    def test_schema_version_is_7(self):
        assert SCHEMA_VERSION >= 7

    def test_migration_applies_cleanly(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert ver >= 7

    def test_new_columns_added(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(blueprint_llm_profiles)").fetchall()]
        conn.close()
        for col in [
            "protocol",
            "a2a_endpoint",
            "a2a_timeout",
            "fallback_llm_profile_id",
            "a2a_config_json",
        ]:
            assert col in cols, f"Missing column: {col}"

    def test_default_values(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        conn.row_factory = sqlite3.Row
        # Insert a profile without specifying new columns
        conn.execute(
            "INSERT INTO blueprint_llm_profiles (id, name, provider, model, description, tags_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("test-1", "Test", "openrouter", "gpt-4", "", "[]", "2024-01-01", "2024-01-01"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM blueprint_llm_profiles WHERE id = 'test-1'").fetchone()
        conn.close()
        assert row["protocol"] == "litellm"
        assert row["a2a_endpoint"] is None
        assert row["a2a_timeout"] == 120
        assert row["fallback_llm_profile_id"] is None
        assert row["a2a_config_json"] == "{}"

    def test_migration_is_idempotent(self, tmp_path: Path):
        db = tmp_path / "test.db"
        run_migrations(db)
        run_migrations(db)
        conn = sqlite3.connect(str(db))
        ver = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert ver >= 9
