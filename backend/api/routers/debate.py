"""Debate API router — create, query, and run debates."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_audit_service, get_debate_graph, get_debate_store
from backend.api.events import subscribe, unsubscribe
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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DebateListItem])
async def list_debates(
    limit: int = 50,
    offset: int = 0,
    store: DebateStore = Depends(get_debate_store),
) -> list[DebateListItem]:
    """List all debates (newest first) — for history panel."""
    debates = store.list_all(limit=limit, offset=offset)
    items = []
    for d in debates:
        req = d.get("request", {})
        # request may be a dict (from JSON) or a DebateRequest object
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

        items.append(DebateListItem(
            debate_id=d["debate_id"],
            status=d["status"],
            current_round=d.get("current_round", 0),
            max_rounds=d.get("max_rounds", 3),
            consensus_score=consensus,
            case_preview=case_text[:120],
            language=language,
            created_at=d.get("created_at", datetime.now(UTC)),
            updated_at=d.get("updated_at", datetime.now(UTC)),
        ))
    return items


@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    request: DebateRequest,
    audit: AuditService = Depends(get_audit_service),
    store: DebateStore = Depends(get_debate_store),
) -> DebateResponse:
    """Create a new debate (status = pending)."""
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


@router.get("/{debate_id}", response_model=DebateStatusResponse)
async def get_debate(
    debate_id: str,
    store: DebateStore = Depends(get_debate_store),
) -> DebateStatusResponse:
    """Get debate status and progress."""
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    req = debate.get("request", {})
    max_rounds = getattr(req, "max_rounds", None) if hasattr(req, "max_rounds") else req.get("max_rounds", 3) if isinstance(req, dict) else 3

    result = debate.get("result")
    consensus = result.get("final_consensus") if isinstance(result, dict) else None

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        current_round=debate.get("current_round", 0),
        max_rounds=max_rounds,
        consensus_score=consensus,
        rounds=[
            RoundData(**r) for r in debate.get("rounds", [])
        ],
        created_at=debate.get("created_at", datetime.now(UTC)),
        updated_at=debate.get("updated_at", datetime.now(UTC)),
    )


@router.post("/{debate_id}/start", response_model=DebateStatusResponse)
async def start_debate(
    debate_id: str,
    background_tasks: BackgroundTasks,
    audit: AuditService = Depends(get_audit_service),
    store: DebateStore = Depends(get_debate_store),
) -> DebateStatusResponse:
    """Start a pending debate — launches the workflow in a background task.

    Returns immediately with status=running.  Real-time progress is
    delivered via the SSE stream endpoint.
    """
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate["status"] != DebateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Debate is already {debate['status'].value}")

    debate["status"] = DebateStatus.RUNNING
    debate["updated_at"] = datetime.now(UTC)
    store.put(debate_id, debate)

    # Launch workflow in background so the HTTP response returns immediately
    background_tasks.add_task(_run_debate_workflow, debate_id, audit, store)

    req = debate.get("request", {})
    max_rounds = getattr(req, "max_rounds", None) if hasattr(req, "max_rounds") else req.get("max_rounds", 3) if isinstance(req, dict) else 3

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        current_round=debate.get("current_round", 0),
        max_rounds=max_rounds,
        consensus_score=None,
        rounds=[],
        created_at=debate.get("created_at", datetime.now(UTC)),
        updated_at=debate.get("updated_at", datetime.now(UTC)),
    )


async def _run_debate_workflow(debate_id: str, audit: AuditService, store: DebateStore) -> None:
    """Run the LangGraph workflow for a debate (called as background task)."""
    debate = store.get(debate_id)
    if not debate:
        return

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
        agent_profile_list = req.get("agent_profile", [
            {"role": "strategist", "llm_profile": "default", "temperature": 0.7},
            {"role": "critic", "llm_profile": "default", "temperature": 0.7},
            {"role": "optimizer", "llm_profile": "default", "temperature": 0.7},
            {"role": "moderator", "llm_profile": "default", "temperature": 0.7},
        ])

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
        return

    # Update debate state
    store.update(
        debate_id,
        status=DebateStatus.COMPLETED,
        current_round=result.get("current_round", max_rounds),
        rounds=result.get("rounds", []),
        result=result,
        updated_at=datetime.now(UTC),
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
        audit.record(event)

    logger.info(
        "Debate %s completed: %d rounds, consensus=%.3f",
        debate_id, result.get("current_round", 0), result.get("final_consensus", 0.0),
    )


# ---------------------------------------------------------------------------
# SSE endpoint — real-time streaming via event bus
# ---------------------------------------------------------------------------

async def _sse_events(debate_id: str, store: DebateStore):
    """Yield SSE events for a debate using the event bus."""
    debate = store.get(debate_id)
    if not debate:
        yield {"event": "error", "data": json.dumps({"detail": "Debate not found"})}
        return

    # Send initial status
    yield {
        "event": "status_change",
        "data": json.dumps({"debate_id": debate_id, "status": debate["status"].value if hasattr(debate["status"], "value") else debate["status"]}),
    }

    # If debate is already completed, send all rounds at once
    if debate["status"] == DebateStatus.COMPLETED:
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

    # If debate is running, subscribe to the event bus for real-time updates
    if debate["status"] == DebateStatus.RUNNING:
        queue = subscribe(debate_id)
        try:
            while True:
                try:
                    event_type, payload = await asyncio.wait_for(queue.get(), timeout=300.0)
                except asyncio.TimeoutError:
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
    store: DebateStore = Depends(get_debate_store),
):
    """SSE endpoint for real-time debate updates."""
    return EventSourceResponse(_sse_events(debate_id, store))
