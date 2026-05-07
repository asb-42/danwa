"""Audit API router — query audit events for debates."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_audit_service, get_debate_store_for_project, get_project_id
from backend.persistence.audit import AuditService

router = APIRouter()


@router.get("/{debate_id_or_title}")
async def get_audit_events(
    debate_id_or_title: str,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> list[dict]:
    """Return all audit events for a debate, ordered by round.

    Accepts either a debate UUID or a debate title as the path parameter.
    If a title is provided, it is resolved to the matching debate ID first.
    """
    # Try direct lookup by debate_id first
    events = audit.get_events(debate_id_or_title)
    if events:
        return events

    # If no events found, try resolving as a title
    store = get_debate_store_for_project(project_id)
    for d in store.list_all(limit=500):
        if d.get("title", "") == debate_id_or_title:
            events = audit.get_events(d["debate_id"])
            return events if events else []

    # Also try case-insensitive partial match on title
    search_lower = debate_id_or_title.lower()
    for d in store.list_all(limit=500):
        title = d.get("title", "")
        if title and search_lower in title.lower():
            events = audit.get_events(d["debate_id"])
            return events if events else []

    # Return empty list — not a 404, since "no events yet" is valid
    return []


@router.get("/project/{project_id}")
async def get_audit_events_by_project(
    project_id: str,
    limit: int = 100,
    offset: int = 0,
    audit: AuditService = Depends(get_audit_service),
) -> list[dict]:
    """Return audit events for a project, ordered by timestamp desc."""
    return audit.get_events_by_project(project_id, limit=limit, offset=offset)
