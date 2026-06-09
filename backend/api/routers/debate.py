"""Debate API router — CRUD endpoints for debates.

Business logic (workflow execution, RAG, title generation, OOB queues,
cancellation state) lives in ``backend.services.debate_workflow``.
Real-time SSE streaming lives in ``backend.api.routers.debate_stream``.

.. deprecated::
    These routes are deprecated. Use ``/api/v1/tenants/{tid}/cases/{cid}/debates/``
    instead. Legacy routes will be removed in a future version.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import (
    get_audit_service,
    get_debate_store_for_case,
    get_project_id,
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

logger = logging.getLogger(__name__)

router = APIRouter()

_DEPRECATION_NOTICE = "Use /api/v1/tenants/{tid}/cases/{cid}/debates/ instead. See /api/v1/debate for deprecation details."


def _add_deprecation_header(response):
    """Add deprecation header the instance."""
    response.headers["X-Deprecation"] = _DEPRECATION_NOTICE
    return response


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
    except Exception as e:
        logger.warning("Failed to resolve LLM profile model for %s: %s", llm_profile_id, e)
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
) -> list[DebateListItem]:
    """List all debates (newest first) — for history panel.

    Query params:
        status: Filter by debate status (pending, running, completed, failed).
        search: Full-text search in case_preview (case-insensitive).
    """
    store = get_debate_store_for_case(project_id)
    debates = store.list_all(limit=limit + offset)

    from backend.api.deps import get_project_store

    project = get_project_store().get(project_id)
    project_name = project.name if project else project_id

    items = []
    for d in debates:
        req = d.get("request", {})
        if hasattr(req, "case"):
            case_text = req.case.text
            language = getattr(req, "language", "de") or "de"
        elif isinstance(req, dict):
            case_text = req.get("case", {}).get("text", "") if isinstance(req.get("case"), dict) else ""
            language = req.get("language", "de") or "de"
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

        # Fork info anzeigen
        fork_info = d.get("fork_info")
        parent_id = fork_info.get("parent_debate_id") if isinstance(fork_info, dict) else None

        # Forks dieses Debatts zählen
        debate_id_current = d["debate_id"]
        forks_count = sum(
            1
            for other_d in debates
            if isinstance(other_d.get("fork_info"), dict) and other_d["fork_info"].get("parent_debate_id") == debate_id_current
        )

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
                parent_debate_id=parent_id,
                forks_count=forks_count,
                is_mvp=d.get("is_mvp", False),
            )
        )

    return items[offset : offset + limit]


@router.get("/cross-project/running")
async def find_running_debate_across_projects() -> DebateListItem | None:
    """Find the first running debate across ALL projects.

    Used by the Dashboard to detect externally-started debates (e.g. via A2A)
    that may live in a different project than the active one.
    """
    from backend.api.deps import get_project_store

    for project in get_project_store().list_all():
        try:
            store = get_debate_store_for_case(project.id)
            debates = store.list_all(limit=20)
            for d in debates:
                if d.get("status") == DebateStatus.RUNNING:
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

                    result = d.get("result")
                    consensus = result.get("final_consensus") if isinstance(result, dict) else None

                    return DebateListItem(
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
                        project_id=project.id,
                        project_name=project.name,
                        parent_debate_id=None,
                        forks_count=0,
                    )
        except Exception:
            continue
    return None


@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    request: DebateRequest,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> DebateResponse:
    """Create a new debate (status = pending)."""
    store = get_debate_store_for_case(project_id)
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
) -> dict:
    """Delete a debate and its associated audit events."""
    store = get_debate_store_for_case(project_id)
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


class MoveDebateBody(BaseModel):
    """Request body for moving a debate to another project."""

    project_id: str = Field(..., description="Target project ID to move the debate to")


@router.patch("/{debate_id}")
async def move_debate(
    debate_id: str,
    body: MoveDebateBody,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> dict:
    """Move a debate to a different project.

    Source project is determined by the X-Project-Id header.
    Target project is specified in the request body.
    """
    if body.project_id == project_id:
        raise HTTPException(status_code=400, detail="Source and target projects are the same")

    from backend.api.deps import get_project_store

    target_project = get_project_store().get(body.project_id)
    if not target_project:
        raise HTTPException(status_code=404, detail="Target project not found")

    source_store = get_debate_store_for_case(project_id)
    debate = source_store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val == "running":
        raise HTTPException(status_code=409, detail="Cannot move a running debate")

    target_store = get_debate_store_for_case(body.project_id)
    moved = source_store.move(debate_id, target_store)
    if not moved:
        raise HTTPException(status_code=500, detail="Failed to move debate")

    updated_audit = audit.update_debate_project(debate_id, body.project_id)

    logger.info(
        "Moved debate %s from project %s to project %s (%d audit events updated)",
        debate_id,
        project_id,
        body.project_id,
        updated_audit,
    )

    return {
        "detail": "Debate moved successfully",
        "debate_id": debate_id,
        "source_project_id": project_id,
        "target_project_id": body.project_id,
        "audit_events_updated": updated_audit,
    }


@router.get("/{debate_id}", response_model=DebateStatusResponse)
async def get_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
) -> DebateStatusResponse:
    """Get debate status and progress."""
    from backend.services.debate_workflow import build_rag_preview, extract_rag_info

    store = get_debate_store_for_case(project_id)
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

    from backend.api.deps import get_project_store

    project = get_project_store().get(project_id)
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

    # Fork info
    fork_info = debate.get("fork_info")
    parent_id = fork_info.get("parent_debate_id") if isinstance(fork_info, dict) else None

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
        prompt_language=debate.get("prompt_language", language),
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
        parent_debate_id=parent_id,
        session_id=debate.get("session_id"),
        is_mvp=debate.get("is_mvp", False),
    )


@router.post("/{debate_id}/start", response_model=DebateStatusResponse)
async def start_debate(
    debate_id: str,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> DebateStatusResponse:
    """Start a pending debate — launches the workflow in a background task.

    Returns immediately with status=running.  Real-time progress is
    delivered via the SSE stream endpoint.
    """
    from backend.services.debate_workflow import extract_rag_info
    from backend.tasks.dispatch import dispatch_debate_task

    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate["status"] != DebateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Debate is already {debate['status'].value}")

    debate["status"] = DebateStatus.RUNNING
    debate["updated_at"] = datetime.now(UTC)
    store.put(debate_id, debate)

    dispatch_debate_task(background_tasks, debate_id, project_id, audit, store)

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
        prompt_language=language,
        llm_profile_id=llm_profile_id,
        rag_enabled=rag_enabled,
        rag_document_count=len(document_ids),
    )


# ---------------------------------------------------------------------------
# Debate from Canvas Layout / Workflow Definition
# ---------------------------------------------------------------------------


class StartFromLayoutBody(BaseModel):
    """Request body for starting a debate from a canvas layout."""

    case_text: str = Field(..., min_length=1, description="Debate case/topic")
    bundle_ids: list[str] = Field(
        default_factory=list,
        description="AgentBundle IDs to use (overrides layout agent nodes)",
    )
    max_rounds: int = Field(default=3, ge=1, le=20)
    consensus_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    language: str | None = Field(default=None, description="Language code (uses user preference if not set)")
    llm_profile_id: str = Field(default="")


class StartFromWorkflowBody(BaseModel):
    """Request body for starting a debate from a workflow definition."""

    case_text: str = Field(..., min_length=1, description="Debate case/topic")
    max_rounds: int = Field(default=3, ge=1, le=20)
    consensus_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    language: str | None = Field(default=None, description="Language code (uses user preference if not set)")


@router.post("/from-layout/{layout_id}", response_model=DebateResponse, status_code=201)
async def start_debate_from_layout(
    layout_id: str,
    body: StartFromLayoutBody,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> DebateResponse:
    """Start a debate directly from a canvas layout.

    Converts the layout to a WorkflowDefinition, creates a debate with
    bundle-resolved agent profiles, and launches the workflow.
    """
    from backend.api.deps import get_blueprint_repository
    from backend.blueprints.canvas_to_workflow import CanvasToWorkflowConverter, ConversionError
    from backend.tasks.dispatch import dispatch_debate_task

    repo = get_blueprint_repository()
    store = get_debate_store_for_case(project_id)

    layout = repo.get_layout(layout_id)
    if not layout:
        raise HTTPException(status_code=404, detail="Canvas layout not found")

    try:
        converter = CanvasToWorkflowConverter(repo)
        wf = converter.convert(layout=layout)
    except ConversionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    # Build request with bundle_ids
    from backend.models.schemas import CaseInput
    from backend.models.schemas import DebateRequest as ReqModel

    request = ReqModel(
        case=CaseInput(text=body.case_text),
        agent_profile=[],  # Will be overridden by bundle_ids
        bundle_ids=body.bundle_ids,
        max_rounds=body.max_rounds,
        consensus_threshold=body.consensus_threshold,
        language=body.language,
        llm_profile_id=body.llm_profile_id,
    )

    debate = {
        "debate_id": debate_id,
        "status": DebateStatus.RUNNING,
        "title": "",
        "request": request,
        "max_rounds": body.max_rounds,
        "current_round": 0,
        "rounds": [],
        "created_at": now,
        "updated_at": now,
        "result": None,
        "workflow_id": wf.id,
    }
    store.put(debate_id, debate)

    dispatch_debate_task(background_tasks, debate_id, project_id, audit, store)

    return DebateResponse(
        debate_id=debate["debate_id"],
        status=DebateStatus.PENDING,
        title=debate["title"],
        created_at=debate["created_at"],
    )


# ---------------------------------------------------------------------------
# Cancel endpoint
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/cancel")
async def cancel_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
) -> dict:
    """Cancel a running debate.

    Sets a cancellation flag that the workflow checks between rounds.
    Idempotent: if the debate already completed or failed, returns the
    current status instead of raising an error.
    """
    from backend.services.debate_workflow import mark_cancelled

    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status

    if status_val in ("completed", "failed"):
        logger.info(
            "Debate %s cancel requested but already '%s' — returning current status",
            debate_id,
            status_val,
        )
        return {"status": status_val, "message": f"Debate already {status_val}"}

    # The workflow runner checks is_cancelled(session_id), NOT debate_id.
    # MVP debates use different IDs: debate_id (UUID) vs session_id (wf-xxx).
    # We must cancel the session_id so the running workflow sees the flag.
    session_id = debate.get("session_id", debate_id)
    mark_cancelled(session_id)
    logger.info("Debate %s cancellation requested (session_id=%s)", debate_id, session_id)
    return {"status": "ok", "message": "Cancellation requested"}


@router.post("/{debate_id}/force-reset")
async def force_reset_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
) -> dict:
    """Force-reset a stuck 'running' debate to 'failed'.

    Use this when a debate is stuck in 'running' state after a crash
    or server restart. Only operates on debates with status 'running'.
    """
    from datetime import UTC, datetime

    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "running":
        return {"status": status_val, "message": f"Debate is not running (current status: {status_val})"}

    store.update(
        debate_id,
        status=DebateStatus.FAILED,
        updated_at=datetime.now(UTC),
        result={"error": "Force-reset: debate was stuck in 'running' state"},
    )
    logger.info("Force-reset debate %s from 'running' to 'failed'", debate_id)
    return {"status": "ok", "message": "Debate reset to 'failed'"}


# ---------------------------------------------------------------------------
# Out-of-Band (OOB) Input endpoint
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/oob", response_model=OOBInputResponse)
async def submit_oob_input(
    debate_id: str,
    body: OOBInputBody,
    project_id: str = Depends(get_project_id),
) -> OOBInputResponse:
    """Submit an out-of-band input for a running debate.

    The input is queued and will be consumed by the next agent that matches
    the routing target.  Emits an SSE event for visualization.
    """
    from backend.services.debate_workflow import enqueue_oob

    store = get_debate_store_for_case(project_id)
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

    # Bridge to workflow interjection_service so agent nodes can
    # consume this input.  MVP debates use a different session_id
    # than debate_id, so both the OOB queue and the interjection
    # service must receive the item.
    session_id = debate.get("session_id", debate_id)
    try:
        from backend.workflow.interjection import interjection_service

        await interjection_service.submit(
            session_id=session_id,
            content=body.content,
            source="user",
            metadata={"oob_id": oob_id, "target": body.target.model_dump()},
        )
        logger.info("OOB input %s bridged to interjection_service for session %s", oob_id, session_id)
    except Exception:
        logger.warning("Failed to bridge OOB input %s to interjection_service for session %s", oob_id, session_id, exc_info=True)

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
) -> dict:
    """Assign or update documents for a pending debate.

    Can be called before or after debate creation, but only while the
    debate is still pending (not yet started).
    """
    store = get_debate_store_for_case(project_id)
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


# ---------------------------------------------------------------------------
# List forks of a debate (P4 helper)
# ---------------------------------------------------------------------------


@router.get("/{debate_id}/forks", response_model=list[DebateListItem])
async def list_forks(
    debate_id: str,
    limit: int = 50,
    offset: int = 0,
    project_id: str = Depends(get_project_id),
) -> list[DebateListItem]:
    """List all forks originating from a given debate (P4).

    Allows tracing the fork tree of a debate.
    """
    store = get_debate_store_for_case(project_id)
    debates = store.list_all(limit=limit + offset)

    from backend.api.deps import get_project_store

    project = get_project_store().get(project_id)
    project_name = project.name if project else project_id

    items = []
    for d in debates:
        fork_info = d.get("fork_info")
        if not isinstance(fork_info, dict):
            continue
        parent = fork_info.get("parent_debate_id")
        if parent != debate_id:
            continue

        req = d.get("request", {})
        if hasattr(req, "case"):
            case_text = req.case.text
        elif isinstance(req, dict):
            case_text = req.get("case", {}).get("text", "")
        else:
            case_text = ""

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
                created_at=d.get("created_at", datetime.now(UTC)),
                updated_at=d.get("updated_at", datetime.now(UTC)),
                project_id=project_id,
                project_name=project_name,
                parent_debate_id=parent,
            )
        )

    return items[offset : offset + limit]


# ---------------------------------------------------------------------------
# On-completed hook (P3 — DMS document auto-creation)
# ---------------------------------------------------------------------------


@router.post("/on-completed", response_model=dict)
async def on_debate_completed_hook(
    debate_id: str,
    project_id: str = Depends(get_project_id),
) -> dict:
    """Internal hook triggered after a debate transitions to completed status (P3).

    Creates a DMS document with the debate transcript for future RAG retrieval.
    """
    from backend.services.debate_workflow import on_debate_completed as do_complete

    doc_id = await do_complete(debate_id, project_id)
    if doc_id:
        return {"detail": "DMS document created", "document_id": doc_id}
    else:
        raise HTTPException(status_code=500, detail="Failed to create DMS document for debate")
