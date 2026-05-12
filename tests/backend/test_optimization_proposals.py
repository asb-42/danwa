"""Tests for OptimizationProposal, ProposalRepository, and MetaWorkflowService."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.blueprints.repository import BlueprintRepository
from backend.models.optimization_proposal import (
    OptimizationProposal,
    ProposalCreatedBy,
    ProposalStatus,
)
from backend.repositories.proposal_repo import ProposalRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def proposal_repo(db_path: Path) -> ProposalRepository:
    # Run migrations to create tables
    from backend.blueprints.migrations import run_migrations

    run_migrations(db_path)
    return ProposalRepository(db_path)


@pytest.fixture
def blueprint_repo(db_path: Path) -> BlueprintRepository:
    return BlueprintRepository(db_path)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOptimizationProposal:
    def test_defaults(self) -> None:
        p = OptimizationProposal(target_workflow_id="wf1")
        assert p.status == ProposalStatus.PENDING
        assert p.created_by == ProposalCreatedBy.META_AGENT
        assert p.proposed_nodes == []
        assert p.id  # auto-generated

    def test_full_model(self) -> None:
        p = OptimizationProposal(
            id="prop-1",
            target_workflow_id="wf1",
            source_session_id="s1",
            rationale="Improve performance",
            risk_assessment="Low",
            estimated_impact="High",
            status=ProposalStatus.APPROVED,
            created_by=ProposalCreatedBy.USER,
            approved_by="admin",
            parent_version_id="wf1",
            new_version_id="wf1-v2",
        )
        assert p.status == ProposalStatus.APPROVED
        assert p.new_version_id == "wf1-v2"


class TestProposalRepository:
    def test_save_and_get(self, proposal_repo: ProposalRepository) -> None:
        p = OptimizationProposal(id="p1", target_workflow_id="wf1")
        proposal_repo.save(p)
        loaded = proposal_repo.get("p1")
        assert loaded is not None
        assert loaded.target_workflow_id == "wf1"
        assert loaded.status == ProposalStatus.PENDING

    def test_get_nonexistent(self, proposal_repo: ProposalRepository) -> None:
        assert proposal_repo.get("nonexistent") is None

    def test_list_all(self, proposal_repo: ProposalRepository) -> None:
        for i in range(3):
            proposal_repo.save(OptimizationProposal(id=f"p{i}", target_workflow_id="wf1"))
        proposals = proposal_repo.list_proposals()
        assert len(proposals) == 3

    def test_list_filter_status(self, proposal_repo: ProposalRepository) -> None:
        proposal_repo.save(
            OptimizationProposal(
                id="p1",
                target_workflow_id="wf1",
                status=ProposalStatus.PENDING,
            )
        )
        proposal_repo.save(
            OptimizationProposal(
                id="p2",
                target_workflow_id="wf1",
                status=ProposalStatus.REJECTED,
            )
        )
        pending = proposal_repo.list_proposals(
            status=ProposalStatus.PENDING,
        )
        assert len(pending) == 1
        assert pending[0].id == "p1"

    def test_update_status_approved(self, proposal_repo: ProposalRepository) -> None:
        proposal_repo.save(OptimizationProposal(id="p1", target_workflow_id="wf1"))
        proposal_repo.update_status(
            "p1",
            ProposalStatus.APPROVED,
            approved_by="admin",
            new_version_id="wf1-v2",
        )
        loaded = proposal_repo.get("p1")
        assert loaded is not None
        assert loaded.status == ProposalStatus.APPROVED
        assert loaded.approved_by == "admin"
        assert loaded.new_version_id == "wf1-v2"
        assert loaded.approved_at is not None

    def test_update_status_rejected(self, proposal_repo: ProposalRepository) -> None:
        proposal_repo.save(OptimizationProposal(id="p1", target_workflow_id="wf1"))
        proposal_repo.update_status("p1", ProposalStatus.REJECTED)
        loaded = proposal_repo.get("p1")
        assert loaded is not None
        assert loaded.status == ProposalStatus.REJECTED
