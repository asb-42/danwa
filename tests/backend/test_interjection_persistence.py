"""Tests for the L6 fix — SQLite persistence of :class:`InterjectionService`.

The original implementation kept interjections in a process-local dict
and lost every pending user input on a server restart.  These tests
exercise the new ``db_path=`` constructor argument: every submit is
mirrored to SQLite, every drain marks rows consumed, and a fresh
service instance pointing at the same DB re-hydrates the pending queue
on first per-session access.

The tests deliberately use a ``tmp_path``-backed database — the
production singleton's ``data/blueprints.db`` is never touched here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from backend.workflow.interjection import InterjectionService

# ---------------------------------------------------------------------------
# Basic write-through
# ---------------------------------------------------------------------------


class TestPersistenceWriteThrough:
    """Verify that submit/consume/clear all touch the SQLite mirror."""

    @pytest.mark.asyncio
    async def test_submit_persists_row(self, tmp_path: Path) -> None:
        """A new submission must show up in the SQLite mirror."""
        db = tmp_path / "interjections.db"
        service = InterjectionService(db_path=db)

        iid = await service.submit("sess-1", "Hello", source="user")

        # The DB file must exist and contain exactly one pending row
        # with the same id.
        assert db.exists()
        with sqlite3.connect(str(db)) as conn:
            rows = conn.execute("SELECT interjection_id, session_id, content, source, status FROM interjections").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == iid
        assert rows[0][1] == "sess-1"
        assert rows[0][2] == "Hello"
        assert rows[0][3] == "user"
        assert rows[0][4] == "pending"

    @pytest.mark.asyncio
    async def test_submit_persists_metadata_as_json(self, tmp_path: Path) -> None:
        """Metadata must round-trip through the JSON column intact."""
        db = tmp_path / "interjections.db"
        service = InterjectionService(db_path=db)

        await service.submit("sess-1", "Data", source="api", metadata={"trace_id": "abc", "n": 7})

        with sqlite3.connect(str(db)) as conn:
            row = conn.execute("SELECT metadata FROM interjections").fetchone()
        assert row is not None
        assert json.loads(row[0]) == {"trace_id": "abc", "n": 7}

    @pytest.mark.asyncio
    async def test_consume_marks_rows_consumed_in_db(self, tmp_path: Path) -> None:
        """Draining a session must flip the corresponding rows to 'consumed'."""
        db = tmp_path / "interjections.db"
        service = InterjectionService(db_path=db)

        await service.submit("sess-1", "First", source="user")
        await service.submit("sess-1", "Second", source="api")

        await service.consume("sess-1")

        with sqlite3.connect(str(db)) as conn:
            statuses = [r[0] for r in conn.execute("SELECT status FROM interjections").fetchall()]
        assert statuses == ["consumed", "consumed"]

    @pytest.mark.asyncio
    async def test_consumed_rows_have_consumed_at(self, tmp_path: Path) -> None:
        """The ``consumed_at`` timestamp must be populated on drain."""
        db = tmp_path / "interjections.db"
        service = InterjectionService(db_path=db)

        await service.submit("sess-1", "Hello")
        await service.consume("sess-1")

        with sqlite3.connect(str(db)) as conn:
            row = conn.execute("SELECT status, consumed_at FROM interjections").fetchone()
        assert row[0] == "consumed"
        assert row[1] is not None
        # ISO 8601 timestamp (the service uses ``datetime.now(UTC).isoformat()``).
        assert "T" in row[1]

    @pytest.mark.asyncio
    async def test_clear_removes_rows_from_db(self, tmp_path: Path) -> None:
        """``clear()`` must DELETE the rows so they do not resurrect on restart."""
        db = tmp_path / "interjections.db"
        service = InterjectionService(db_path=db)

        await service.submit("sess-1", "Doomed")
        await service.clear("sess-1")

        with sqlite3.connect(str(db)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM interjections").fetchone()[0]
        assert count == 0


# ---------------------------------------------------------------------------
# Restart resilience — the heart of the L6 fix
# ---------------------------------------------------------------------------


class TestPersistenceRestartResilience:
    """Verify that a fresh service instance re-hydrates pending rows."""

    @pytest.mark.asyncio
    async def test_pending_survives_service_restart(self, tmp_path: Path) -> None:
        """After a process restart the new service must find the pending
        interjection the previous process submitted.
        """
        db = tmp_path / "interjections.db"

        # "Old" process: submit, then "crash" before consuming.
        old = InterjectionService(db_path=db)
        await old.submit("sess-restart-1", "Survivor", source="user")
        del old

        # "New" process: fresh instance, same DB.
        new = InterjectionService(db_path=db)
        results = await new.consume("sess-restart-1")

        assert len(results) == 1
        assert results[0]["content"] == "Survivor"
        assert results[0]["source"] == "user"

    @pytest.mark.asyncio
    async def test_consumed_rows_do_not_resurface(self, tmp_path: Path) -> None:
        """Rows that were drained before the crash must not reappear
        in the new process — ``status='consumed'`` excludes them.
        """
        db = tmp_path / "interjections.db"

        old = InterjectionService(db_path=db)
        await old.submit("sess-restart-2", "Drained")
        await old.consume("sess-restart-2")
        del old

        new = InterjectionService(db_path=db)
        results = await new.consume("sess-restart-2")
        assert results == []

    @pytest.mark.asyncio
    async def test_clear_then_restart_yields_empty(self, tmp_path: Path) -> None:
        """A session cleared before the crash must stay empty after restart."""
        db = tmp_path / "interjections.db"

        old = InterjectionService(db_path=db)
        await old.submit("sess-restart-3", "Erased")
        await old.clear("sess-restart-3")
        del old

        new = InterjectionService(db_path=db)
        results = await new.consume("sess-restart-3")
        assert results == []

    @pytest.mark.asyncio
    async def test_multi_session_independence_after_restart(self, tmp_path: Path) -> None:
        """Two sessions queued before the crash must remain isolated after."""
        db = tmp_path / "interjections.db"

        old = InterjectionService(db_path=db)
        await old.submit("sess-A", "for A")
        await old.submit("sess-B", "for B")
        del old

        new = InterjectionService(db_path=db)
        results_a = await new.consume("sess-A")
        results_b = await new.consume("sess-B")

        assert [r["content"] for r in results_a] == ["for A"]
        assert [r["content"] for r in results_b] == ["for B"]


# ---------------------------------------------------------------------------
# Schema / connection hygiene
# ---------------------------------------------------------------------------


class TestPersistenceSchema:
    """Sanity checks on the SQLite schema and connection handling."""

    @pytest.mark.asyncio
    async def test_creates_table_on_first_use(self, tmp_path: Path) -> None:
        """The ``interjections`` table must exist after the first DB call."""
        db = tmp_path / "interjections.db"
        service = InterjectionService(db_path=db)

        await service.submit("sess-1", "init")

        with sqlite3.connect(str(db)) as conn:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "interjections" in tables

    @pytest.mark.asyncio
    async def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """A non-existent parent dir must be created, not blow up."""
        db = tmp_path / "nested" / "deeper" / "interjections.db"
        service = InterjectionService(db_path=db)

        await service.submit("sess-1", "Hello")

        assert db.exists()

    @pytest.mark.asyncio
    async def test_in_memory_mode_skips_db_entirely(self) -> None:
        """``db_path=None`` must not create any connection or file."""
        service = InterjectionService()

        # Trigger every public method to confirm nothing leaks.
        await service.submit("sess", "x")
        await service.consume("sess")
        await service.clear("sess")

        assert service._conn is None
        assert service._db_path is None
        assert service._db_lock is None


# ---------------------------------------------------------------------------
# Singleton default — the L6 fix also flips the module-level default
# ---------------------------------------------------------------------------


class TestSingletonUsesDefaultDb:
    """The module-level singleton must be configured for persistence."""

    def test_singleton_has_db_path(self) -> None:
        from backend.workflow.interjection import (
            _DEFAULT_DB_PATH,
            interjection_service,
        )

        assert interjection_service._db_path == _DEFAULT_DB_PATH
        assert interjection_service._db_path is not None

    def test_default_db_path_points_at_blueprints_db(self) -> None:
        """Default path is the shared ``data/blueprints.db`` (same as
        audit_logger / state_snapshot) so the application only manages
        one DB file for workflow state.
        """
        from backend.workflow.interjection import _DEFAULT_DB_PATH

        assert _DEFAULT_DB_PATH == Path("data/blueprints.db")
