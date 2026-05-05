"""Audit API router — query audit events for debates."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_audit_service, get_project_id
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


@router.get("/project/{project_id}")
async def get_audit_events_by_project(
    project_id: str,
    limit: int = 100,
    offset: int = 0,
    audit: AuditService = Depends(get_audit_service),
) -> list[dict]:
    """Return audit events for a project, ordered by timestamp desc."""
    return audit.get_events_by_project(project_id, limit=limit, offset=offset)
