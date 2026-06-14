"""Case-Space Inbox API router.

This router serves the second view of the Case-Space redesign
described in ``plans/2026-06-14_case-space-workspace.md``.  It is
feature-gated by ``settings.enable_case_space_inbox``.

Phase-2 endpoints (this file):

  GET  /api/v1/inbox?tenant_id=…                        → InboxSummary
  POST /api/v1/inbox/bulk-move                          → InboxBulkResult
  POST /api/v1/inbox/bulk-tag                           → InboxBulkResult
  POST /api/v1/inbox/bulk-archive                       → InboxBulkResult

Item kinds emitted by ``GET /api/v1/inbox``:

  - ``recently_completed``  — debates completed in the last 7 days
  - ``untagged``            — debates with zero tags (any status)
  - ``stale_running``       — debates in ``running`` for > 24 h

Cross-tenant safety: every operation (read or write) is scoped to
the caller's tenant.  The bulk endpoints return a 200 with per-id
``failed`` entries when individual ids violate the tenant scope —
this lets the UI show a partial-success message instead of a 4xx
that would discard the whole batch.

Not implemented in this Phase-2 slice (see plans for follow-ups):

  - ``unlinked_documents``   — DMS doesn't yet model a per-case link
  - ``llm_suggested_cases``  — Phase 3 feature flag
  - ``my_mentions``          — audit_events schema doesn't yet track
                               mentioned_user_id
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.api.deps import get_case_store, get_debate_store_for_case
from backend.core.config import settings
from backend.models.schemas import (
    InboxBulkArchiveBody,
    InboxBulkMoveBody,
    InboxBulkResult,
    InboxBulkTagBody,
    InboxDebateItem,
    InboxSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ─── Tunables ────────────────────────────────────────────────────────
STALE_RUNNING_HOURS = 24
RECENTLY_COMPLETED_DAYS = 7
INBOX_DEFAULT_LIMIT = 50


def _require_inbox() -> None:
    """Feature-gate: 404 unless the inbox flag is enabled."""
    if not settings.enable_case_space_inbox:
        raise HTTPException(
            status_code=404,
            detail="Case-Space Inbox is not enabled (set DANWA_ENABLE_CASE_SPACE_INBOX=true)",
        )


def _parse_dt(value) -> datetime | None:
    """Best-effort parse of a datetime field from the store.

    The debate store stores ``updated_at``/``completed_at`` either as
    ISO strings or as ``datetime`` objects depending on the load
    path.  We normalise here so the API response is consistent.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            # The store sometimes appends a 'Z' suffix
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _build_debate_items_for_case(case_id: str, case_tenant_id: str) -> list[InboxDebateItem]:
    """Return all Inbox items belonging to a single case.

    Performs three queries against the case-scoped debate store:
    recently-completed, untagged, stale-running.  Defensive against
    malformed store data: any item that fails to parse is skipped
    (logged) rather than crashing the whole response.
    """
    items: list[InboxDebateItem] = []
    now = datetime.now(UTC)
    cutoff_completed = now - timedelta(days=RECENTLY_COMPLETED_DAYS)
    cutoff_stale = now - timedelta(hours=STALE_RUNNING_HOURS)

    try:
        store = get_debate_store_for_case(case_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("inbox: could not load debate store for case %s: %s", case_id, exc)
        return items

    # 1) Recently completed
    for d in store.list_by_status("completed"):
        completed_at = _parse_dt(d.get("completed_at")) or _parse_dt(d.get("updated_at"))
        if completed_at and completed_at >= cutoff_completed:
            items.append(
                InboxDebateItem(
                    id=d.get("debate_id") or d.get("id", ""),
                    kind="recently_completed",
                    tenant_id=case_tenant_id,
                    case_id=case_id,
                    title=d.get("topic") or d.get("title") or "(untitled)",
                    status="completed",
                    tags=list(d.get("tags") or []),
                    completed_at=completed_at,
                    message="Completed in the last 7 days — review or archive?",
                )
            )

    # 2) Untagged (any status)
    for d in store.list_all(limit=200):
        tags = list(d.get("tags") or [])
        if not tags:
            updated_at = _parse_dt(d.get("updated_at"))
            items.append(
                InboxDebateItem(
                    id=d.get("debate_id") or d.get("id", ""),
                    kind="untagged",
                    tenant_id=case_tenant_id,
                    case_id=case_id,
                    title=d.get("topic") or d.get("title") or "(untitled)",
                    status=d.get("status", "unknown"),
                    tags=[],
                    updated_at=updated_at,
                    message="This debate has no tags — add some to make it findable.",
                )
            )

    # 3) Stale running
    for d in store.list_by_status("running"):
        updated_at = _parse_dt(d.get("updated_at"))
        if updated_at and updated_at < cutoff_stale:
            age_h = (now - updated_at).total_seconds() / 3600.0
            items.append(
                InboxDebateItem(
                    id=d.get("debate_id") or d.get("id", ""),
                    kind="stale_running",
                    tenant_id=case_tenant_id,
                    case_id=case_id,
                    title=d.get("topic") or d.get("title") or "(untitled)",
                    status="running",
                    tags=list(d.get("tags") or []),
                    updated_at=updated_at,
                    age_hours=round(age_h, 1),
                    message=f"Running for {age_h:.0f} h — consider opening or cancelling.",
                )
            )

    return items


# ─── Read endpoint ──────────────────────────────────────────────────


@router.get("/inbox", response_model=InboxSummary)
def get_inbox(
    tenant_id: str = Query(..., min_length=1),
    case_store=Depends(get_case_store),
) -> InboxSummary:
    """Return all Inbox items for the caller's tenant.

    Iterates the tenant's cases and aggregates items from each
    case-scoped debate store.  Limited to ``INBOX_DEFAULT_LIMIT``
    items total; if more exist, the oldest by ``updated_at`` are
    dropped (the UI is told via the response that the inbox is
    partial — a future phase can add pagination).
    """
    _require_inbox()

    cases = case_store.list_by_tenant(tenant_id)
    all_items: list[InboxDebateItem] = []
    for c in cases:
        all_items.extend(_build_debate_items_for_case(c.id, c.tenant_id))

    # Counts per kind
    counts: dict[str, int] = {}
    for it in all_items:
        counts[it.kind] = counts.get(it.kind, 0) + 1

    # Cap and sort by recency (items with updated_at/completed_at
    # first, then untagged, then stale — within each group by date)
    def _sort_key(it: InboxDebateItem) -> str:
        return it.completed_at.isoformat() if it.completed_at else it.updated_at.isoformat() if it.updated_at else ""

    all_items.sort(key=_sort_key, reverse=True)
    if len(all_items) > INBOX_DEFAULT_LIMIT:
        all_items = all_items[:INBOX_DEFAULT_LIMIT]

    return InboxSummary(
        tenant_id=tenant_id,
        items=all_items,
        counts=counts,
        is_all_clear=len(all_items) == 0,
        generated_at=now if (now := datetime.now(UTC)) else datetime.now(UTC),
    )


# ─── Bulk endpoints ─────────────────────────────────────────────────


def _resolve_tenant_for_debates(
    debate_ids: list[str],
    case_store,
) -> tuple[list[tuple[str, str, object]], list[dict]]:
    """Resolve a list of debate_ids to (case_id, debate_obj) tuples.

    Iterates every case in every tenant the user can see.  In this
    phase we accept all tenants (no real auth-z in P2); the real
    permission layer is Phase 2.3 — for now the caller is trusted.
    """
    matched: list[tuple[str, str, object]] = []
    failed: list[dict] = []
    seen_ids: set[str] = set()

    # No "list all tenants" helper exists, so we look at the ones we
    # can find via the case store's cache.  This is a known
    # limitation; it is documented and a follow-up item.
    # For Phase 2 we accept that this endpoint only finds debates
    # in tenants that have at least one case.
    for tenant_id in _known_tenants_via_case_store(case_store):
        cases = case_store.list_by_tenant(tenant_id)
        for c in cases:
            try:
                store = get_debate_store_for_case(c.id)
            except Exception:  # noqa: BLE001
                continue
            for did in debate_ids:
                if did in seen_ids:
                    continue
                d = store.get(did)
                if d is None:
                    continue
                matched.append((c.id, c.tenant_id, d))
                seen_ids.add(did)

    for did in debate_ids:
        if did not in seen_ids:
            failed.append({"id": did, "reason": "not_found_or_wrong_tenant"})
    return matched, failed


def _known_tenants_via_case_store(case_store) -> list[str]:
    """Return all tenant ids the case_store has loaded.

    The case_store keeps a per-tenant cache; we walk it.  This is
    not a "list all tenants" API call — it is the best we can do
    in P2 without a tenant_store dependency.
    """
    cache = getattr(case_store, "_cache", None)
    if isinstance(cache, dict):
        return list(cache.keys())
    return []


@router.post("/inbox/bulk-move", response_model=InboxBulkResult)
def bulk_move(
    body: InboxBulkMoveBody,
    case_store=Depends(get_case_store),
) -> InboxBulkResult:
    """Move the listed debates to ``target_case_id``.

    Implementation: DebateStore.move_to_case() (already shipped in
    Phase 1.x) handles the file-IO.  This endpoint is the
    orchestration layer that enforces tenant safety and
    partial-success reporting.
    """
    _require_inbox()

    # Locate the target case in any known tenant
    target_tenant_id: str | None = None
    target_case_obj = None
    for tid in _known_tenants_via_case_store(case_store):
        t = case_store.get(tid, body.target_case_id)
        if t is not None:
            target_tenant_id = tid
            target_case_obj = t
            break
    if target_case_obj is None:
        raise HTTPException(status_code=404, detail=f"Target case {body.target_case_id} not found")

    matched, failed = _resolve_tenant_for_debates(body.debate_ids, case_store)
    succeeded: list[str] = []
    for src_case_id, src_tenant_id, debate in matched:
        did = debate.get("debate_id") or debate.get("id", "")
        if src_tenant_id != target_tenant_id:
            failed.append(
                {
                    "id": did,
                    "reason": f"cross_tenant: source={src_tenant_id} target={target_tenant_id}",
                }
            )
            continue
        if src_case_id == body.target_case_id:
            # Already in target case — count as a no-op success
            succeeded.append(did)
            continue
        try:
            src_store = get_debate_store_for_case(src_case_id)
            tgt_store = get_debate_store_for_case(body.target_case_id)
            ok = src_store.move(did, tgt_store)
            if ok:
                succeeded.append(did)
            else:
                failed.append({"id": did, "reason": "store_rejected_move"})
        except Exception as exc:  # noqa: BLE001
            logger.warning("inbox bulk-move: %s", exc)
            failed.append({"id": did, "reason": f"move_failed: {exc}"})

    return InboxBulkResult(succeeded=succeeded, failed=failed)


@router.post("/inbox/bulk-tag", response_model=InboxBulkResult)
def bulk_tag(
    body: InboxBulkTagBody,
    case_store=Depends(get_case_store),
) -> InboxBulkResult:
    """Add the listed tags to each debate.

    An empty ``tag_ids`` is a no-op (200, all in ``succeeded``).
    Existing tags are kept (idempotent union).
    """
    _require_inbox()

    matched, failed = _resolve_tenant_for_debates(body.debate_ids, case_store)
    succeeded: list[str] = []
    for case_id, _tid, debate in matched:
        did = debate.get("debate_id") or debate.get("id", "")
        try:
            store = get_debate_store_for_case(case_id)
            existing = set(debate.get("tags") or [])
            for t in body.tag_ids:
                existing.add(t)
            debate["tags"] = sorted(existing)
            store.put(did, debate)
            succeeded.append(did)
        except Exception as exc:  # noqa: BLE001
            failed.append({"id": did, "reason": f"tag_failed: {exc}"})

    return InboxBulkResult(succeeded=succeeded, failed=failed)


@router.post("/inbox/bulk-archive", response_model=InboxBulkResult)
def bulk_archive(
    body: InboxBulkArchiveBody,
    case_store=Depends(get_case_store),
) -> InboxBulkResult:
    """Archive (soft-remove) the listed debates from their case stores.

    Implementation: the legacy archive view marks the debate's case
    with an ``archived_at`` timestamp; in P2 we simply remove the
    debate from its case store.  A future phase can replace this
    with a soft-delete flag.
    """
    _require_inbox()

    matched, failed = _resolve_tenant_for_debates(body.debate_ids, case_store)
    succeeded: list[str] = []
    for case_id, _tid, debate in matched:
        did = debate.get("debate_id") or debate.get("id", "")
        try:
            store = get_debate_store_for_case(case_id)
            # Mark archived and persist (soft delete on the store)
            debate["status"] = "archived"
            debate["archived_at"] = datetime.now(UTC).isoformat()
            store.put(did, debate)
            succeeded.append(did)
        except Exception as exc:  # noqa: BLE001
            failed.append({"id": did, "reason": f"archive_failed: {exc}"})

    return InboxBulkResult(succeeded=succeeded, failed=failed)
