"""Audit API router — query audit events for debates."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.api.deps import get_audit_service, get_debate_store_for_case, get_project_id
from backend.persistence.audit import AuditService

logger = logging.getLogger(__name__)

router = APIRouter()


def _enrich_events_with_debate_data(
    events: list[dict],
    debate_data: dict | None,
) -> list[dict]:
    """Enrich audit events with actual agent output content from the debate store.

    The ``AuditService`` only stores hashes — this function matches events
    to agent outputs in the debate rounds and adds the actual content.
    """
    if not debate_data:
        return events

    result = debate_data.get("result", {})
    rounds = debate_data.get("rounds", [])
    if not rounds and result:
        rounds = result.get("rounds", [])

    # Build a lookup: (round, role) -> agent_output content
    content_lookup: dict[tuple[int, str], dict] = {}
    for rd in rounds:
        round_num = rd.get("round", 0)
        for ao in rd.get("agent_outputs", []):
            role = ao.get("role", "")
            content_lookup[(round_num, role)] = {
                "content": ao.get("content", ""),
                "tokens_used": ao.get("tokens_used", 0),
            }

    enriched: list[dict] = []
    for event in events:
        event_copy = dict(event)
        round_num = event.get("round", 0)
        agent = event.get("agent", "")
        match = content_lookup.get((round_num, agent))
        if match:
            event_copy["content"] = match["content"]
            event_copy["tokens_used"] = match["tokens_used"]
        # Also try to resolve agent_output action with content
        if event.get("action") == "agent_output" and not event_copy.get("content"):
            # Try matching by round only (agent field might differ)
            for key, val in content_lookup.items():
                if key[0] == round_num:
                    event_copy["content"] = val["content"]
                    event_copy["tokens_used"] = val["tokens_used"]
                    break
        enriched.append(event_copy)

    return enriched


def _resolve_debate_id(debate_id_or_title: str, project_id: str) -> tuple[str, dict | None]:
    """Resolve a debate ID or title to the actual debate ID and data.

    Returns (debate_id, debate_data) or (debate_id_or_title, None) if not found.
    """
    store = get_debate_store_for_case(project_id)

    # Try direct lookup by debate_id first
    debate_data = store.get(debate_id_or_title)
    if debate_data:
        return debate_id_or_title, debate_data

    # Try exact title match
    for d in store.list_all(limit=500):
        if d.get("title", "") == debate_id_or_title:
            return d["debate_id"], d

    # Try case-insensitive partial match on title
    search_lower = debate_id_or_title.lower()
    for d in store.list_all(limit=500):
        title = d.get("title", "")
        if title and search_lower in title.lower():
            return d["debate_id"], d

    return debate_id_or_title, None


@router.get("/{debate_id_or_title}")
async def get_audit_events(
    debate_id_or_title: str,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> list[dict]:
    """Return all audit events for a debate, ordered by round.

    Accepts either a debate UUID or a debate title as the path parameter.
    If a title is provided, it is resolved to the matching debate ID first.

    Events are enriched with actual agent output content from the debate store.
    Falls back to workflow audit_log table for MVP debates.
    """
    debate_id, debate_data = _resolve_debate_id(debate_id_or_title, project_id)
    events = audit.get_events(debate_id)
    if events:
        return _enrich_events_with_debate_data(events, debate_data)

    # Fallback: check workflow audit_log table for MVP debates
    if debate_data and debate_data.get("session_id"):
        from backend.workflow.audit_logger import get_audit_logger

        session_id = debate_data["session_id"]
        al = get_audit_logger()
        wf_events = al.get_audit_log(session_id)
        if wf_events:
            return _transform_workflow_audit_events(wf_events, session_id)

    # Return empty list — not a 404, since "no events yet" is valid
    return []


def _transform_workflow_audit_events(wf_events: list[dict], session_id: str = "") -> list[dict]:
    """Transform workflow audit_log entries to the format expected by AuditView."""
    # Build enrichment maps from state snapshot
    llm_name_map: dict[str, str] = {}
    ctx_map: dict[str, dict] = {}
    if session_id:
        try:
            from backend.workflow.report_generator import (
                _build_audit_context_map,
                _build_node_llm_name_map,
                _format_audit_content,
            )

            llm_name_map = _build_node_llm_name_map(session_id)
            ctx_map = _build_audit_context_map(session_id)
        except Exception:
            _format_audit_content = None  # type: ignore[assignment]

    result = []
    for entry in wf_events:
        event_type = entry.get("event_type", "")
        node_id = entry.get("node_id", "")
        llm_display = llm_name_map.get(node_id, "") or entry.get("llm_profile_id", "")
        ctx = ctx_map.get(node_id, {})
        raw_content = entry.get("output_content", "")
        formatted = _format_audit_content(raw_content, event_type) if _format_audit_content else raw_content
        if event_type == "node_completed":
            result.append(
                {
                    "round": ctx.get("round"),
                    "phase": ctx.get("phase", ""),
                    "agent": entry.get("actor", ""),
                    "action": f"node_completed ({node_id})",
                    "content": formatted,
                    "timestamp": entry.get("timestamp"),
                    "llm_model": llm_display,
                    "tokens_used": entry.get("completion_tokens", 0),
                }
            )
        elif event_type == "node_started":
            result.append(
                {
                    "round": ctx.get("round"),
                    "phase": ctx.get("phase", ""),
                    "agent": entry.get("actor", ""),
                    "action": f"node_started ({node_id})",
                    "content": "",
                    "timestamp": entry.get("timestamp"),
                    "llm_model": "",
                    "tokens_used": 0,
                }
            )
        elif event_type == "node_failed":
            result.append(
                {
                    "round": ctx.get("round"),
                    "phase": ctx.get("phase", ""),
                    "agent": entry.get("actor", ""),
                    "action": f"node_failed ({node_id})",
                    "content": formatted,
                    "timestamp": entry.get("timestamp"),
                    "llm_model": "",
                    "tokens_used": 0,
                }
            )
        else:
            result.append(
                {
                    "round": ctx.get("round"),
                    "phase": ctx.get("phase", ""),
                    "agent": entry.get("actor", ""),
                    "action": event_type,
                    "content": formatted,
                    "timestamp": entry.get("timestamp"),
                    "llm_model": "",
                    "tokens_used": 0,
                }
            )
    return result


@router.get("/project/{project_id}")
async def get_audit_events_by_project(
    project_id: str,
    limit: int = 100,
    offset: int = 0,
    audit: AuditService = Depends(get_audit_service),
) -> list[dict]:
    """Return audit events for a project, ordered by timestamp desc."""
    return audit.get_events_by_project(project_id, limit=limit, offset=offset)
