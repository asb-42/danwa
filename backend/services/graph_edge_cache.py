"""GraphEdgeCacheService — materialised view of audit events as graph edges.

Phase 4.3 / 5.2 of plans/2026-06-14_case-space-impl-todos.md.

The case-space ``GET /api/v1/graph/edges`` endpoint used to return
a stub ``["graph_edge_cache not yet implemented (Phase 5+ plan item)"]``
string.  This service replaces the stub with real evidence strings
derived from the audit log.

Approach: "Materialized View, lazy refresh"
-------------------------------------------
We do not maintain a live in-memory or pub/sub-fed cache.  Instead:

  1. The v003 migration creates the ``graph_edge_cache`` table in
     ``audit.db`` with one row per unique (tenant, src, tgt, type)
     edge.  The table is initially empty.
  2. When the router needs evidence for an edge, it calls
     :meth:`GraphEdgeCacheService.get_evidence`.  If the row is
     absent or older than ``REFRESH_AFTER_SECONDS``, the service
     first runs :meth:`refresh_for_tenant` to repopulate from
     ``audit_events``, then returns the evidence.
  3. The in-process ``_last_refresh`` dict caches the per-tenant
     refresh timestamp so concurrent edge lookups within the same
     60 s window don't trigger duplicate refreshes.

The service is best-effort: a failure during refresh is logged
and the router falls back to a one-line placeholder string.
It is NEVER allowed to crash a graph request.

Edge types produced
-------------------
Currently we materialise three edge types from the audit log:

  - ``AuditEvent -> Debate``   type="emitted_by"
      (every audit_event for a debate points to that debate)
  - ``User -> AuditEvent``     type="performed"
      (debate-actor -> audit_event; we use the ``agent`` column)
  - ``Case -> Debate``         type="contains"
      (derived from the debate's project_id == case's id)

The router in ``graph.py`` composes its own Case->Debate and
Case->Tag edges from the case_store; this service only fills
in evidence for edges the router already knows about.

We deliberately do NOT derive Document->Document or
Document->Debate edges here.  Those are pure-RAG-embedding
edges (Phase 4+ future work, see plans §A.7) and live outside
the audit log.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.core.config import settings

logger = logging.getLogger(__name__)


# ─── Tuning constants ────────────────────────────────────────────────────

# Per-tenant refresh window: don't re-scan the audit log more than
# once per 60 s for the same tenant.  Longer than this and the
# evidence can drift from the live state; shorter wastes CPU.
REFRESH_AFTER_SECONDS = 60

# How many sample evidence entries we keep in the cache table.
SAMPLE_EVIDENCE_MAX = 5

# How many audit events to consider per tenant during refresh.
# Bounded to keep the UPSERT path linear in tenant size; older
# events are accepted as historical context and are not lost —
# they just don't get cached.
REFRESH_AUDIT_WINDOW_DAYS = 90


# ─── Result dataclass ────────────────────────────────────────────────────


@dataclass(frozen=True)
class EdgeEvidence:
    """One edge with its full evidence payload.

    Mirrors the EdgeDetail Pydantic model in models/schemas.py
    but is engine-agnostic so the service can be tested without
    importing the FastAPI layer.
    """

    src: str
    tgt: str
    type: str
    weight: float
    evidence: list[str]
    created_at: str  # ISO-8601 first-seen timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "src": self.src,
            "tgt": self.tgt,
            "type": self.type,
            "weight": self.weight,
            "evidence": list(self.evidence),
            "created_at": self.created_at,
        }


# ─── Service ────────────────────────────────────────────────────────────


class GraphEdgeCacheService:
    """Materialised edge cache, lazy-refreshing from audit_events.

    Thread-safe: the refresh is guarded by a per-process
    ``threading.Lock`` so two parallel router requests cannot
    trigger two simultaneous UPDATEs for the same tenant.
    """

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or settings.db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._refresh_lock = threading.Lock()
        # tenant_id -> last refresh datetime
        self._last_refresh: dict[str, datetime] = {}

    # ── Connection helper ───────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    # ── Public read API ─────────────────────────────────────────────

    def get_evidence(
        self,
        tenant_id: str,
        src: str,
        tgt: str,
    ) -> EdgeEvidence | None:
        """Return the cached evidence for (src, tgt) in a tenant.

        Triggers a refresh if the cache is empty or stale.  Returns
        None if the edge has no evidence (the router will then use
        a placeholder).
        """
        if not tenant_id or not src or not tgt:
            return None

        if self._is_stale(tenant_id):
            self.refresh_for_tenant(tenant_id)

        row = self._lookup(tenant_id, src, tgt)
        if row is None:
            return None
        return self._row_to_evidence(row)

    # ── Public refresh API ──────────────────────────────────────────

    def refresh_for_tenant(self, tenant_id: str) -> int:
        """Rebuild the cache for a tenant from the audit_events table.

        Idempotent: existing rows are updated, missing rows are
        inserted.  Returns the number of rows touched.
        """
        if not tenant_id:
            return 0

        with self._refresh_lock:
            cutoff = (datetime.now(UTC) - timedelta(days=REFRESH_AUDIT_WINDOW_DAYS)).isoformat()
            touched = 0
            try:
                with self._connect() as conn:
                    # ── 1. AuditEvent -> Debate ("emitted_by") ──────────
                    rows_aed = conn.execute(
                        """
                        SELECT debate_id, MIN(timestamp), MAX(timestamp), COUNT(*)
                        FROM audit_events
                        WHERE project_id = ? AND timestamp >= ?
                        GROUP BY debate_id
                        """,
                        (tenant_id, cutoff),
                    ).fetchall()
                    for debate_id, first_ts, last_ts, count in rows_aed:
                        sample = self._sample_evidence_for_debate(conn, tenant_id, debate_id, cutoff)
                        self._upsert(
                            conn,
                            tenant_id=tenant_id,
                            src_type="AuditEvent",
                            src_id=f"audit:{debate_id}",
                            tgt_type="Debate",
                            tgt_id=f"debate:{debate_id}",
                            type="emitted_by",
                            weight=1.0,
                            evidence_count=count,
                            first_seen=first_ts or "",
                            last_seen=last_ts or "",
                            sample=sample,
                        )
                        touched += 1

                    # ── 2. User -> AuditEvent ("performed") ─────────────
                    rows_perf = conn.execute(
                        """
                        SELECT agent, debate_id, MIN(timestamp), MAX(timestamp), COUNT(*)
                        FROM audit_events
                        WHERE project_id = ? AND timestamp >= ? AND agent != ''
                        GROUP BY agent, debate_id
                        """,
                        (tenant_id, cutoff),
                    ).fetchall()
                    for agent, debate_id, first_ts, last_ts, count in rows_perf:
                        # One row per (user, debate) the user acted on.
                        sample = self._sample_evidence_for_user_debate(conn, tenant_id, agent, debate_id, cutoff)
                        self._upsert(
                            conn,
                            tenant_id=tenant_id,
                            src_type="User",
                            src_id=f"user:{agent}",
                            tgt_type="AuditEvent",
                            tgt_id=f"audit:{debate_id}",
                            type="performed",
                            weight=1.0,
                            evidence_count=count,
                            first_seen=first_ts or "",
                            last_seen=last_ts or "",
                            sample=sample,
                        )
                        touched += 1

                    conn.commit()
            except sqlite3.OperationalError as exc:
                # Table doesn't exist yet (migration not run) or DB locked.
                logger.warning("graph_edge_cache refresh failed: %s", exc)
                return 0
            except Exception:  # noqa: BLE001
                logger.exception("graph_edge_cache refresh crashed")
                return 0

            self._last_refresh[tenant_id] = datetime.now(UTC)
            logger.debug(
                "graph_edge_cache: refreshed tenant=%s, touched=%d rows",
                tenant_id,
                touched,
            )
            return touched

    # ── Internal helpers ────────────────────────────────────────────

    def _is_stale(self, tenant_id: str) -> bool:
        last = self._last_refresh.get(tenant_id)
        if last is None:
            return True
        return (datetime.now(UTC) - last).total_seconds() > REFRESH_AFTER_SECONDS

    def _lookup(
        self,
        tenant_id: str,
        src: str,
        tgt: str,
    ) -> tuple | None:
        try:
            with self._connect() as conn:
                # The src/tgt columns are stored as "type:id" — split
                # the incoming strings so we can do a clean lookup
                # without parsing in SQL.
                src_type, src_id = self._split_id(src)
                tgt_type, tgt_id = self._split_id(tgt)
                return conn.execute(
                    """
                    SELECT src_type, src_id, tgt_type, tgt_id, type,
                           weight, evidence_count, first_seen, last_seen,
                           sample_evidence
                    FROM graph_edge_cache
                    WHERE tenant_id = ? AND src_type = ? AND src_id = ?
                      AND tgt_type = ? AND tgt_id = ?
                    ORDER BY type
                    LIMIT 1
                    """,
                    (tenant_id, src_type, src_id, tgt_type, tgt_id),
                ).fetchone()
        except sqlite3.OperationalError:
            return None

    def _row_to_evidence(self, row: tuple) -> EdgeEvidence:
        (src_type, src_id, tgt_type, tgt_id, type_, weight, count, first_seen, last_seen, sample_json) = row
        try:
            sample = json.loads(sample_json) if sample_json else []
        except json.JSONDecodeError:
            sample = []
        evidence = list(sample)
        # Append a summary line so the user sees the count even when
        # the sample list is empty.
        if count and not evidence:
            evidence.append(f"{count} audit events between {first_seen[:10]} and {last_seen[:10]}")
        return EdgeEvidence(
            src=f"{src_type}:{src_id}",
            tgt=f"{tgt_type}:{tgt_id}",
            type=type_,
            weight=weight,
            evidence=evidence,
            created_at=first_seen or "",
        )

    @staticmethod
    def _split_id(qualified: str) -> tuple[str, str]:
        """Split a "Type:id" string into (type, id)."""
        if ":" in qualified:
            t, _, i = qualified.partition(":")
            return t, i
        return "", qualified

    def _upsert(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        src_type: str,
        src_id: str,
        tgt_type: str,
        tgt_id: str,
        type: str,
        weight: float,
        evidence_count: int,
        first_seen: str,
        last_seen: str,
        sample: list[str],
    ) -> None:
        sample_json = json.dumps(sample[:SAMPLE_EVIDENCE_MAX], ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO graph_edge_cache
                (tenant_id, src_type, src_id, tgt_type, tgt_id, type,
                 weight, evidence_count, first_seen, last_seen, sample_evidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, src_type, src_id, tgt_type, tgt_id, type)
            DO UPDATE SET
                weight = excluded.weight,
                evidence_count = excluded.evidence_count,
                first_seen = MIN(first_seen, excluded.first_seen),
                last_seen  = MAX(last_seen,  excluded.last_seen),
                sample_evidence = excluded.sample_evidence
            """,
            (tenant_id, src_type, src_id, tgt_type, tgt_id, type, weight, evidence_count, first_seen, last_seen, sample_json),
        )

    def _sample_evidence_for_debate(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        debate_id: str,
        cutoff: str,
    ) -> list[str]:
        rows = conn.execute(
            """
            SELECT agent, action, timestamp
            FROM audit_events
            WHERE project_id = ? AND debate_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (tenant_id, debate_id, cutoff, SAMPLE_EVIDENCE_MAX),
        ).fetchall()
        return [self._format_evidence_line(agent, action, ts) for agent, action, ts in rows]

    def _sample_evidence_for_user_debate(
        self,
        conn: sqlite3.Connection,
        tenant_id: str,
        agent: str,
        debate_id: str,
        cutoff: str,
    ) -> list[str]:
        rows = conn.execute(
            """
            SELECT action, timestamp
            FROM audit_events
            WHERE project_id = ? AND agent = ? AND debate_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (tenant_id, agent, debate_id, cutoff, SAMPLE_EVIDENCE_MAX),
        ).fetchall()
        return [self._format_evidence_line(agent, action, ts) for action, ts in rows]

    @staticmethod
    def _format_evidence_line(agent: str, action: str, timestamp: str) -> str:
        when = (timestamp or "")[:10]  # YYYY-MM-DD
        return f"{action or 'event'} by {agent or 'unknown'} on {when or 'unknown date'}"


# ─── Module-level singleton ─────────────────────────────────────────────
_service: GraphEdgeCacheService | None = None


def get_graph_edge_cache_service() -> GraphEdgeCacheService:
    """Return the process-wide service instance."""
    global _service
    if _service is None:
        _service = GraphEdgeCacheService()
    return _service
