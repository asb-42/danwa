"""Optimization Proposals — API router for workflow reflection.

Endpoints:
- POST /api/v1/workflows/{id}/reflect                  — generate proposal
- GET  /api/v1/optimization-proposals                   — list proposals
- GET  /api/v1/optimization-proposals/{id}              — get single proposal
- POST /api/v1/optimization-proposals/{id}/approve      — approve proposal
- POST /api/v1/optimization-proposals/{id}/reject       — reject proposal
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.blueprints.repository import BlueprintRepository
from backend.models.optimization_proposal import OptimizationProposal, ProposalStatus
from backend.repositories.proposal_repo import ProposalRepository
from backend.services.meta_workflow import MetaWorkflowService
from backend.workflow.audit_logger import get_audit_logger

logger = logging.getLogger(__name__)

router = APIRouter(tags=["optimization-proposals"])

_REPO: BlueprintRepository | None = None
_PROPOSAL_REPO: ProposalRepository | None = None
_META_SERVICE: MetaWorkflowService | None = None


def _get_blueprint_repo() -> BlueprintRepository:
    """Return (or lazily create) blueprint repo."""
    global _REPO
    if _REPO is None:
        _REPO = BlueprintRepository()
    return _REPO


def _get_proposal_repo() -> ProposalRepository:
    """Return (or lazily create) proposal repo."""
    global _PROPOSAL_REPO
    if _PROPOSAL_REPO is None:
        _PROPOSAL_REPO = ProposalRepository()
    return _PROPOSAL_REPO


def _get_meta_service() -> MetaWorkflowService:
    """Return (or lazily create) meta service."""
    global _META_SERVICE
    if _META_SERVICE is None:
        _META_SERVICE = MetaWorkflowService(
            blueprint_repo=_get_blueprint_repo(),
            proposal_repo=_get_proposal_repo(),
        )
    return _META_SERVICE


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ProposalResponse(BaseModel):
    """Response model for an optimization proposal."""

    id: str
    target_workflow_id: str
    source_session_id: str | None = None
    proposed_nodes: list[dict] = Field(default_factory=list)
    proposed_edges: list[dict] = Field(default_factory=list)
    rationale: str = ""
    risk_assessment: str = ""
    estimated_impact: str = ""
    status: str
    created_by: str
    approved_by: str | None = None
    approved_at: str | None = None
    parent_version_id: str = ""
    new_version_id: str | None = None
    created_at: str


class ReflectResponse(BaseModel):
    """Response after generating a proposal."""

    proposal_id: str
    target_workflow_id: str
    status: str = "pending"


class ApproveResponse(BaseModel):
    """Response after approving a proposal."""

    proposal_id: str
    new_version_id: str
    status: str = "approved"


def _proposal_to_response(p: OptimizationProposal) -> ProposalResponse:
    """Proposal to response the instance."""
    return ProposalResponse(
        id=p.id,
        target_workflow_id=p.target_workflow_id,
        source_session_id=p.source_session_id,
        proposed_nodes=p.proposed_nodes,
        proposed_edges=p.proposed_edges,
        rationale=p.rationale,
        risk_assessment=p.risk_assessment,
        estimated_impact=p.estimated_impact,
        status=p.status.value,
        created_by=p.created_by.value,
        approved_by=p.approved_by,
        approved_at=p.approved_at.isoformat() if p.approved_at else None,
        parent_version_id=p.parent_version_id,
        new_version_id=p.new_version_id,
        created_at=p.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/workflows/{workflow_id}/reflect",
    response_model=ReflectResponse,
    status_code=201,
)
async def reflect_on_workflow(workflow_id: str) -> ReflectResponse:
    """Generate an optimization proposal for a workflow."""
    meta = _get_meta_service()
    try:
        proposal = await meta.generate_proposal(workflow_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    # Audit log
    try:
        get_audit_logger().log_workflow_event(
            session_id="",
            workflow_id=workflow_id,
            workflow_version=1,
            event_type="proposal_created",
            actor="meta_agent",
            metadata={"proposal_id": proposal.id},
        )
    except Exception:
        logger.debug("Audit logging failed for proposal_created", exc_info=True)

    return ReflectResponse(
        proposal_id=proposal.id,
        target_workflow_id=proposal.target_workflow_id,
        status=proposal.status.value,
    )


@router.get(
    "/optimization-proposals",
    response_model=list[ProposalResponse],
)
async def list_proposals(
    status: str | None = None,
    workflow_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[ProposalResponse]:
    """List optimization proposals, optionally filtered."""
    repo = _get_proposal_repo()
    proposal_status = ProposalStatus(status) if status else None
    proposals = repo.list_proposals(
        status=proposal_status,
        workflow_id=workflow_id,
        limit=limit,
        offset=offset,
    )
    return [_proposal_to_response(p) for p in proposals]


@router.get(
    "/optimization-proposals/{proposal_id}",
    response_model=ProposalResponse,
)
async def get_proposal(proposal_id: str) -> ProposalResponse:
    """Get a single optimization proposal."""
    repo = _get_proposal_repo()
    proposal = repo.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")
    return _proposal_to_response(proposal)


@router.post(
    "/optimization-proposals/{proposal_id}/approve",
    response_model=ApproveResponse,
)
async def approve_proposal(proposal_id: str) -> ApproveResponse:
    """Approve a proposal — creates a new WorkflowDefinition version."""
    repo = _get_proposal_repo()
    proposal = repo.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")

    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve proposal with status={proposal.status.value}",
        )

    bp_repo = _get_blueprint_repo()

    # Get the current workflow and create a new version
    workflow = bp_repo.get_workflow_definition(proposal.target_workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow {proposal.target_workflow_id!r} not found",
        )

    # Create new workflow version
    new_workflow = workflow.model_copy()
    new_workflow.id = f"{workflow.id}-v{workflow.version + 1}"
    new_workflow.version = workflow.version + 1
    new_workflow.is_locked = False
    new_workflow.updated_at = datetime.now(UTC)

    # Apply proposed changes if any
    if proposal.proposed_nodes:
        new_workflow.nodes = proposal.proposed_nodes
    if proposal.proposed_edges:
        new_workflow.edges = proposal.proposed_edges

    bp_repo.save_workflow_definition(new_workflow)

    # Update proposal status
    repo.update_status(
        proposal_id,
        ProposalStatus.APPROVED,
        approved_by="user",  # TODO: get from auth context
        new_version_id=new_workflow.id,
    )

    # Audit log
    try:
        get_audit_logger().log_workflow_event(
            session_id="",
            workflow_id=proposal.target_workflow_id,
            workflow_version=workflow.version,
            event_type="proposal_approved",
            actor="user",
            metadata={"proposal_id": proposal_id, "new_version_id": new_workflow.id},
        )
    except Exception:
        logger.debug("Audit logging failed for proposal_approved", exc_info=True)

    return ApproveResponse(
        proposal_id=proposal_id,
        new_version_id=new_workflow.id,
        status="approved",
    )


@router.post(
    "/optimization-proposals/{proposal_id}/reject",
    status_code=200,
)
async def reject_proposal(proposal_id: str) -> dict:
    """Reject a proposal."""
    repo = _get_proposal_repo()
    proposal = repo.get(proposal_id)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f"Proposal {proposal_id!r} not found")

    if proposal.status != ProposalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject proposal with status={proposal.status.value}",
        )

    repo.update_status(proposal_id, ProposalStatus.REJECTED, approved_by="user")

    # Audit log
    try:
        get_audit_logger().log_workflow_event(
            session_id="",
            workflow_id=proposal.target_workflow_id,
            workflow_version=1,
            event_type="proposal_rejected",
            actor="user",
            metadata={"proposal_id": proposal_id},
        )
    except Exception:
        logger.debug("Audit logging failed for proposal_rejected", exc_info=True)

    return {"proposal_id": proposal_id, "status": "rejected"}
