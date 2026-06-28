"""API router for debate session history (list, delete, export reports, traces).

LEGACY: This router is superseded by the case-scoped sessions router under
``/api/v1/tenants/{tid}/cases/{cid}/sessions/`` (see
``backend/api/routers/assistant.py``) and the workflow-exec router under
``/api/v1/workflow-exec/sessions``. It is no longer registered in ``main.py``
(commit `chore/remove-legacy-sessions-router-2026-06`). The endpoints below
return ``410 Gone`` to signal to any straggler client that the API has been
intentionally retired and a successor path is available.

The legacy ``src.*`` imports have been removed entirely; the original
implementation is preserved in git history for reference. See plan
``plans/2026-06-22_danwa-legacy-sessions-router-cleanup.md`` for context.
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter()

_SUCCESSOR_HINT = (
    "Use /api/v1/tenants/{tid}/cases/{cid}/sessions/ (assistant router) or /api/v1/workflow-exec/sessions (workflow-exec router) instead."
)


@router.get("")
def list_sessions(
    limit: int = 20,
    offset: int = 0,
    min_consensus: float | None = None,
    project_id: str | None = None,
):
    """LEGACY: list past debate sessions. Retired — see module docstring."""
    return JSONResponse(
        status_code=410,
        content={"detail": "Legacy /api/v1/sessions endpoint retired.", "successor": _SUCCESSOR_HINT},
    )


@router.get("/{session_id}")
def get_session(session_id: str):
    """LEGACY: get a single session by ID. Retired — see module docstring."""
    raise HTTPException(status_code=410, detail=f"Legacy /api/v1/sessions/{session_id} endpoint retired. {_SUCCESSOR_HINT}")


@router.delete("/{session_id}")
def delete_session(session_id: str):
    """LEGACY: delete a session. Retired — see module docstring."""
    raise HTTPException(status_code=410, detail=f"Legacy DELETE /api/v1/sessions/{session_id} endpoint retired. {_SUCCESSOR_HINT}")


@router.get("/{session_id}/trace")
def get_trace(session_id: str):
    """LEGACY: get the audit trace for a session. Retired — see module docstring."""
    raise HTTPException(status_code=410, detail=f"Legacy /api/v1/sessions/{session_id}/trace endpoint retired. {_SUCCESSOR_HINT}")


@router.get("/{session_id}/report/{fmt}")
async def download_report(session_id: str, fmt: str):
    """LEGACY: download a report (docx or pdf). Retired — see module docstring.

    Successor: ``POST /api/v1/sessions/{id}/report`` (workflow_reports router)
    plus ``GET /api/v1/sessions/{id}/report/stream`` for SSE progress.
    """
    raise HTTPException(
        status_code=410,
        detail=(
            f"Legacy /api/v1/sessions/{session_id}/report/{fmt} endpoint retired. "
            f"Use POST /api/v1/workflow-exec/sessions/{session_id}/report instead."
        ),
    )
