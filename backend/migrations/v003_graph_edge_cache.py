"""Migration v003: Pre-computed graph edge cache.

Background
----------
Phase 4.3 / 5.2 of plans/2026-06-14_case-space-impl-todos.md asks
for a persistent cache of graph edges (Case -> Debate -> Tag,
AuditEvent -> Debate, etc.) so that the ``GET /api/v1/graph/edges``
endpoint can return real evidence ("tag added by jane on 2026-06-01")
instead of a stub string.

This migration adds a single SQLite table in the same
``audit.db`` file the AuditService uses.  The table is a
materialised view of the audit log: it is NOT updated in real
time.  Instead, ``GraphEdgeCacheService.refresh_for_tenant``
rebuilds the per-tenant rows on demand (idempotent UPSERT) and
the router caches the result for 60 seconds.

Why same database?
------------------
- One connection to manage
- Same backup story (audit.db is already in the rotation)
- The cache is logically derived from audit_events; co-locating
  keeps the relationship explicit and avoids stale-cache
  scenarios where the audit log is wiped but the cache survives

Idempotency
-----------
Safe to run on every startup.  We use ``CREATE TABLE IF NOT
EXISTS`` and only add indexes if missing.  Existing rows are
preserved; ``refresh_for_tenant`` is the only writer.

Backfill
--------
Per the user's instruction (2026-06-15), we do NOT backfill
existing tenants.  The cache is empty after this migration
runs; it fills up as new audit events are recorded and
``refresh_for_tenant`` is called on demand.  Tenants that
stop using the product for >90 days will not get their older
edges cached — the design choice is "live working set only".
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Default DB path mirrors AuditService default.
# Import is deferred to avoid a circular dependency at module
# import time (migrations are imported very early in main.py).
_DEFAULT_DB_PATH = Path("data/audit.db")


def migrate_graph_edge_cache(db_path: Path | None = None) -> None:
    """Create the graph_edge_cache table and its indexes.

    Idempotent — safe to call on every backend startup.
    """
    target = db_path or _DEFAULT_DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Running v003 graph_edge_cache migration on %s", target)

    with sqlite3.connect(str(target)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS graph_edge_cache (
                tenant_id     TEXT NOT NULL,
                src_type      TEXT NOT NULL,
                src_id        TEXT NOT NULL,
                tgt_type      TEXT NOT NULL,
                tgt_id        TEXT NOT NULL,
                type          TEXT NOT NULL,
                weight        REAL NOT NULL DEFAULT 1.0,
                evidence_count INTEGER NOT NULL DEFAULT 0,
                first_seen    TEXT NOT NULL,
                last_seen     TEXT NOT NULL,
                -- Sample evidence (most recent up to 5) for fast display.
                -- Full evidence is reconstructed on demand by the service.
                sample_evidence TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (tenant_id, src_type, src_id, tgt_type, tgt_id, type)
            )
        """)
        # Index for "give me all edges out of this entity" queries
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gec_src
            ON graph_edge_cache (tenant_id, src_type, src_id)
        """)
        # Index for "give me all edges into this entity"
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gec_tgt
            ON graph_edge_cache (tenant_id, tgt_type, tgt_id)
        """)
        # Index for the router's "edges from this source to this target"
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_gec_pair
            ON graph_edge_cache (tenant_id, src_type, src_id, tgt_type, tgt_id)
        """)
        conn.commit()
    logger.info("v003 graph_edge_cache migration complete")
