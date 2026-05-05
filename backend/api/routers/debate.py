"""Debate API router — create, query, and run debates."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import (
    get_audit_service,
    get_debate_graph,
    get_debate_store_for_project,
    get_project_id,
    get_project_store,
)
from backend.api.events import publish_async, subscribe, unsubscribe
from backend.models.schemas import (
    AuditEvent,
    DebateListItem,
    DebateRequest,
    DebateResponse,
    DebateStatus,
    DebateStatusResponse,
    RoundData,
)
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore

logger = logging.getLogger(__name__)

router = APIRouter()

# Set of debate IDs that have been requested to cancel
_cancelled_debates: set[str] = set()


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
    store = get_debate_store_for_project(project_id)
    debates = store.list_all(limit=limit + offset)  # fetch extra for filtering

    # Resolve project name once
    project_store = get_project_store()
    project = project_store.get(project_id)
    project_name = project.name if project else project_id

    items = []
    for d in debates:
        req = d.get("request", {})
        # request may be a dict (from JSON) or a DebateRequest object
        if hasattr(req, "case"):
            case_text = req.case.text
            language = getattr(req, "language", "de")
        elif isinstance(req, dict):
            case_text = (
                req.get("case", {}).get("text", "") if isinstance(req.get("case"), dict) else ""
            )
            language = req.get("language", "de")
        else:
            case_text = ""
            language = "de"

        # Filter by status
        if status and d.get("status") != status:
            continue

        # Filter by search text
        if search and search.lower() not in case_text.lower():
            continue

        result = d.get("result")
        consensus = result.get("final_consensus") if isinstance(result, dict) else None

        items.append(
            DebateListItem(
                debate_id=d["debate_id"],
                status=d["status"],
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

    # Apply offset/limit after filtering
    return items[offset : offset + limit]


@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    request: DebateRequest,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> DebateResponse:
    """Create a new debate (status = pending)."""
    store = get_debate_store_for_project(project_id)
    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    debate = {
        "debate_id": debate_id,
        "status": DebateStatus.PENDING,
        "request": request,
        "max_rounds": request.max_rounds,
        "current_round": 0,
        "rounds": [],
        "created_at": now,
        "updated_at": now,
        "result": None,
    }

    store.put(debate_id, debate)

    return DebateResponse(debate_id=debate_id, status=DebateStatus.PENDING, created_at=now)


@router.delete("/{debate_id}")
async def delete_debate(
    debate_id: str,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
) -> dict:
    """Delete a debate and its associated audit events."""
    store = get_debate_store_for_project(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    # Prevent deletion of running debates
    status = debate.get("status")
    status_value = status.value if hasattr(status, "value") else status
    if status_value == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running debate")

    # Delete audit events first, then the debate itself
    deleted_events = audit.delete_events(debate_id)
    store.delete(debate_id)

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
) -> DebateStatusResponse:
    """Get debate status and progress."""
    store = get_debate_store_for_project(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    req = debate.get("request", {})
    max_rounds = (
        getattr(req, "max_rounds", None)
        if hasattr(req, "max_rounds")
        else req.get("max_rounds", 3)
        if isinstance(req, dict)
        else 3
    )

    # Extract case text and metadata from request
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

    # Resolve project name
    project_store = get_project_store()
    project = project_store.get(project_id)
    project_name = project.name if project else project_id

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        current_round=debate.get("current_round", 0),
        max_rounds=max_rounds,
        consensus_score=consensus,
        rounds=[RoundData(**r) for r in debate.get("rounds", [])],
        created_at=debate.get("created_at", datetime.now(UTC)),
        updated_at=debate.get("updated_at", datetime.now(UTC)),
        case_text=case_text,
        language=language,
        llm_profile_id=llm_profile_id,
        anomalies=anomalies,
        project_id=project_id,
        project_name=project_name,
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
    store = get_debate_store_for_project(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate["status"] != DebateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Debate is already {debate['status'].value}")

    debate["status"] = DebateStatus.RUNNING
    debate["updated_at"] = datetime.now(UTC)
    store.put(debate_id, debate)

    # Launch workflow in background so the HTTP response returns immediately
    background_tasks.add_task(_run_debate_workflow, debate_id, project_id, audit, store)

    req = debate.get("request", {})
    max_rounds = (
        getattr(req, "max_rounds", None)
        if hasattr(req, "max_rounds")
        else req.get("max_rounds", 3)
        if isinstance(req, dict)
        else 3
    )

    # Extract case text and metadata from request
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

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        current_round=debate.get("current_round", 0),
        max_rounds=max_rounds,
        consensus_score=None,
        rounds=[],
        created_at=debate.get("created_at", datetime.now(UTC)),
        updated_at=debate.get("updated_at", datetime.now(UTC)),
        case_text=case_text,
        language=language,
        llm_profile_id=llm_profile_id,
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
    The debate will be marked as failed with a cancellation message.

    Idempotent: if the debate already completed or failed, returns the
    current status instead of raising an error (race condition fix).
    """
    store = get_debate_store_for_project(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate["status"]
    status_val = status.value if hasattr(status, "value") else status

    # Already finished — return current status (idempotent)
    if status_val in ("completed", "failed"):
        logger.info(
            "Debate %s cancel requested but already '%s' — returning current status",
            debate_id,
            status_val,
        )
        return {
            "status": status_val,
            "message": f"Debate already {status_val}",
        }

    # Pending or running — set cancellation flag
    _cancelled_debates.add(debate_id)
    logger.info("Debate %s cancellation requested", debate_id)
    return {"status": "ok", "message": "Cancellation requested"}


def is_cancelled(debate_id: str) -> bool:
    """Check if a debate has been cancelled."""
    return debate_id in _cancelled_debates


def clear_cancel(debate_id: str) -> None:
    """Remove cancellation flag after handling."""
    _cancelled_debates.discard(debate_id)


async def _run_debate_workflow(
    debate_id: str, project_id: str, audit: AuditService, store: DebateStore
) -> None:
    """Run the LangGraph workflow for a debate (called as background task)."""
    debate = store.get(debate_id)
    if not debate:
        return

    # --- Publish: workflow started (immediate feedback to user) ---
    await publish_async(
        debate_id,
        "workflow_started",
        {
            "type": "workflow_started",
            "message": "Workflow engine started, preparing debate...",
            "debate_id": debate_id,
        },
    )

    req = debate["request"]

    # Extract request fields (handle both DebateRequest object and dict)
    if hasattr(req, "case"):
        case_text = req.case.text
        max_rounds = req.max_rounds
        consensus_threshold = req.consensus_threshold
        enable_fact_check = req.enable_fact_check
        enable_memory = req.enable_memory
        llm_profile_id = req.llm_profile_id
        prompt_variant = req.prompt_variant
        agent_persona_ids = req.agent_persona_ids
        language = getattr(req, "language", "de")
        # search_mode: use explicit value, or derive from enable_fact_check
        raw_search_mode = getattr(req, "search_mode", None)
        if raw_search_mode is not None:
            search_mode = (
                raw_search_mode.value
                if hasattr(raw_search_mode, "value")
                else str(raw_search_mode)
            )
        elif enable_fact_check:
            search_mode = "required"
        else:
            search_mode = "off"
        agent_profile_list = [
            {"role": a.role.value, "llm_profile": a.llm_profile, "temperature": a.temperature}
            for a in req.agent_profile
        ]
    else:
        # Dict form (loaded from JSON persistence)
        case_text = req.get("case", {}).get("text", "")
        max_rounds = req.get("max_rounds", 3)
        consensus_threshold = req.get("consensus_threshold", 0.8)
        enable_fact_check = req.get("enable_fact_check", False)
        enable_memory = req.get("enable_memory", False)
        llm_profile_id = req.get("llm_profile_id", "openrouter-claude")
        prompt_variant = req.get("prompt_variant", "default")
        agent_persona_ids = req.get("agent_persona_ids", {})
        language = req.get("language", "de")
        raw_search_mode = req.get("search_mode")
        if raw_search_mode:
            search_mode = raw_search_mode
        elif enable_fact_check:
            search_mode = "required"
        else:
            search_mode = "off"
        agent_profile_list = req.get(
            "agent_profile",
            [
                {"role": "strategist", "llm_profile": "default", "temperature": 0.7},
                {"role": "critic", "llm_profile": "default", "temperature": 0.7},
                {"role": "optimizer", "llm_profile": "default", "temperature": 0.7},
                {"role": "moderator", "llm_profile": "default", "temperature": 0.7},
            ],
        )

    # Build initial state for LangGraph
    initial_state = {
        "context": case_text,
        "agent_profile": agent_profile_list,
        "max_rounds": max_rounds,
        "threshold": consensus_threshold,
        "enable_fact_check": enable_fact_check,
        "enable_memory": enable_memory,
        "rag_context": "",
        # --- Profile configuration (Sprint 3) ---
        "llm_profile_id": llm_profile_id,
        "prompt_variant": prompt_variant,
        "agent_persona_ids": agent_persona_ids,
        # --- Language (Sprint 4) ---
        "language": language,
        # --- Web search (Sprint 5) ---
        "search_mode": search_mode,
        # --- Project isolation ---
        "project_id": project_id,
        # --- Runtime ---
        "session_id": debate_id,
        "current_round": 0,
        "current_agent_index": 0,
        "rounds": [],
        "agent_outputs": [],
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "validation_report": [],
        "used_variant": "default",
    }

    # Run graph — async because nodes may call LLM APIs
    graph = get_debate_graph()
    try:
        result = await graph.ainvoke(initial_state)
    except Exception as exc:
        logger.error("Debate %s failed: %s", debate_id, exc, exc_info=True)
        store.update(debate_id, status=DebateStatus.FAILED, updated_at=datetime.now(UTC))
        clear_cancel(debate_id)
        return

    # Check if debate was cancelled during execution
    if is_cancelled(debate_id):
        store.update(
            debate_id,
            status=DebateStatus.FAILED,
            current_round=result.get("current_round", 0),
            rounds=result.get("rounds", []),
            result={**(result or {}), "cancel_reason": "User cancelled the debate"},
            updated_at=datetime.now(UTC),
        )
        # Publish SSE event so the frontend sees the status change
        await publish_async(
            debate_id,
            "status_change",
            {
                "status": "failed",
                "cancel_reason": "User cancelled the debate",
            },
        )
        clear_cancel(debate_id)
        logger.info("Debate %s was cancelled by user", debate_id)
        return

    # Update debate state — mark as failed if all agents had anomalies
    anomalies = result.get("anomalies", [])
    has_failures = len(anomalies) > 0
    final_status = DebateStatus.FAILED if has_failures else DebateStatus.COMPLETED

    store.update(
        debate_id,
        status=final_status,
        current_round=result.get("current_round", max_rounds),
        rounds=result.get("rounds", []),
        result=result,
        updated_at=datetime.now(UTC),
    )

    if has_failures:
        logger.warning(
            "Debate %s completed with %d anomaly(ies): %s",
            debate_id,
            len(anomalies),
            anomalies,
        )

    # Record audit events
    for agent_output in result.get("agent_outputs", []):
        event = AuditEvent(
            debate_id=debate_id,
            round=result.get("current_round", 1),
            agent=agent_output["role"],
            action="agent_output",
            input_hash=str(hash(agent_output["content"][:100])),
            output_hash=str(hash(agent_output["content"])),
            llm_model=llm_profile_id,
            tokens_used=agent_output.get("tokens_used", 0),
        )
        audit.record(event, project_id=project_id)

    clear_cancel(debate_id)
    logger.info(
        "Debate %s completed: %d rounds, consensus=%.3f",
        debate_id,
        result.get("current_round", 0),
        result.get("final_consensus", 0.0),
    )


# ---------------------------------------------------------------------------
# SSE endpoint — real-time streaming via event bus
# ---------------------------------------------------------------------------


async def _sse_events(debate_id: str, project_id: str, store: DebateStore):
    """Yield SSE events for a debate using the event bus.

    Subscribes to the event bus for pending AND running debates so that
    events published after ``start_debate()`` are not missed (the frontend
    connects SSE *before* calling start).
    """
    debate = store.get(debate_id)
    if not debate:
        yield {"event": "error", "data": json.dumps({"detail": "Debate not found"})}
        return

    status = debate["status"]
    status_val = status.value if hasattr(status, "value") else status

    # Send initial status
    yield {
        "event": "status_change",
        "data": json.dumps({"debate_id": debate_id, "status": status_val}),
    }

    # If debate is already completed/failed, send all rounds at once and return
    if status == DebateStatus.COMPLETED:
        for i, round_data in enumerate(debate.get("rounds", [])):
            yield {
                "event": "round_update",
                "data": json.dumps({"round": i + 1, "data": round_data}),
            }
        yield {
            "event": "status_change",
            "data": json.dumps({"debate_id": debate_id, "status": "completed"}),
        }
        return

    if status == DebateStatus.FAILED:
        yield {
            "event": "status_change",
            "data": json.dumps({"debate_id": debate_id, "status": "failed"}),
        }
        return

    # For pending or running debates: subscribe to the event bus.
    # The frontend connects SSE *before* calling start_debate(), so the
    # debate is still pending at this point.  We must subscribe now so
    # that events published once the background task starts are received.
    queue = subscribe(debate_id)
    try:
        while True:
            try:
                event_type, payload = await asyncio.wait_for(queue.get(), timeout=300.0)
            except TimeoutError:
                # No events for 5 minutes — send keepalive
                yield {"event": "keepalive", "data": "{}"}
                continue

            yield {"event": event_type, "data": payload}

            # If debate completed or failed, stop
            if event_type == "status_change":
                data = json.loads(payload)
                if data.get("status") in ("completed", "failed"):
                    break
    finally:
        unsubscribe(debate_id, queue)


@router.get("/{debate_id}/stream")
async def stream_debate(
    debate_id: str,
    project_id: str = Query(
        ...,
        description="Project UUID (query param, since EventSource cannot send headers)",
    ),
):
    """SSE endpoint for real-time debate updates.

    Accepts ``project_id`` as a **query parameter** because the browser's
    ``EventSource`` API cannot send custom HTTP headers.
    """
    store = get_debate_store_for_project(project_id)
    return EventSourceResponse(_sse_events(debate_id, project_id, store))
