"""Workflow Execution — API router for running workflows and interjections.

Endpoints:
- POST /{workflow_id}/start — starts workflow execution
- GET /{session_id}/state — returns current execution state
- POST /{session_id}/pause — pauses execution
- POST /{session_id}/resume — resumes execution
- POST /{session_id}/cancel — cancels execution
- GET /{session_id}/stream — SSE endpoint for real-time events
- POST /{session_id}/interject — submit a user interjection during execution
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import EventSourceResponse
from pydantic import BaseModel, Field

from backend.api.events import publish_async, subscribe, unsubscribe
from backend.blueprints.compiler import CompilerService
from backend.blueprints.repository import BlueprintRepository
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.immutability import archive_session, guard_mutable, restore_session
from backend.workflow.interjection import interjection_service
from backend.workflow.state_snapshot import StateSnapshotStore
from backend.workflow.workflow_runner import (
    cancel_session,
    get_pause_event,
    get_session_status,
    pause_session,
    resume_session,
    run_workflow_background,
    set_session_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow-exec"])

# Shared instances — initialized lazily or via dependency injection
_repo: BlueprintRepository | None = None
_snapshot_store: StateSnapshotStore | None = None


def _get_repo() -> BlueprintRepository:
    global _repo
    if _repo is None:
        _repo = BlueprintRepository()
    return _repo


def _get_snapshot_store() -> StateSnapshotStore:
    global _snapshot_store
    if _snapshot_store is None:
        _snapshot_store = StateSnapshotStore()
    return _snapshot_store


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartWorkflowRequest(BaseModel):
    """Request body for starting a workflow."""

    context: str = Field(..., min_length=1, description="The debate topic / context")
    language: str = Field(default="de", description="Language code")
    project_id: str = Field(default="default", description="Project ID")
    max_rounds: int = Field(default=10, ge=1, description="Maximum rounds")
    threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Consensus threshold")
    document_ids: list[str] = Field(
        default_factory=list,
        description="DMS document IDs to include as RAG context",
    )
    rag_auto_retrieve: bool = Field(
        default=False,
        description="Automatically retrieve relevant document chunks based on context",
    )


class StartWorkflowResponse(BaseModel):
    """Response after starting a workflow."""

    session_id: str
    status: str = "running"


class SessionStateResponse(BaseModel):
    """Response for session state query."""

    session_id: str
    status: str
    workflow_id: str | None = None
    current_node_id: str | None = None
    current_round: int = 0
    node_outputs: list[dict[str, Any]] = Field(default_factory=list)
    output: str | None = None
    final_consensus: float | None = None


class StatusResponse(BaseModel):
    """Generic status response."""

    session_id: str
    status: str


class InterjectRequest(BaseModel):
    """Request body for submitting an interjection."""

    content: str = Field(..., min_length=1, description="The interjection text")
    source: str = Field(
        default="user",
        description="Origin of the interjection (user, system, api)",
    )
    metadata: dict = Field(default_factory=dict, description="Optional metadata")


class InterjectResponse(BaseModel):
    """Response after submitting an interjection."""

    interjection_id: str
    status: str = "queued"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{workflow_id}/start", response_model=StartWorkflowResponse)
async def start_workflow(
    workflow_id: str,
    body: StartWorkflowRequest,
    background_tasks: BackgroundTasks,
) -> StartWorkflowResponse:
    """Start executing a workflow definition.

    Loads the WorkflowDefinition from the repository, compiles it into
    a LangGraph StateGraph, builds the initial state, and launches
    the execution as a background task.
    """
    repo = _get_repo()
    snapshot_store = _get_snapshot_store()

    # Load workflow definition
    workflow = repo.get_workflow_definition(workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")

    # Compile to LangGraph
    compiler = CompilerService(repo)
    compiled = compiler.compile_to_langgraph(workflow)

    if not compiled.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Workflow compilation failed",
                "errors": compiled.errors,
                "warnings": compiled.warnings,
            },
        )

    # Generate session ID
    session_id = f"wf-{uuid.uuid4().hex[:12]}"

    # Resolve RAG context
    rag_context = ""
    if body.document_ids or body.rag_auto_retrieve:
        try:
            from backend.api.routers.debate import _resolve_rag_context
            rag_context, _ = _resolve_rag_context(
                project_id=body.project_id,
                case_text=body.context,
                document_ids=body.document_ids,
                rag_auto_retrieve=body.rag_auto_retrieve,
            )
            if rag_context:
                logger.info(
                    "RAG context resolved for workflow %s (%d chars)",
                    workflow_id,
                    len(rag_context),
                )
        except Exception:
            logger.warning(
                "Failed to resolve RAG context for workflow %s",
                workflow_id,
                exc_info=True,
            )

    # Build initial state
    initial_state: dict[str, Any] = {
        "workflow_id": workflow_id,
        "session_id": session_id,
        "project_id": body.project_id,
        "context": body.context,
        "language": body.language,
        "rag_context": rag_context,
        "node_sequence": compiled.node_sequence,
        "node_configs": {
            agent.node_id: {
                "blueprint_id": agent.blueprint_id,
                "blueprint_name": agent.blueprint_name,
                "llm_profile_id": agent.llm_profile_id,
                "llm_model": agent.llm_model,
                "role_definition_id": agent.role_definition_id,
                "role": agent.role,
                "prompt_template_id": agent.prompt_template_id,
            }
            for agent in compiled.resolved_agents
        },
        "edge_map": {},
        "termination_conditions": [],
        "current_node_id": "",
        "current_round": 1,
        "max_rounds": body.max_rounds,
        "threshold": body.threshold,
        "node_outputs": [],
        "messages": [],
        "current_draft": "",
        "interjection_queue": [],
        "consumed_interjections": [],
        "final_consensus": 0.0,
        "output": "",
        "status": "running",
        "is_paused": False,
        "pause_event": get_pause_event(session_id),
    }

    set_session_status(session_id, "running")

    # Launch as background task
    background_tasks.add_task(
        run_workflow_background,
        session_id=session_id,
        workflow_id=workflow_id,
        project_id=body.project_id,
        initial_state=initial_state,
        compiled_workflow=compiled,
        snapshot_store=snapshot_store,
    )

    logger.info("Started workflow %s as session %s", workflow_id, session_id)
    return StartWorkflowResponse(session_id=session_id, status="running")


@router.get("/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(session_id: str) -> SessionStateResponse:
    """Get the current execution state for a workflow session.

    Returns the latest state snapshot from SQLite.
    """
    snapshot_store = _get_snapshot_store()
    status = get_session_status(session_id)

    if status == "unknown":
        # Try to load from snapshot store
        snapshot = snapshot_store.get_latest(session_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
        state = snapshot.get("state", {})
        return SessionStateResponse(
            session_id=session_id,
            status=state.get("status", "unknown"),
            workflow_id=snapshot.get("workflow_id"),
            current_node_id=snapshot.get("node_id"),
            current_round=snapshot.get("round_number", 0),
            node_outputs=state.get("node_outputs", []),
            output=state.get("output"),
            final_consensus=state.get("final_consensus"),
        )

    # Load latest snapshot for running/paused sessions
    snapshot = snapshot_store.get_latest(session_id)
    state = snapshot.get("state", {}) if snapshot else {}

    return SessionStateResponse(
        session_id=session_id,
        status=status,
        workflow_id=snapshot.get("workflow_id") if snapshot else None,
        current_node_id=snapshot.get("node_id") if snapshot else None,
        current_round=snapshot.get("round_number", 0) if snapshot else 0,
        node_outputs=state.get("node_outputs", []),
        output=state.get("output"),
        final_consensus=state.get("final_consensus"),
    )


@router.post("/{session_id}/pause", response_model=StatusResponse)
async def pause_workflow(session_id: str) -> StatusResponse:
    """Pause a running workflow.

    Sets the pause flag; the workflow will check this between nodes.
    """
    guard_mutable(session_id)
    status = get_session_status(session_id)
    if status not in ("running",):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot pause session in status '{status}'",
        )

    pause_session(session_id)
    logger.info("Paused session %s", session_id)
    return StatusResponse(session_id=session_id, status="paused")


@router.post("/{session_id}/resume", response_model=StatusResponse)
async def resume_workflow(session_id: str) -> StatusResponse:
    """Resume a paused workflow.

    Clears the pause flag and signals the pause event.
    """
    guard_mutable(session_id)
    status = get_session_status(session_id)
    if status != "paused":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot resume session in status '{status}'",
        )

    resume_session(session_id)
    logger.info("Resumed session %s", session_id)
    return StatusResponse(session_id=session_id, status="running")


@router.post("/{session_id}/cancel", response_model=StatusResponse)
async def cancel_workflow(session_id: str) -> StatusResponse:
    """Cancel a running or paused workflow.

    Sets a cancellation flag that the workflow checks between nodes.
    Idempotent: if already completed/failed/cancelled, returns current status.
    """
    guard_mutable(session_id)
    status = get_session_status(session_id)
    if status in ("completed", "failed", "cancelled"):
        return StatusResponse(session_id=session_id, status=status)

    cancel_session(session_id)

    # Also resume if paused, so the workflow can exit
    resume_session(session_id)

    logger.info("Cancelled session %s", session_id)
    return StatusResponse(session_id=session_id, status="cancelled")


@router.get("/{session_id}/stream")
async def stream_workflow_events(session_id: str) -> EventSourceResponse:
    """SSE endpoint for real-time workflow execution events.

    Subscribes to the event bus and yields events as they are published
    by workflow nodes.
    """
    status = get_session_status(session_id)

    async def event_generator():
        # Send initial status
        yield {
            "event": "status",
            "data": json.dumps({"session_id": session_id, "status": status}),
        }

        # If already terminal, just return
        if status in ("completed", "failed", "cancelled"):
            return

        # Subscribe to event bus
        queue = subscribe(session_id)
        try:
            while True:
                try:
                    event_type, payload = await asyncio.wait_for(
                        queue.get(), timeout=300.0
                    )
                    yield {"event": event_type, "data": payload}

                    # Stop on terminal events
                    if event_type in ("workflow.complete", "node.error"):
                        break
                except TimeoutError:
                    # Send keepalive
                    yield {"event": "ping", "data": "{}"}
        finally:
            unsubscribe(session_id, queue)

    return EventSourceResponse(event_generator())


@router.post("/{session_id}/interject", response_model=InterjectResponse)
async def submit_interjection(
    session_id: str,
    body: InterjectRequest,
) -> InterjectResponse:
    """Submit a user interjection for a running workflow session.

    The interjection is queued and will be consumed by the next
    interjection node in the workflow graph.  Emits an SSE event
    for frontend visualization.
    """
    guard_mutable(session_id)
    interjection_id = await interjection_service.submit(
        session_id=session_id,
        content=body.content,
        source=body.source,
        metadata=body.metadata,
    )

    # Emit SSE event for frontend visualization
    await publish_async(
        session_id,
        "interjection.received",
        {
            "type": "interjection.received",
            "interjection_id": interjection_id,
            "content": body.content,
            "source": body.source,
        },
    )

    # --- Audit log ---
    try:
        get_audit_logger().log_interjection(
            session_id=session_id,
            workflow_id="",
            workflow_version=1,
            actor=body.source,
            content=body.content,
            metadata={"interjection_id": interjection_id, **(body.metadata or {})},
        )
    except Exception:
        logger.debug("Audit logging failed for interjection", exc_info=True)

    logger.info("Interjection %s queued for session %s", interjection_id, session_id)
    return InterjectResponse(
        interjection_id=interjection_id,
        status="queued",
    )


# ---------------------------------------------------------------------------
# Session soft-delete / restore
# ---------------------------------------------------------------------------


@router.delete("/{session_id}", response_model=StatusResponse)
async def archive_workflow_session(session_id: str) -> StatusResponse:
    """Soft-delete a workflow session (sets ``is_archived = 1``).

    The session data is preserved but excluded from default listings.
    Use ``POST /{session_id}/restore`` to un-archive.
    """
    guard_mutable(session_id)
    archive_session(session_id)
    logger.info("Archived session %s", session_id)
    return StatusResponse(session_id=session_id, status="archived")


@router.post("/{session_id}/restore", response_model=StatusResponse)
async def restore_workflow_session(session_id: str) -> StatusResponse:
    """Restore an archived workflow session (sets ``is_archived = 0``)."""
    restored = restore_session(session_id)
    if not restored:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found",
        )
    logger.info("Restored session %s", session_id)
    return StatusResponse(session_id=session_id, status="restored")
