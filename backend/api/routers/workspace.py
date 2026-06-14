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

    # Aggregate counts — keep this cheap: store.get already loaded the
    # case; the per-entity counts are derived from the case's existing
    # relationships (Phase 1 returns the bare minimum; richer aggregation
    # in Phase 2 once the inbox engine is in place).
    try:
        debate_count = len(getattr(case, "debate_ids", []) or [])
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
        members=list(getattr(case, "members", []) or []),
        debate_count=debate_count,
        document_count=document_count,
        recent_events=[],  # populated in Phase 2 once the inbox engine exists
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
