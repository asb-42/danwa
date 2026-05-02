"""Audit API router — query audit events for debates."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_audit_service
from backend.persistence.audit import AuditService

router = APIRouter()


@router.get("/{debate_id}")
async def get_audit_events(
    debate_id: str,
    audit: AuditService = Depends(get_audit_service),
) -> list[dict]:
    """Return all audit events for a debate, ordered by round."""
    events = audit.get_events(debate_id)
    if not events:
        # Return empty list — not a 404, since "no events yet" is valid
        return []
    return events
