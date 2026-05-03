"""Debate API router — create, query, and run debates."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_audit_service, get_debate_graph
from backend.api.events import subscribe, unsubscribe
from backend.models.schemas import (
    AuditEvent,
    DebateRequest,
    DebateResponse,
    DebateStatus,
    DebateStatusResponse,
    RoundData,
)
from backend.persistence.audit import AuditService

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory debate store (Sprint 1 only — replaced by DB in Sprint 3)
# ---------------------------------------------------------------------------
_debates: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=DebateResponse, status_code=201)
async def create_debate(
    request: DebateRequest,
    audit: AuditService = Depends(get_audit_service),
) -> DebateResponse:
    """Create a new debate (status = pending)."""
    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    _debates[debate_id] = {
        "debate_id": debate_id,
        "status": DebateStatus.PENDING,
        "request": request,
        "current_round": 0,
        "rounds": [],
        "created_at": now,
        "updated_at": now,
        "result": None,
    }

    return DebateResponse(debate_id=debate_id, status=DebateStatus.PENDING, created_at=now)


@router.get("/{debate_id}", response_model=DebateStatusResponse)
async def get_debate(debate_id: str) -> DebateStatusResponse:
    """Get debate status and progress."""
    debate = _debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        current_round=debate["current_round"],
        max_rounds=debate["request"].max_rounds,
        consensus_score=debate["result"]["final_consensus"] if debate["result"] else None,
        rounds=[
            RoundData(**r) for r in debate["rounds"]
        ],
        created_at=debate["created_at"],
        updated_at=debate["updated_at"],
    )


@router.post("/{debate_id}/start", response_model=DebateStatusResponse)
async def start_debate(
    debate_id: str,
    background_tasks: BackgroundTasks,
    audit: AuditService = Depends(get_audit_service),
) -> DebateStatusResponse:
    """Start a pending debate — launches the workflow in a background task.

    Returns immediately with status=running.  Real-time progress is
    delivered via the SSE stream endpoint.
    """
    debate = _debates.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate["status"] != DebateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Debate is already {debate['status'].value}")

    debate["status"] = DebateStatus.RUNNING
    debate["updated_at"] = datetime.now(UTC)

    # Launch workflow in background so the HTTP response returns immediately
    background_tasks.add_task(_run_debate_workflow, debate_id, audit)

    return DebateStatusResponse(
        debate_id=debate["debate_id"],
        status=debate["status"],
        current_round=debate["current_round"],
        max_rounds=debate["request"].max_rounds,
        consensus_score=None,
        rounds=[],
        created_at=debate["created_at"],
        updated_at=debate["updated_at"],
    )


async def _run_debate_workflow(debate_id: str, audit: AuditService) -> None:
    """Run the LangGraph workflow for a debate (called as background task)."""
    debate = _debates.get(debate_id)
    if not debate:
        return

    req = debate["request"]

    # Build initial state for LangGraph
    initial_state = {
        "context": req.case.text,
        "agent_profile": [
            {"role": a.role.value, "llm_profile": a.llm_profile, "temperature": a.temperature}
            for a in req.agent_profile
        ],
        "max_rounds": req.max_rounds,
        "threshold": req.consensus_threshold,
        "enable_fact_check": req.enable_fact_check,
        "enable_memory": req.enable_memory,
        "rag_context": "",
        # --- Profile configuration (Sprint 3) ---
        "llm_profile_id": req.llm_profile_id,
        "prompt_variant": req.prompt_variant,
        "agent_persona_ids": req.agent_persona_ids,
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
        debate["status"] = DebateStatus.FAILED
        debate["updated_at"] = datetime.now(UTC)
        return

    # Update debate state
    debate["status"] = DebateStatus.COMPLETED
    debate["current_round"] = result.get("current_round", req.max_rounds)
    debate["rounds"] = result.get("rounds", [])
    debate["result"] = result
    debate["updated_at"] = datetime.now(UTC)

    # Record audit events
    for agent_output in result.get("agent_outputs", []):
        event = AuditEvent(
            debate_id=debate_id,
            round=result.get("current_round", 1),
            agent=agent_output["role"],
            action="agent_output",
            input_hash=str(hash(agent_output["content"][:100])),
            output_hash=str(hash(agent_output["content"])),
            llm_model=req.llm_profile_id,
            tokens_used=agent_output.get("tokens_used", 0),
        )
        audit.record(event)

    logger.info(
        "Debate %s completed: %d rounds, consensus=%.3f",
        debate_id, debate["current_round"], result.get("final_consensus", 0.0),
    )


# ---------------------------------------------------------------------------
# SSE endpoint — real-time streaming via event bus
# ---------------------------------------------------------------------------

async def _sse_events(debate_id: str):
    """Yield SSE events for a debate using the event bus."""
    debate = _debates.get(debate_id)
    if not debate:
        yield {"event": "error", "data": json.dumps({"detail": "Debate not found"})}
        return

    # Send initial status
    yield {
        "event": "status_change",
        "data": json.dumps({"debate_id": debate_id, "status": debate["status"].value}),
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
async def stream_debate(debate_id: str):
    """SSE endpoint for real-time debate updates."""
    return EventSourceResponse(_sse_events(debate_id))
