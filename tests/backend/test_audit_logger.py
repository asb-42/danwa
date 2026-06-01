"""Tests for Phase 7 Group B — AuditLogger service.

Updated Sprint 3: Tests include input_content / output_content columns.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from backend.workflow.audit_logger import AuditLogger


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary database with the audit_log table (v23 schema)."""
    db = tmp_path / "test.db"
    conn = sqlite3.connect(str(db))
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
    """)
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def audit(tmp_db: Path) -> AuditLogger:
    return AuditLogger(tmp_db)


class TestComputeHash:
    def test_consistent_hash(self, audit: AuditLogger):
        data = {"key": "value", "num": 42}
        h1 = audit._compute_hash(data)
        h2 = audit._compute_hash(data)
        assert h1 == h2

    def test_sha256_format(self, audit: AuditLogger):
        h = audit._compute_hash("hello")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_none_returns_empty(self, audit: AuditLogger):
        assert audit._compute_hash(None) == ""

    def test_dict_hash_matches_manual(self, audit: AuditLogger):
        data = {"a": 1}
        expected = hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        assert audit._compute_hash(data) == expected

    def test_sanitize_content_str(self, audit: AuditLogger):
        result = audit._sanitize_content("hello world")
        assert result == "hello world"

    def test_sanitize_content_dict(self, audit: AuditLogger):
        result = audit._sanitize_content({"key": "value"})
        assert "key" in result

    def test_sanitize_content_none(self, audit: AuditLogger):
        result = audit._sanitize_content(None)
        assert result == ""

    def test_sanitize_content_truncation(self, audit: AuditLogger):
        long_str = "x" * 100000
        result = audit._sanitize_content(long_str, max_len=100)
        assert len(result) == 100


class TestLogNodeExecution:
    def test_inserts_record(self, audit: AuditLogger, tmp_db: Path):
        audit.log_node_execution(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="n1",
            actor="strategist",
            input_data={"prompt": "test"},
            output_data={"content": "response"},
            llm_profile_id="profile-1",
            latency_ms=150,
            prompt_tokens=10,
            completion_tokens=20,
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE session_id = 's1'").fetchone()
        conn.close()
        assert row is not None
        assert row["event_type"] == "node_completed"
        assert row["node_id"] == "n1"
        assert row["actor"] == "strategist"
        assert row["latency_ms"] == 150
        assert row["prompt_tokens"] == 10
        assert row["completion_tokens"] == 20
        assert row["llm_profile_id"] == "profile-1"
        assert len(row["input_hash"]) == 64
        assert len(row["output_hash"]) == 64
        assert row["input_content"] is not None
        assert row["output_content"] is not None

    def test_input_output_hashes(self, audit: AuditLogger, tmp_db: Path):
        audit.log_node_execution(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="n1",
            input_data={"key": "val"},
            output_data={"result": "ok"},
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log").fetchone()
        conn.close()
        assert row["input_hash"] == audit._compute_hash({"key": "val"})
        assert row["output_hash"] == audit._compute_hash({"result": "ok"})
        assert "key" in row["input_content"]
        assert "result" in row["output_content"]

    def test_input_output_content_empty(self, audit: AuditLogger, tmp_db: Path):
        audit.log_node_execution(
            session_id="s2",
            workflow_id="w2",
            workflow_version=1,
            node_id="n2",
            actor="critic",
            input_data=None,
            output_data=None,
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE session_id = 's2'").fetchone()
        conn.close()
        assert row is not None
        assert row["input_content"] == ""
        assert row["output_content"] == ""

    def test_input_output_content_long(self, audit: AuditLogger, tmp_db: Path):
        long_text = "A" * 100000
        audit.log_node_execution(
            session_id="s3",
            workflow_id="w3",
            workflow_version=1,
            node_id="n3",
            input_data={"data": long_text},
            output_data={"result": long_text},
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE session_id = 's3'").fetchone()
        conn.close()
        assert len(row["input_content"]) <= 50000


class TestLogInterjection:
    def test_inserts_interjection_record(self, audit: AuditLogger, tmp_db: Path):
        audit.log_interjection(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="wf-inject-1",
            actor="user",
            content="Please focus on cost",
            metadata={"source": "web"},
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE event_type = 'interjection_submitted'").fetchone()
        conn.close()
        assert row is not None
        assert row["actor"] == "user"
        assert row["node_id"] == "wf-inject-1"
        assert "cost" in row["input_content"]


class TestLogWorkflowEvent:
    def test_workflow_started(self, audit: AuditLogger, tmp_db: Path):
        audit.log_workflow_event(
            session_id="s1",
            workflow_id="w1",
            workflow_version=2,
            event_type="workflow_started",
            actor="system",
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE event_type = 'workflow_started'").fetchone()
        conn.close()
        assert row is not None
        assert row["workflow_version"] == 2

    def test_workflow_completed_with_metadata(self, audit: AuditLogger, tmp_db: Path):
        audit.log_workflow_event(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            event_type="workflow_completed",
            actor="system",
            metadata={"consensus": 0.85},
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE event_type = 'workflow_completed'").fetchone()
        conn.close()
        assert row is not None
        assert len(row["output_hash"]) == 64
        assert "consensus" in row["output_content"]


class TestGetAuditLog:
    def test_filter_by_session(self, audit: AuditLogger, tmp_db: Path):
        for i in range(3):
            audit.log_node_execution(
                session_id="s1",
                workflow_id="w1",
                workflow_version=1,
                node_id=f"n{i}",
            )
        for i in range(2):
            audit.log_node_execution(
                session_id="s2",
                workflow_id="w1",
                workflow_version=1,
                node_id=f"n{i}",
            )
        results = audit.get_audit_log("s1")
        assert len(results) == 3

    def test_filter_by_event_type(self, audit: AuditLogger, tmp_db: Path):
        audit.log_node_execution(session_id="s1", workflow_id="w1", workflow_version=1, node_id="n1")
        audit.log_interjection(session_id="s1", workflow_id="w1", workflow_version=1, actor="user", content="test")
        from backend.models.schemas import AuditLogQuery

        results = audit.get_audit_log("s1", AuditLogQuery(event_type="interjection_submitted"))
        assert len(results) == 1
        assert results[0]["event_type"] == "interjection_submitted"

    def test_pagination(self, audit: AuditLogger, tmp_db: Path):
        for i in range(5):
            audit.log_node_execution(
                session_id="s1",
                workflow_id="w1",
                workflow_version=1,
                node_id=f"n{i}",
            )
        from backend.models.schemas import AuditLogQuery

        results = audit.get_audit_log("s1", AuditLogQuery(limit=2, offset=0))
        assert len(results) == 2
        results2 = audit.get_audit_log("s1", AuditLogQuery(limit=2, offset=2))
        assert len(results2) == 2


class TestGetAuditLogForReplay:
    def test_ordered_by_timestamp(self, audit: AuditLogger, tmp_db: Path):
        for i in range(5):
            audit.log_node_execution(
                session_id="s1",
                workflow_id="w1",
                workflow_version=1,
                node_id=f"n{i}",
            )
        results = audit.get_audit_log_for_replay("s1")
        assert len(results) == 5
        timestamps = [r["timestamp"] for r in results]
        assert timestamps == sorted(timestamps)

    def test_replay_contains_content(self, audit: AuditLogger, tmp_db: Path):
        audit.log_node_execution(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="n1",
            input_data={"prompt": "What is AI?"},
            output_data={"content": "AI is artificial intelligence."},
        )
        results = audit.get_audit_log_for_replay("s1")
        assert len(results) == 1
        entry = results[0]
        assert "input_content" in entry
        assert "output_content" in entry
        assert "AI" in entry["input_content"]
        assert "AI" in entry["output_content"]


class TestCountEvents:
    def test_count(self, audit: AuditLogger, tmp_db: Path):
        for i in range(3):
            audit.log_node_execution(
                session_id="s1",
                workflow_id="w1",
                workflow_version=1,
                node_id=f"n{i}",
            )
        assert audit.count_events("s1") == 3
        assert audit.count_events("nonexistent") == 0


class TestTraceLogPath:
    def test_log_with_trace_log_path(self, audit: AuditLogger, tmp_db: Path):
        audit.log_node_execution(
            session_id="s1",
            workflow_id="w1",
            workflow_version=1,
            node_id="n1",
            input_data={"prompt": "test"},
            output_data={"content": "response"},
            trace_log_path="logs/s1.jsonl",
        )
        conn = sqlite3.connect(str(tmp_db))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM audit_log WHERE session_id = 's1'").fetchone()
        conn.close()
        assert row["trace_log_path"] == "logs/s1.jsonl"
