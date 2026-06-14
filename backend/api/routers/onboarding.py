"""Case-Space Onboarding API router.

Lightweight router for the Welcome-Card flow described in
``plans/2026-06-14_case-space-workspace.md`` (Phase 3).

Phase-3 endpoint:

  GET /api/v1/onboarding/state?tenant_id=…  → OnboardingState

Returns three booleans that the frontend uses to decide whether
to show the Welcome-Card.  All three are intentionally simple
counts against the existing stores — no new database tables,
no schema changes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query

from backend.api.deps import get_case_store, get_debate_store_for_case
from backend.core.config import settings
from backend.models.schemas import OnboardingState

logger = logging.getLogger(__name__)

router = APIRouter()


def _require_onboarding() -> None:
    """The onboarding state is only meaningful when Case-Space is enabled."""
    if not settings.enable_case_space:
        # We don't 404 here — onboarding is a soft feature that
        # should still answer queries even when the workspace flag
        # is off, so the frontend can render an "off" message.
        pass


@router.get("/onboarding/state", response_model=OnboardingState)
def get_onboarding_state(
    tenant_id: str = Query(..., min_length=1),
    case_store=Depends(get_case_store),
) -> OnboardingState:
    """Return the three booleans the Welcome-Card consumes.

    The counts are best-effort and use the same stores the
    WorkspaceView already touches.  We don't open a separate
    document store query — documents are tracked per project, not
    per tenant, and a tenant-wide document count is not a useful
    onboarding signal.

    The function never raises: if a store is unavailable the
    corresponding boolean is False, which makes the Welcome-Card
    render with that card hidden rather than crash the dashboard.
    """
    _require_onboarding()

    has_cases = False
    has_debates = False
    try:
        cases = case_store.list_by_tenant(tenant_id)
        has_cases = len(cases) > 0
        # Count debates across all cases of the tenant
        for c in cases:
            try:
                debate_store = get_debate_store_for_case(c.id)
                if debate_store.list_all(limit=1):
                    has_debates = True
                    break
            except Exception:  # noqa: BLE001
                continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("onboarding: store unavailable for tenant %s: %s", tenant_id, exc)

    return OnboardingState(
        tenant_id=tenant_id,
        has_cases=has_cases,
        has_documents=False,  # DMS is per-project, not per-tenant — always False in this scope
        has_debates=has_debates,
    )
