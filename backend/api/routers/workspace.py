"""Case-Space Workspace API router.

This router serves the new Case-Space Workspace feature described in
``plans/2026-06-14_case-space-workspace.md``.  It is feature-gated by
``settings.enable_case_space``; while the flag is False the router
returns 404 for every endpoint so the legacy CasesView remains the
only navigation path.

Phase-1 endpoints (this file):
- GET  /api/v1/workspace/summary?case_id=…  → WorkspaceSummary
- GET  /api/v1/cases/search?q=…               → list[CaseSearchHit]  (Typeahead)

Permission model:
- The current user must have access to the case's tenant.  The detailed
  permission check is delegated to the case store, which raises
  PermissionError → mapped to 403 by the global handler.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_active_tenant, get_case_store
from backend.core.config import settings
from backend.models.schemas import (
    CaseSearchHit,
    WorkspaceRecentEvent,
    WorkspaceSuggestedNextStep,
    WorkspaceSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_case_space() -> None:
    """Feature-gate: 404 unless the workspace flag is enabled."""
    if not settings.enable_case_space:
        raise HTTPException(
            status_code=404,
            detail="Case-Space Workspace is not enabled (set DANWA_ENABLE_CASE_SPACE=true)",
        )


def _build_suggested_next_steps(
    case_id: str,
    debate_count: int,
    document_count: int,
) -> list[WorkspaceSuggestedNextStep]:
    """Return contextual hints based on the case's current state.

    Heuristics are deliberately simple in Phase 1 — they are designed
    to be replaced by richer signals once the analytics pipeline
    (phase 3+) provides per-case engagement metrics.
    """
    steps: list[WorkspaceSuggestedNextStep] = []
    if document_count == 0:
        steps.append(
            WorkspaceSuggestedNextStep(
                kind="no_documents",
                severity="info",
                message="No documents linked to this case yet.",
                action_label="Upload document",
                action_target="/workspace/upload",
            )
        )
    if debate_count == 0:
        steps.append(
            WorkspaceSuggestedNextStep(
                kind="no_debates",
                severity="info",
                message="This case has no debates yet.",
                action_label="Start debate",
                action_target="/workspace/new-debate",
            )
        )
    return steps


def _resolve_tag_name(tenant_id: str, tag_id: str) -> str:
    """Resolve a tag UUID to its display name.

    Falls back to the raw id when the tag has been deleted (or the
    TagStore cannot be reached for any reason).  This is a
    nice-to-have for the Workspace summary — it must never break
    the request, so every failure mode returns the raw id.
    """
    try:
        from backend.api.deps import get_tag_store

        tag = get_tag_store().get(tenant_id, tag_id)
        if tag is not None and getattr(tag, "name", None):
            return str(tag.name)
    except Exception:  # noqa: BLE001
        pass
    return tag_id


def _collect_recent_audit_events(tenant_id: str, case_id: str, limit: int = 5) -> list[WorkspaceRecentEvent]:
    """Aggregate the most recent audit events across all debates of a case.

    Phase 3.6: the Inspector / Recent-Activity strip in the
    Workspace view shows the last 5 events for the active
    case.  We pull the per-debate audit log (sorted by
    timestamp) and flatten them into a WorkspaceRecentEvent
    list.  Defensive: any error from the underlying audit
    service is swallowed and an empty list is returned --
    the Recent-Activity strip is a nice-to-have.
    """
    from backend.api.deps import get_debate_store_for_case
    from backend.workflow.audit_logger import get_audit_logger

    try:
        debate_store = get_debate_store_for_case(case_id)
        debates = debate_store.list_all() or []
    except Exception:  # noqa: BLE001
        debates = []

    events: list[WorkspaceRecentEvent] = []
    for d in debates[:50]:  # cap to 50 debates per case for sanity
        sid = d.get("session_id") or ""
        if not sid:
            continue
        try:
            al = get_audit_logger()
            wf_events = al.get_audit_log(sid) or []
        except Exception:  # noqa: BLE001
            continue
        for ev in wf_events:
            events.append(
                WorkspaceRecentEvent(
                    id=str(ev.get("id") or ev.get("timestamp") or ""),
                    event_type=str(ev.get("action") or ev.get("event_type") or "event"),
                    actor=ev.get("agent"),
                    subject=ev.get("role") or ev.get("agent"),
                    case_id=case_id,
                    debate_id=d.get("debate_id") or d.get("id") or "",
                    round=ev.get("round") if isinstance(ev.get("round"), int) else None,
                    phase=ev.get("phase"),
                    created_at=str(ev.get("timestamp") or ev.get("created_at") or ""),
                )
            )
    events.sort(key=lambda e: e.created_at, reverse=True)
    return events[:limit]


@router.get("/workspace/summary", response_model=WorkspaceSummary)
def get_workspace_summary(
    case_id: str = Query(..., min_length=1),
    tenant_id: str = Depends(get_active_tenant),
    store=Depends(get_case_store),
) -> WorkspaceSummary:
    """Return a case-scoped summary suitable for the Workspace view.

    The endpoint is intentionally read-only and aggregate-only — the
    actual entities (debates, documents, tags) are loaded separately
    by the frontend.  The summary exists so the Workspace can render
    a first paint without N+1 round-trips.
    """
    _require_case_space()

    # CaseStore.get requires (tenant_id, case_id).  P1 bugfix: the
    # original implementation called store.get(case_id) with a
    # single argument, which raised TypeError on every request
    # once the feature flag was on.  We now resolve the active
    # tenant via get_active_tenant (which honours the
    # X-Tenant-Id header) and pass it explicitly.
    case = store.get(tenant_id, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # 2026-06-16 — Cross-tenant defence in depth.
    # ``store.get(tenant_id, case_id)`` should already enforce
    # tenant scoping, but a misconfigured store or a stale
    # backfill could in principle return a case whose own
    # ``tenant_id`` does not match the caller's active tenant.
    # We re-check explicitly here so a mismatch is surfaced as
    # 404 (not_found) rather than silently leaking the wrong
    # tenant's data into the summary.  See
    # plans/2026-06-16_last-workspace-cross-tenant-bug.md.
    case_tenant = getattr(case, "tenant_id", None)
    if case_tenant and case_tenant != tenant_id:
        logger.warning(
            "workspace/summary: case %s belongs to tenant %s but caller "
            "is in tenant %s — refusing to render",
            case_id, case_tenant, tenant_id,
        )
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Aggregate counts.  The case object does not embed a
    # `debate_ids` list (debates live in their own per-case
    # DebateStore), so we count via the store.  We do not fetch
    # the full debate payloads here; ``list_all(limit=...)`` is
    # used with a high-enough cap that the UI can show "Debates:
    # 3" or "Documents: 0" without paging.  Documents are
    # currently per-project, not per-case (DMS scope) — we
    # default to 0 unless the case object exposes a count.
    try:
        from backend.api.deps import get_debate_store_for_case
        debate_store = get_debate_store_for_case(case.id)
        all_debates = debate_store.list_all(limit=500) or []
        debate_count = len(all_debates)
    except Exception:  # noqa: BLE001
        debate_count = 0
    try:
        document_count = len(getattr(case, "document_ids", []) or [])
    except Exception:  # noqa: BLE001
        document_count = 0

    return WorkspaceSummary(
        case_id=case.id,
        tenant_id=case.tenant_id,
        title=case.title,
        description=getattr(case, "description", None),
        status=getattr(case, "status", "active"),
        tags=list(getattr(case, "tags", []) or []),
        # Phase 2.8: resolve tag UUIDs -> names so the UI can
        # render "Science" instead of the UUID.  Falls back to
        # the raw id when the tag has been deleted since the
        # case was tagged.
        tag_names=[
            _resolve_tag_name(case.tenant_id, t)
            for t in (getattr(case, "tags", []) or [])
        ],
        members=list(getattr(case, "members", []) or []),
        member_count=len(getattr(case, "members", []) or []),
        debate_count=debate_count,
        document_count=document_count,
        recent_events=_collect_recent_audit_events(tenant_id, case_id, limit=5),
        suggested_next_steps=_build_suggested_next_steps(
            case_id=case.id,
            debate_count=debate_count,
            document_count=document_count,
        ),
        generated_at=datetime.now(UTC),
    )


@router.get("/cases/search", response_model=list[CaseSearchHit])
def search_cases(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(10, ge=1, le=50),
    store=Depends(get_case_store),
) -> list[CaseSearchHit]:
    """Typeahead endpoint for the Case selector in the Workspace header.

    Returns up to ``limit`` cases whose title or tags contain ``q``
    (case-insensitive substring match).  The store handles the
    tenant-scope filtering; the endpoint is read-only.
    """
    _require_case_space()

    needle = q.strip().lower()
    if not needle:
        return []

    try:
        all_cases = store.list()  # store-level list (may apply tenant filter)
    except Exception as exc:  # noqa: BLE001
        logger.warning("search_cases: store.list failed: %s", exc)
        return []

    hits: list[CaseSearchHit] = []
    for c in all_cases:
        title = (getattr(c, "title", "") or "").lower()
        tags = [t.lower() for t in (getattr(c, "tags", []) or [])]
        if needle in title or any(needle in t for t in tags):
            hits.append(
                CaseSearchHit(
                    case_id=c.id,
                    tenant_id=c.tenant_id,
                    title=c.title,
                    status=getattr(c, "status", "active"),
                    tags=list(getattr(c, "tags", []) or []),
                )
            )
            if len(hits) >= limit:
                break
    return hits
