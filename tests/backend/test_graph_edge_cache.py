"""Tests for the GraphEdgeCacheService (Phase 4.3/5.2).

The service materialises graph edges from the audit_events table.
We test the data path with a real in-memory SQLite database
(populated by hand) plus the v003 migration, and we test the
edge-evidence format the router exposes to the frontend.

Backend tests run against an isolated audit.db created in a
tmp_path fixture; we never touch the production DB.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.migrations.v003_graph_edge_cache import migrate_graph_edge_cache
from backend.services.graph_edge_cache import (
    REFRESH_AFTER_SECONDS,
    GraphEdgeCacheService,
)

# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def audit_db(tmp_path: Path) -> Path:
    """A fresh audit.db with both the audit_events and
    graph_edge_cache tables created."""
    db = tmp_path / "audit.db"
    # audit_events is created by AuditService; reproduce its schema
    # (minus the parts the service does not need) so the service
    # queries are valid.
    with sqlite3.connect(str(db)) as conn:
        conn.execute("""
            CREATE TABLE audit_events (
                id              TEXT PRIMARY KEY,
                debate_id       TEXT NOT NULL,
                project_id      TEXT NOT NULL DEFAULT '_default',
                round           INTEGER NOT NULL DEFAULT 0,
                agent           TEXT NOT NULL DEFAULT '',
                action          TEXT NOT NULL DEFAULT '',
                timestamp       TEXT NOT NULL,
                input_hash      TEXT NOT NULL DEFAULT '',
                output_hash     TEXT NOT NULL DEFAULT '',
                llm_model       TEXT NOT NULL DEFAULT 'dummy',
                tokens_used     INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
    # Run the v003 migration to add the graph_edge_cache table
    migrate_graph_edge_cache(db_path=db)
    return db


def _insert_audit(
    db: Path,
    *,
    id: str,
    project_id: str,
    debate_id: str,
    agent: str,
    action: str,
    ts: str,
) -> None:
    with sqlite3.connect(str(db)) as conn:
        conn.execute(
            """
            INSERT INTO audit_events
                (id, project_id, debate_id, agent, action, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (id, project_id, debate_id, agent, action, ts),
        )
        conn.commit()


def _recent_iso(days_ago: int = 1) -> str:
    """Return an ISO-8601 timestamp ``days_ago`` days before now."""
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


# ─── Tests ──────────────────────────────────────────────────────────────


def test_migration_creates_table_and_indexes(audit_db: Path) -> None:
    """The v003 migration is idempotent and creates 3 indexes."""
    with sqlite3.connect(str(audit_db)) as conn:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "graph_edge_cache" in tables
        idx = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='graph_edge_cache'").fetchall()]
        assert "idx_gec_src" in idx
        assert "idx_gec_tgt" in idx
        assert "idx_gec_pair" in idx

    # Running the migration a second time is a no-op
    migrate_graph_edge_cache(db_path=audit_db)
    # Table still exists, no errors
    with sqlite3.connect(str(audit_db)) as conn:
        conn.execute("SELECT COUNT(*) FROM graph_edge_cache").fetchone()


def test_refresh_aggregates_audit_events_into_edges(audit_db: Path) -> None:
    """A tenant with N audit events gets the right number of
    distinct edge rows after refresh."""
    tid = "tenant-1"
    for i in range(3):
        _insert_audit(
            audit_db,
            id=f"e{i}",
            project_id=tid,
            debate_id=f"d{i}",
            agent="strategist",
            action="node_started",
            ts=_recent_iso(),
        )

    svc = GraphEdgeCacheService(db_path=audit_db)
    touched = svc.refresh_for_tenant(tid)
    # 3 debates -> 3 AuditEvent->Debate "emitted_by" rows
    # 1 unique (agent, debate) per debate -> 3 User->AuditEvent rows
    assert touched == 6

    with sqlite3.connect(str(audit_db)) as conn:
        edges = conn.execute(
            "SELECT src_type, tgt_type, type, evidence_count FROM graph_edge_cache WHERE tenant_id = ?",
            (tid,),
        ).fetchall()
    assert len(edges) == 6
    types = {(e[0], e[1], e[2]) for e in edges}
    assert ("AuditEvent", "Debate", "emitted_by") in types
    assert ("User", "AuditEvent", "performed") in types


def test_refresh_is_idempotent(audit_db: Path) -> None:
    """Two refreshes in a row produce the same row count."""
    tid = "tenant-1"
    _insert_audit(
        audit_db,
        id="e1",
        project_id=tid,
        debate_id="d1",
        agent="strategist",
        action="node_started",
        ts=_recent_iso(),
    )
    svc = GraphEdgeCacheService(db_path=audit_db)
    svc.refresh_for_tenant(tid)
    first_count = _count_rows(audit_db, tid)
    svc.refresh_for_tenant(tid)
    second_count = _count_rows(audit_db, tid)
    assert first_count == second_count


def test_refresh_skips_audit_events_outside_window(audit_db: Path) -> None:
    """Audit events older than REFRESH_AUDIT_WINDOW_DAYS are not
    cached."""
    tid = "tenant-1"
    _insert_audit(
        audit_db,
        id="recent",
        project_id=tid,
        debate_id="d1",
        agent="strategist",
        action="node_started",
        ts=_recent_iso(5),
    )
    _insert_audit(
        audit_db,
        id="old",
        project_id=tid,
        debate_id="d2",
        agent="strategist",
        action="node_started",
        ts=_recent_iso(120),  # > REFRESH_AUDIT_WINDOW_DAYS=90
    )
    svc = GraphEdgeCacheService(db_path=audit_db)
    touched = svc.refresh_for_tenant(tid)
    # Only the recent debate contributes an edge
    assert touched == 2  # 1 emitted_by + 1 performed
    with sqlite3.connect(str(audit_db)) as conn:
        only_recent = conn.execute(
            "SELECT tgt_id FROM graph_edge_cache WHERE tenant_id = ? AND type = 'emitted_by'",
            (tid,),
        ).fetchone()
    assert only_recent is not None
    assert "d1" in only_recent[0]


def test_get_evidence_returns_evidence_for_cached_edge(audit_db: Path) -> None:
    """End-to-end: refresh + get_evidence returns a populated
    EdgeEvidence with a formatted sample line."""
    tid = "tenant-1"
    _insert_audit(
        audit_db,
        id="e1",
        project_id=tid,
        debate_id="d42",
        agent="strategist",
        action="node_started",
        ts=_recent_iso(2),
    )
    _insert_audit(
        audit_db,
        id="e2",
        project_id=tid,
        debate_id="d42",
        agent="critic",
        action="node_completed",
        ts=_recent_iso(1),
    )

    svc = GraphEdgeCacheService(db_path=audit_db)
    ev = svc.get_evidence(tid, "AuditEvent:audit:d42", "Debate:debate:d42")
    assert ev is not None
    assert ev.src == "AuditEvent:audit:d42"
    assert ev.tgt == "Debate:debate:d42"
    assert ev.type == "emitted_by"
    assert ev.weight == 1.0
    # evidence contains at least the two sample lines
    assert len(ev.evidence) >= 2
    assert any("strategist" in line for line in ev.evidence)
    assert any("critic" in line for line in ev.evidence)
    # Format: "action by agent on YYYY-MM-DD"
    assert all(" on " in line for line in ev.evidence)


def test_get_evidence_returns_none_for_unknown_pair(audit_db: Path) -> None:
    """No audit events, no edge: get_evidence returns None."""
    svc = GraphEdgeCacheService(db_path=audit_db)
    ev = svc.get_evidence("tenant-x", "AuditEvent:audit:nope", "Debate:debate:nope")
    assert ev is None


def test_get_evidence_persists_refresh(audit_db: Path) -> None:
    """A second get_evidence within REFRESH_AFTER_SECONDS does not
    re-scan the audit log.  We assert this by inserting a new
    audit event between the two calls and checking that the
    evidence is unchanged."""
    tid = "tenant-1"
    _insert_audit(
        audit_db,
        id="e1",
        project_id=tid,
        debate_id="d1",
        agent="strategist",
        action="node_started",
        ts=_recent_iso(1),
    )
    svc = GraphEdgeCacheService(db_path=audit_db)
    ev1 = svc.get_evidence(tid, "AuditEvent:audit:d1", "Debate:debate:d1")
    # Insert a new event AFTER the first refresh
    _insert_audit(
        audit_db,
        id="e2",
        project_id=tid,
        debate_id="d1",
        agent="critic",
        action="node_completed",
        ts=_recent_iso(0),
    )
    ev2 = svc.get_evidence(tid, "AuditEvent:audit:d1", "Debate:debate:d1")
    # Same evidence (no re-scan)
    assert ev1 is not None and ev2 is not None
    assert ev1.evidence == ev2.evidence


def test_refresh_after_seconds_constant() -> None:
    """The constant is exposed for the router; assert it is the
    value documented in the service header."""
    assert REFRESH_AFTER_SECONDS == 60


def test_get_evidence_with_invalid_inputs(audit_db: Path) -> None:
    """Empty tenant_id / src / tgt short-circuit to None."""
    svc = GraphEdgeCacheService(db_path=audit_db)
    assert svc.get_evidence("", "src", "tgt") is None
    assert svc.get_evidence("tenant", "", "tgt") is None
    assert svc.get_evidence("tenant", "src", "") is None


def test_format_evidence_line_handles_missing_fields() -> None:
    """The helper is robust to empty agent / action / timestamp."""
    line = GraphEdgeCacheService._format_evidence_line("", "", "")
    assert "unknown" in line


# ─── Helpers ────────────────────────────────────────────────────────────


def _count_rows(db: Path, tenant_id: str) -> int:
    with sqlite3.connect(str(db)) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM graph_edge_cache WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()[0]


# Suppress an unused-import warning; the json module is part of the
# service's contract and re-imported indirectly elsewhere.
_ = json
