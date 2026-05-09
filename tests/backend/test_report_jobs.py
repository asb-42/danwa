"""Tests for Phase 7 Group D — Report Jobs."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from backend.workflow.report_jobs import ReportJobStore


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database with the report_jobs table."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS report_jobs (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            format TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            file_path TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def store(tmp_db: Path) -> ReportJobStore:
    return ReportJobStore(tmp_db)


class TestCreateJob:
    def test_returns_job_id(self, store: ReportJobStore):
        job_id = store.create_job("sess-1", "docx")
        assert isinstance(job_id, str)
        assert len(job_id) > 0

    def test_job_is_pending(self, store: ReportJobStore, tmp_db: Path):
        job_id = store.create_job("sess-1", "pdf")
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM report_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row["status"] == "pending"
        assert row["format"] == "pdf"
        assert row["session_id"] == "sess-1"
        assert row["created_at"] is not None


class TestUpdateJob:
    def test_update_status(self, store: ReportJobStore, tmp_db: Path):
        job_id = store.create_job("sess-1", "docx")
        store.update_job(job_id, status="running")
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM report_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        assert row["status"] == "running"

    def test_update_completed(self, store: ReportJobStore, tmp_db: Path):
        job_id = store.create_job("sess-1", "docx")
        store.update_job(job_id, status="completed", file_path="/tmp/report.docx")
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM report_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        assert row["status"] == "completed"
        assert row["file_path"] == "/tmp/report.docx"
        assert row["completed_at"] is not None

    def test_update_failed(self, store: ReportJobStore, tmp_db: Path):
        job_id = store.create_job("sess-1", "pdf")
        store.update_job(job_id, status="failed", error="Generation failed")
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM report_jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()
        assert row["status"] == "failed"
        assert row["error"] == "Generation failed"
        assert row["completed_at"] is not None


class TestGetJob:
    def test_returns_job(self, store: ReportJobStore):
        job_id = store.create_job("sess-1", "docx")
        job = store.get_job(job_id)
        assert job is not None
        assert job["id"] == job_id
        assert job["session_id"] == "sess-1"
        assert job["format"] == "docx"

    def test_nonexistent_returns_none(self, store: ReportJobStore):
        assert store.get_job("nonexistent") is None


class TestListJobs:
    def test_list_all(self, store: ReportJobStore):
        store.create_job("sess-1", "docx")
        store.create_job("sess-2", "pdf")
        jobs = store.list_jobs()
        assert len(jobs) == 2

    def test_filter_by_session(self, store: ReportJobStore):
        store.create_job("sess-1", "docx")
        store.create_job("sess-1", "pdf")
        store.create_job("sess-2", "docx")
        jobs = store.list_jobs(session_id="sess-1")
        assert len(jobs) == 2

    def test_ordered_by_created_desc(self, store: ReportJobStore):
        store.create_job("sess-1", "docx")
        store.create_job("sess-2", "pdf")
        jobs = store.list_jobs()
        assert jobs[0]["created_at"] >= jobs[1]["created_at"]
