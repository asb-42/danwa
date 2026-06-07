"""MetaWorkflowService — stub for the meta-workflow reflection engine.

In this phase, generate_proposal() produces a dummy proposal with
static text.  No LLM integration yet.
"""

from __future__ import annotations

import logging

from backend.blueprints.repository import BlueprintRepository
from backend.models.artifact import DebateArtifact
from backend.models.optimization_proposal import (
    OptimizationProposal,
    ProposalCreatedBy,
    ProposalStatus,
)
from backend.repositories.proposal_repo import ProposalRepository

logger = logging.getLogger(__name__)


class MetaWorkflowService:
    """Stub for the meta-workflow reflection engine.

    Generates dummy optimization proposals.  In future phases,
    this will integrate with an LLM to analyze debate artifacts
    and propose concrete workflow improvements.
    """

    def __init__(
        self,
        blueprint_repo: BlueprintRepository,
        proposal_repo: ProposalRepository,
    ) -> None:
        """Initialise MetaWorkflowService."""
        self._blueprint_repo = blueprint_repo
        self._proposal_repo = proposal_repo

    async def generate_proposal(
        self,
        target_workflow_id: str,
        artifact: DebateArtifact | None = None,
    ) -> OptimizationProposal:
        """Generate an optimization proposal for a workflow.

        Args:
            target_workflow_id: The workflow to optimize.
            artifact: Optional debate artifact to analyze.

        Returns:
            A dummy ``OptimizationProposal``.

        Raises:
            ValueError: If the workflow does not exist or is locked.
        """
        # Validate workflow exists
        workflow = self._blueprint_repo.get_workflow_definition(target_workflow_id)
        if workflow is None:
            raise ValueError(f"Workflow {target_workflow_id!r} not found")

        if workflow.is_locked:
            raise ValueError(f"Workflow {target_workflow_id!r} is locked and cannot be reflected upon")

        # Build source session reference
        source_session_id = artifact.session_id if artifact else None

        # Create dummy proposal
        proposal = OptimizationProposal(
            target_workflow_id=target_workflow_id,
            source_session_id=source_session_id,
            proposed_nodes=[],
            proposed_edges=[],
            rationale=(
                "Dies ist ein Platzhalter für die Meta-Agent-Analyse. "
                "In einer zukünftigen Phase wird dieser Service eine LLM-gestützte "
                "Analyse des DebateArtifact durchführen und konkrete "
                "Workflow-Verbesserungen vorschlagen."
            ),
            risk_assessment="Gering — keine Änderungen vorgeschlagen (Stub).",
            estimated_impact="N/A — Platzhalter-Proposal.",
            status=ProposalStatus.PENDING,
            created_by=ProposalCreatedBy.META_AGENT,
            parent_version_id=target_workflow_id,
        )

        self._proposal_repo.save(proposal)
        logger.info("Dummy proposal %s generated for workflow %s", proposal.id, target_workflow_id)
        return proposal
