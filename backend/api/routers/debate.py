"""Debate API router — CRUD endpoints for debates.

Business logic (workflow execution, RAG, title generation, OOB queues,
cancellation state) lives in ``backend.services.debate_workflow``.
Real-time SSE streaming lives in ``backend.api.routers.debate_stream``.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import (
    get_audit_service,
    get_debate_store_for_project,
    get_project_id,
    get_project_store,
)
from backend.api.events import publish_async
from backend.models.schemas import (
    DebateListItem,
    DebateRequest,
    DebateResponse,
    DebateStatus,
    DebateStatusResponse,
    OOBInputBody,
    OOBInputResponse,
    RoundData,
)
from backend.persistence.audit import AuditService
from backend.persistence.project_store import ProjectStore

logger = logging.getLogger(__name__)

router = APIRouter()


def _resolve_llm_model(llm_profile_id: str, project_id: str) -> str:
    """Resolve an LLM profile ID to the actual model name."""
    if not llm_profile_id:
        return ""
    try:
        from backend.api.deps import get_blueprint_repository

        repo = get_blueprint_repository()
        profile = repo.get_llm_profile(llm_profile_id)
        if profile:
            return profile.model
    except Exception:
        pass
    return llm_profile_id


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[DebateListItem])
async def list_debates(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> list[DebateListItem]:
    """List all debates (newest first) — for history panel.

    Query params:
        status: Filter by debate status (pending, running, completed, failed).
        search: Full-text search in case_preview (case-insensitive).
    """
    store = get_debate_store_for_project(project_id, project_store)
    debates = store.list_all(limit=limit + offset)

    project = project_store.get(project_id)
    project_name = project.name if project else project_id

    items = []
    for d in debates:
        req = d.get("request", {})
        if hasattr(req, "case"):
            case_text = req.case.text
            language = getattr(req, "language", "de")
        elif isinstance(req, dict):
            case_text = req.get("case", {}).get("text", "") if isinstance(req.get("case"), dict) else ""
            language = req.get("language", "de")
        else:
            case_text = ""
            language = "de"

        if status and d.get("status") != status:
            continue

        debate_title = d.get("title", "")
        if search:
            search_lower = search.lower()
            if (
                search_lower not in case_text.lower()
                and search_lower not in debate_title.lower()
                and search_lower not in d.get("debate_id", "").lower()
            ):
                continue

        result = d.get("result")
        consensus = result.get("final_consensus") if isinstance(result, dict) else None

        items.append(
            DebateListItem(
                debate_id=d["debate_id"],
                status=d["status"],
                title=d.get("title", ""),
                current_round=d.get("current_round", 0),
                max_rounds=d.get("max_rounds", 3),
                consensus_score=consensus,
                case_preview=case_text[:120],
                case_text=case_text,
                language=language,
                created_at=d.get("created_at", datetime.now(UTC)),
                updated_at=d.get("updated_at", datetime.now(UTC)),
                project_id=project_id,
                project_name=project_name,
            )
        )

    return items[offset : offset + limit]


@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    request: DebateRequest,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateResponse:
    """Create a new debate (status = pending)."""
    store = get_debate_store_for_project(project_id, project_store)
    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    debate = {
        "debate_id": debate_id,
        "status": DebateStatus.PENDING,
        "title": "",
        "request": request,
        "max_rounds": request.max_rounds,
        "current_round": 0,
        "rounds": [],
        "created_at": now,
        "updated_at": now,
        "result": None,
    }

    store.put(debate_id, debate)

    return DebateResponse(debate_id=debate_id, status=DebateStatus.PENDING, title="", created_at=now)


@router.delete("/{debate_id}")
async def delete_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict:
    """Delete a debate and its associated audit events."""
    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_value = status.value if hasattr(status, "value") else status
    if status_value == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running debate")

    deleted_events = audit.delete_events(debate_id)
    store.delete(debate_id)

    from backend.workflow.hitl.api import cleanup_hitl_state

    cleanup_hitl_state(debate_id)

    logger.info(
        "Deleted debate %s (%d audit events removed)",
        debate_id,
        deleted_events,
    )
    return {"detail": "Debate deleted", "debate_id": debate_id}


@router.get("/{debate_id}", response_model=DebateStatusResponse)
async def get_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateStatusResponse:
    """Get debate status and progress."""
    from backend.services.debate_workflow import build_rag_preview, extract_rag_info

    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    req = debate.get("request", {})
    max_rounds = getattr(req, "max_rounds", None) if hasattr(req, "max_rounds") else req.get("max_rounds", 3) if isinstance(req, dict) else 3

    if hasattr(req, "case"):
        case_text = req.case.text
        language = getattr(req, "language", "de")
        llm_profile_id = req.llm_profile_id
    elif isinstance(req, dict):
        case_text = req.get("case", {}).get("text", "") if isinstance(req.get("case"), dict) else ""
        language = req.get("language", "de")
        llm_profile_id = req.get("llm_profile_id", "")
    else:
        case_text = ""
        language = "de"
        llm_profile_id = ""

    result = debate.get("result")
    consensus = result.get("final_consensus") if isinstance(result, dict) else None
    anomalies = result.get("anomalies", []) if isinstance(result, dict) else []

    project = project_store.get(project_id)
    project_name = project.name if project else project_id

    document_ids, rag_auto_retrieve = extract_rag_info(req)
    rag_enabled = bool(document_ids) or rag_auto_retrieve
    rag_preview = build_rag_preview(project_id, document_ids) if document_ids else ""

    from backend.workflow.hitl.api import (
        get_active_interrupt,
        get_hitl_config,
    )
    from backend.workflow.hitl.api import (
        is_paused as hitl_is_paused,
    )

    hitl_config = get_hitl_config(debate_id)
    hitl_enabled = hitl_config.get("hitl_enabled", False)
    hitl_mode = hitl_config.get("hitl_mode", "off")
    paused = hitl_is_paused(debate_id)
    active_interrupt = get_active_interrupt(debate_id)

    result_interactions = result.get("interactions", []) if isinstance(result, dict) else []

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        title=debate.get("title", ""),
        current_round=debate.get("current_round", 0),
        max_rounds=max_rounds,
        consensus_score=consensus,
        rounds=[RoundData(**r) for r in debate.get("rounds", [])],
        created_at=debate.get("created_at", datetime.now(UTC)),
        updated_at=debate.get("updated_at", datetime.now(UTC)),
        case_text=case_text,
        language=language,
        llm_profile_id=llm_profile_id,
        llm_profile_model=_resolve_llm_model(llm_profile_id, project_id),
        anomalies=anomalies,
        project_id=project_id,
        project_name=project_name,
        rag_enabled=rag_enabled,
        rag_document_count=len(document_ids),
        rag_context_preview=rag_preview,
        hitl_enabled=hitl_enabled,
        hitl_mode=hitl_mode,
        is_paused=paused,
        has_active_interrupt=active_interrupt is not None,
        total_interactions=len(result_interactions),
    )


@router.post("/{debate_id}/start", response_model=DebateStatusResponse)
async def start_debate(
    debate_id: str,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateStatusResponse:
    """Start a pending debate — launches the workflow in a background task.

    Returns immediately with status=running.  Real-time progress is
    delivered via the SSE stream endpoint.
    """
    from backend.services.debate_workflow import extract_rag_info, run_debate_workflow

    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate["status"] != DebateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Debate is already {debate['status'].value}")

    debate["status"] = DebateStatus.RUNNING
    debate["updated_at"] = datetime.now(UTC)
    store.put(debate_id, debate)

    background_tasks.add_task(run_debate_workflow, debate_id, project_id, audit, store)

    req = debate.get("request", {})
    max_rounds = getattr(req, "max_rounds", None) if hasattr(req, "max_rounds") else req.get("max_rounds", 3) if isinstance(req, dict) else 3

    if hasattr(req, "case"):
        case_text = req.case.text
        language = getattr(req, "language", "de")
        llm_profile_id = req.llm_profile_id
    elif isinstance(req, dict):
        case_text = req.get("case", {}).get("text", "") if isinstance(req.get("case"), dict) else ""
        language = req.get("language", "de")
        llm_profile_id = req.get("llm_profile_id", "")
    else:
        case_text = ""
        language = "de"
        llm_profile_id = ""

    document_ids, rag_auto_retrieve = extract_rag_info(req)
    rag_enabled = bool(document_ids) or rag_auto_retrieve

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        title=debate.get("title", ""),
        current_round=debate.get("current_round", 0),
        max_rounds=max_rounds,
        consensus_score=None,
        rounds=[],
        created_at=debate.get("created_at", datetime.now(UTC)),
        updated_at=debate.get("updated_at", datetime.now(UTC)),
        case_text=case_text,
        language=language,
        llm_profile_id=llm_profile_id,
        rag_enabled=rag_enabled,
        rag_document_count=len(document_ids),
    )


# ---------------------------------------------------------------------------
# Cancel endpoint
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/cancel")
async def cancel_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict:
    """Cancel a running debate.

    Sets a cancellation flag that the workflow checks between rounds.
    Idempotent: if the debate already completed or failed, returns the
    current status instead of raising an error.
    """
    from backend.services.debate_workflow import mark_cancelled

    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate["status"]
    status_val = status.value if hasattr(status, "value") else status

    if status_val in ("completed", "failed"):
        logger.info(
            "Debate %s cancel requested but already '%s' — returning current status",
            debate_id,
            status_val,
        )
        return {"status": status_val, "message": f"Debate already {status_val}"}

    mark_cancelled(debate_id)
    logger.info("Debate %s cancellation requested", debate_id)
    return {"status": "ok", "message": "Cancellation requested"}


# ---------------------------------------------------------------------------
# Out-of-Band (OOB) Input endpoint
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/oob", response_model=OOBInputResponse)
async def submit_oob_input(
    debate_id: str,
    body: OOBInputBody,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> OOBInputResponse:
    """Submit an out-of-band input for a running debate.

    The input is queued and will be consumed by the next agent that matches
    the routing target.  Emits an SSE event for visualization.
    """
    from backend.services.debate_workflow import enqueue_oob

    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Debate is not running (current status: {status_val})",
        )

    oob_id = str(uuid.uuid4())
    oob_entry = {
        "oob_id": oob_id,
        "content": body.content,
        "target": body.target.model_dump(),
        "urgency": body.urgency,
        "status": "pending",
        "timestamp": datetime.now(UTC).isoformat(),
    }

    enqueue_oob(debate_id, oob_entry)

    session_id = debate.get("session_id", debate_id)
    await publish_async(
        session_id,
        "oob_input",
        {
            "type": "oob_input",
            "oob_id": oob_id,
            "content": body.content,
            "target": body.target.model_dump(),
            "urgency": body.urgency,
        },
    )

    logger.info("OOB input %s queued for debate %s", oob_id, debate_id)
    return OOBInputResponse(
        oob_id=oob_id,
        status="pending",
        target_resolved=body.target.type.value,
    )


# ---------------------------------------------------------------------------
# Documents endpoint (assign documents to a pending debate)
# ---------------------------------------------------------------------------


class DocumentAssignment(BaseModel):
    """Request body for assigning documents to a debate."""

    document_ids: list[str]
    rag_auto_retrieve: bool = False


@router.put("/{debate_id}/documents")
async def assign_documents(
    debate_id: str,
    body: DocumentAssignment,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> dict:
    """Assign or update documents for a pending debate.

    Can be called before or after debate creation, but only while the
    debate is still pending (not yet started).
    """
    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate["status"]
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "pending":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot assign documents to a {status_val} debate",
        )

    req = debate["request"]
    if hasattr(req, "document_ids"):
        req.document_ids = body.document_ids
        req.rag_auto_retrieve = body.rag_auto_retrieve
    elif isinstance(req, dict):
        req["document_ids"] = body.document_ids
        req["rag_auto_retrieve"] = body.rag_auto_retrieve

    debate["request"] = req
    store.put(debate_id, debate)

    logger.info(
        "Assigned %d documents to debate %s (auto_retrieve=%s)",
        len(body.document_ids),
        debate_id,
        body.rag_auto_retrieve,
    )
    return {
        "debate_id": debate_id,
        "document_ids": body.document_ids,
        "rag_auto_retrieve": body.rag_auto_retrieve,
    }
