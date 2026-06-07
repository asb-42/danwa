"""ProposalRepository — SQLite-backed storage for OptimizationProposals.

Maps to the ``optimization_proposals`` table created in migration v11.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.models.optimization_proposal import (
    OptimizationProposal,
    ProposalCreatedBy,
    ProposalStatus,
)

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path("data/blueprints.db")


class ProposalRepository:
    """SQLite-backed storage for ``OptimizationProposal`` objects."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        """Initialise ProposalRepository."""
        self._db_path = Path(db_path) if db_path else _DEFAULT_DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        """Connect the instance."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _row_to_proposal(row: sqlite3.Row) -> OptimizationProposal:
        """Row to proposal the instance."""
        return OptimizationProposal(
            id=row["id"],
            target_workflow_id=row["target_workflow_id"],
            source_session_id=row["source_session_id"],
            proposed_nodes=json.loads(row["proposed_nodes_json"] or "[]"),
            proposed_edges=json.loads(row["proposed_edges_json"] or "[]"),
            rationale=row["rationale"] or "",
            risk_assessment=row["risk_assessment"] or "",
            estimated_impact=row["estimated_impact"] or "",
            status=ProposalStatus(row["status"]),
            created_by=ProposalCreatedBy(row["created_by"]),
            approved_by=row["approved_by"],
            approved_at=(datetime.fromisoformat(row["approved_at"]) if row["approved_at"] else None),
            parent_version_id=row["parent_version_id"] or "",
            new_version_id=row["new_version_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def save(self, proposal: OptimizationProposal) -> None:
        """Insert an optimization proposal."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO optimization_proposals
                    (id, target_workflow_id, source_session_id,
                     proposed_nodes_json, proposed_edges_json,
                     rationale, risk_assessment, estimated_impact,
                     status, created_by, approved_by, approved_at,
                     parent_version_id, new_version_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.id,
                    proposal.target_workflow_id,
                    proposal.source_session_id,
                    json.dumps(proposal.proposed_nodes),
                    json.dumps(proposal.proposed_edges),
                    proposal.rationale,
                    proposal.risk_assessment,
                    proposal.estimated_impact,
                    proposal.status.value,
                    proposal.created_by.value,
                    proposal.approved_by,
                    proposal.approved_at.isoformat() if proposal.approved_at else None,
                    proposal.parent_version_id,
                    proposal.new_version_id,
                    proposal.created_at.isoformat(),
                ),
            )
        logger.info("OptimizationProposal %s saved", proposal.id)

    def get(self, proposal_id: str) -> OptimizationProposal | None:
        """Return a proposal by ID, or None if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM optimization_proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_proposal(row)

    def list_proposals(
        self,
        status: ProposalStatus | None = None,
        workflow_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[OptimizationProposal]:
        """List proposals with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if workflow_id is not None:
            conditions.append("target_workflow_id = ?")
            params.append(workflow_id)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM optimization_proposals
                {where}
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        return [self._row_to_proposal(r) for r in rows]

    def update_status(
        self,
        proposal_id: str,
        status: ProposalStatus,
        approved_by: str | None = None,
        new_version_id: str | None = None,
    ) -> None:
        """Update the status of a proposal."""
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE optimization_proposals
                SET status = ?,
                    approved_by = COALESCE(?, approved_by),
                    approved_at = CASE
                        WHEN ? IN ('approved', 'rejected') THEN ?
                        ELSE approved_at
                    END,
                    new_version_id = COALESCE(?, new_version_id)
                WHERE id = ?
                """,
                (status.value, approved_by, status.value, now, new_version_id, proposal_id),
            )
        logger.info("OptimizationProposal %s → %s", proposal_id, status.value)
