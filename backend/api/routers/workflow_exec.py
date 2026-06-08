"""Workflow Execution - API router for running workflows and interjections.

Endpoints:
- POST /{workflow_id}/start - starts workflow execution
- GET /{session_id}/state - returns current execution state
- POST /{session_id}/pause - pauses execution
- POST /{session_id}/resume - resumes execution
- POST /{session_id}/cancel - cancels execution

.. deprecated::
    These routes are deprecated. Use ``/api/v1/tenants/{tid}/cases/{cid}/workflows/``
    instead. Legacy routes will be removed in a future version.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from backend.api.deps import get_debate_store_for_case, get_project_id
from backend.api.events import publish_async, subscribe, unsubscribe
from backend.blueprints.compiler import CompilerService
from backend.blueprints.repository import BlueprintRepository
from backend.models.schemas import SearchMode
from backend.persistence.debate_store import DebateStatus
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
    set_session_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workflow-exec"])

# Shared instances — initialized lazily or via dependency injection
_repo: BlueprintRepository | None = None
_snapshot_store: StateSnapshotStore | None = None


def _get_repo() -> BlueprintRepository:
    """Return (or lazily create) repo."""
    global _repo
    if _repo is None:
        _repo = BlueprintRepository()
    return _repo


def _get_snapshot_store() -> StateSnapshotStore:
    """Return (or lazily create) snapshot store."""
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
    language: str | None = Field(default=None, description="Language code (uses user preference if not set)")
    project_id: str = Field(default="_default", description="Project ID")
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
    include_document_analysis: bool = Field(
        default=False,
        description="Include AI-generated document analysis in RAG context (may leak data from other cases in the same project)",
    )


class StartWorkflowResponse(BaseModel):
    """Response after starting a workflow."""

    session_id: str
    status: str = "running"
    debate_id: str | None = None
    workflow_id: str | None = None
    workflow_name: str | None = None
    context: str | None = None


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


class StartMvpDebateRequest(BaseModel):
    """Request body for starting an MVP debate with per-agent LLM profiles."""

    context: str = Field(..., min_length=1, description="The debate topic / context")
    language: str | None = Field(default=None, description="Language code (uses user preference if not set)")
    project_id: str = Field(default="_default", description="Project ID")
    max_rounds: int = Field(default=5, ge=1, description="Maximum rounds")
    threshold: float = Field(default=0.9, ge=0.0, le=1.0, description="Consensus threshold")
    llm_profile_ids: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of role → llm_profile_id for per-agent LLM assignment",
    )
    agent_core_ids: dict[str, str] = Field(
        default_factory=dict,
        description="[Phase 2] Mapping of role → agent-core module ID. Composed with other components via ComposerService.",
    )
    argumentation_pattern_ids: dict[str, str] = Field(
        default_factory=dict,
        description="[Phase 2] Mapping of role → argumentation-pattern module ID.",
    )
    tone_profile_ids: dict[str, str] = Field(
        default_factory=dict,
        description="[Phase 2] Mapping of role → tone-profile module ID.",
    )
    prompt_modifier_ids: dict[str, str] = Field(
        default_factory=dict,
        description="[Phase 2] Mapping of role → prompt-modifier module ID.",
    )

    # --- Web search ---
    search_mode: SearchMode = Field(
        default=SearchMode.OFF,
        description="Web search mode: 'off', 'optional', or 'required'",
    )

    # --- DMS / RAG ---
    document_ids: list[str] = Field(
        default_factory=list,
        description="DMS document IDs to include as RAG context",
    )
    rag_auto_retrieve: bool = Field(
        default=False,
        description="Automatically retrieve relevant document chunks based on context",
    )

    # --- Previous debate context ---
    include_debate_results: bool = Field(
        default=False,
        description="Include results from previous completed debates as RAG context",
    )
    include_document_analysis: bool = Field(
        default=False,
        description="Include AI-generated document analysis in RAG context (may contain data from other cases in the same project)",
    )
    debate_result_ids: list[str] = Field(
        default_factory=list,
        description="Specific debate IDs to include when include_debate_results is true. If empty, auto-selects up to 5 recent completed debates.",
    )

    # --- Extra rounds ---
    enable_extra_rounds: bool = Field(
        default=False,
        description="If true, allow requesting additional rounds when consensus is not reached",
    )


class StartMvpDebateResponse(BaseModel):
    """Response after starting an MVP debate."""

    session_id: str
    debate_id: str
    workflow_id: str
    status: str = "running"
    title: str = ""
    llm_assignments: dict[str, str] = Field(
        description="Mapping of role → llm_profile_id actually used",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/mvp/start", response_model=StartMvpDebateResponse)
async def start_mvp_debate(
    body: StartMvpDebateRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
) -> StartMvpDebateResponse:
    """Create and execute an MVP debate workflow with per-agent LLM profiles.

    Builds a 4-agent debate (strategist → critic → optimizer → moderator)
    where each agent uses its own dedicated LLM profile, compiles it via
    WorkflowCompiler, and launches execution as a background task.
    """
    from backend.blueprints.mvp_debate_canvas import build_mvp_debate_workflow

    repo = _get_repo()
    snapshot_store = _get_snapshot_store()

    # Normalize LLM profile IDs: strip 'llm-' prefix if present (module dir name vs DB ID)
    llm_ids = body.llm_profile_ids or {}
    normalized_ids = {}
    for role, pid in llm_ids.items():
        normalized_ids[role] = pid.removeprefix("llm-") if pid else pid

    wf = build_mvp_debate_workflow(
        repo,
        llm_profile_ids=normalized_ids or None,
        max_rounds=body.max_rounds,
        consensus_threshold=body.threshold,
    )

    compiler = CompilerService(repo)
    compiled = compiler.compile_to_langgraph(wf)

    if not compiled.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "MVP debate compilation failed",
                "errors": compiled.errors,
                "warnings": compiled.warnings,
            },
        )

    session_id = f"wf-{uuid.uuid4().hex[:12]}"

    # Use project_id from header (same as all other endpoints) for RAG context & debate store
    effective_project_id = project_id

    rag_context = ""
    if effective_project_id:
        try:
            from backend.services.debate_workflow import resolve_rag_context

            rag_context, _ = resolve_rag_context(
                project_id=effective_project_id,
                case_text=body.context,
                document_ids=body.document_ids or None,
                rag_auto_retrieve=body.rag_auto_retrieve,
                include_debate_results=body.include_debate_results,
                debate_result_ids=body.debate_result_ids or None,
                include_document_analysis=body.include_document_analysis,
            )
        except Exception:
            logger.warning("Failed to resolve RAG context for MVP debate", exc_info=True)

    logger.info(
        "MVP debate RAG context for project %s: %d chars",
        effective_project_id,
        len(rag_context),
    )

    llm_assignments = {agent.node_id.replace("node-", ""): agent.llm_profile_id for agent in compiled.resolved_agents}

    # --- Phase 2: Compose system_prompt from up to 4 modular components ---
    from backend.services.composer_service import ComposerService, Composition

    composer = ComposerService()
    node_configs: dict[str, dict] = {}
    for agent in compiled.resolved_agents:
        role = agent.node_id.replace("node-", "")
        cfg: dict = {
            "blueprint_id": agent.blueprint_id,
            "blueprint_name": agent.blueprint_name,
            "llm_profile_id": agent.llm_profile_id,
            "llm_model": agent.llm_model,
            "llm_profile_name": agent.llm_profile_name,
            "role_definition_id": agent.role_definition_id,
            "role": agent.role,
            "role_type_name": agent.role_type_name,
            "role_type_icon": agent.role_type_icon,
            "role_type_color": agent.role_type_color,
            "default_max_rounds": agent.default_max_rounds,
            "default_consensus_threshold": agent.default_consensus_threshold,
            "argumentation_pattern": agent.argumentation_pattern,
            "mode": agent.mode,
            "system_prompt": agent.system_prompt,
        }
        # Compose system_prompt from selected components (if any provided)
        composition = Composition(
            agent_core_id=body.agent_core_ids.get(role, ""),
            argumentation_pattern_id=body.argumentation_pattern_ids.get(role, ""),
            tone_profile_id=body.tone_profile_ids.get(role, ""),
            prompt_modifier_id=body.prompt_modifier_ids.get(role, ""),
        )
        composed = composer.compose(composition)
        if composed:
            cfg["system_prompt"] = composed
            logger.info(
                "Composed system_prompt for role '%s' from agent_core=%s pattern=%s tone=%s modifier=%s (%d chars)",
                role,
                composition.agent_core_id or "(default)",
                composition.argumentation_pattern_id or "(none)",
                composition.tone_profile_id or "(none)",
                composition.prompt_modifier_id or "(none)",
                len(composed),
            )
        node_configs[agent.node_id] = cfg

    title = body.context[:80]
    try:
        from backend.services.debate_workflow import generate_debate_title

        generated = await generate_debate_title(
            case_text=body.context,
            llm_profile_id="",
            language=body.language,
            project_id=effective_project_id,
            use_service_llm=True,
        )
        if generated:
            title = generated
    except Exception:
        logger.warning("MVP title generation failed, using fallback", exc_info=True)

    initial_state: dict[str, Any] = {
        "workflow_id": wf.id,
        "session_id": session_id,
        "project_id": effective_project_id,
        "title": title,
        "context": body.context,
        "language": body.language,
        "search_mode": body.search_mode.value,
        "rag_context": rag_context,
        "node_sequence": compiled.node_sequence,
        "node_configs": node_configs,
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
        "enable_extra_rounds": body.enable_extra_rounds,
        "extension_granted": None,
    }

    set_session_status(session_id, "running")

    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    try:
        debate_store = get_debate_store_for_case(effective_project_id)
        debate_store.put(
            debate_id,
            {
                "debate_id": debate_id,
                "session_id": session_id,
                "status": DebateStatus.RUNNING,
                "title": title,
                "request": {"case": {"text": body.context}, "max_rounds": body.max_rounds},
                "max_rounds": body.max_rounds,
                "current_round": 0,
                "rounds": [],
                "created_at": now,
                "updated_at": now,
                "result": None,
                "is_mvp": True,
                "llm_assignments": llm_assignments,
            },
        )
        logger.info("Created MVP debate record %s for session %s", debate_id, session_id)
    except Exception as e:
        logger.warning("Failed to create debate record for MVP session %s: %s", session_id, e, exc_info=True)

    initial_state["debate_id"] = debate_id

    from backend.tasks.dispatch import dispatch_workflow_task

    dispatch_workflow_task(
        background_tasks,
        session_id=session_id,
        workflow_id=wf.id,
        project_id=effective_project_id,
        initial_state=initial_state,
        compiled_workflow=compiled,
        snapshot_store=snapshot_store,
    )

    logger.info(
        "Started MVP debate %s as session %s (debate_id=%s) with LLM assignments: %s",
        wf.id,
        session_id,
        debate_id,
        llm_assignments,
    )
    return StartMvpDebateResponse(
        session_id=session_id,
        debate_id=debate_id,
        workflow_id=wf.id,
        status="running",
        title=title,
        llm_assignments=llm_assignments,
    )


@router.post("/{workflow_id}/start", response_model=StartWorkflowResponse)
async def start_workflow(
    workflow_id: str,
    body: StartWorkflowRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
) -> StartWorkflowResponse:
    """Start executing a workflow definition.

    Uses the project_id from the X-Project-Id header (not the body)
    to ensure debate records are stored in the correct project.
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
            from backend.services.debate_workflow import resolve_rag_context

            rag_context, _ = resolve_rag_context(
                project_id=project_id,
                case_text=body.context,
                document_ids=body.document_ids,
                rag_auto_retrieve=body.rag_auto_retrieve,
                include_document_analysis=body.include_document_analysis,
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

    title = body.context[:80]
    try:
        from backend.services.debate_workflow import generate_debate_title

        generated = await generate_debate_title(
            case_text=body.context,
            llm_profile_id="",
            language=body.language,
            project_id=project_id,
            use_service_llm=True,
        )
        if generated:
            title = generated
    except Exception:
        logger.warning("Title generation failed for workflow, using fallback", exc_info=True)

    # Build initial state
    initial_state: dict[str, Any] = {
        "workflow_id": workflow_id,
        "session_id": session_id,
        "project_id": project_id,
        "title": title,
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
                "llm_profile_name": agent.llm_profile_name,
                "role_definition_id": agent.role_definition_id,
                "role": agent.role,
                "role_type_name": agent.role_type_name,
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

    # Create debate record so the workflow appears in Dashboard/Archive
    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    try:
        debate_store = get_debate_store_for_case(project_id)
        debate_store.put(
            debate_id,
            {
                "debate_id": debate_id,
                "session_id": session_id,
                "status": DebateStatus.RUNNING,
                "title": title,
                "request": {"case": {"text": body.context}, "max_rounds": body.max_rounds},
                "max_rounds": body.max_rounds,
                "current_round": 0,
                "rounds": [],
                "created_at": now,
                "updated_at": now,
                "result": None,
                "is_mvp": True,
                "workflow_id": workflow_id,
                "workflow_name": workflow.name,
            },
        )
        logger.info("Created debate record %s for workflow session %s", debate_id, session_id)
    except Exception as e:
        logger.warning("Failed to create debate record for workflow session %s: %s", session_id, e, exc_info=True)

    initial_state["debate_id"] = debate_id

    # Launch as background task (dispatches to Celery if available, else BackgroundTasks)
    from backend.tasks.dispatch import dispatch_workflow_task

    dispatch_workflow_task(
        background_tasks,
        session_id=session_id,
        workflow_id=workflow_id,
        project_id=project_id,
        initial_state=initial_state,
        compiled_workflow=compiled,
        snapshot_store=snapshot_store,
    )

    logger.info("Started workflow %s as session %s (debate %s)", workflow_id, session_id, debate_id)
    return StartWorkflowResponse(
        session_id=session_id,
        status="running",
        debate_id=debate_id,
        workflow_id=workflow_id,
        workflow_name=workflow.name,
        context=body.context,
    )


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
        """Event generator the instance."""
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
                    event_type, payload = await asyncio.wait_for(queue.get(), timeout=300.0)
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
    # DIAGNOSTIC: Check session status at interject time
    current_status = get_session_status(session_id)
    logger.info(
        "DIAG interject endpoint: session=%s status=%s content_preview=%r",
        session_id,
        current_status,
        body.content[:80],
    )
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
# Audit log retrieval
# ---------------------------------------------------------------------------


@router.get("/{session_id}/audit-log")
async def get_workflow_audit_log(
    session_id: str,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Return audit log entries for a workflow session.

    Used by the frontend to display the audit trail for MVP debates.
    """
    from backend.models.schemas import AuditLogQuery
    from backend.workflow.audit_logger import get_audit_logger

    al = get_audit_logger()
    filters = AuditLogQuery(
        event_type=event_type,
        limit=limit,
        offset=offset,
    )
    events = al.get_audit_log(session_id, filters)

    # Build enrichment maps from state snapshot
    from backend.workflow.report_generator import (
        _build_audit_context_map,
        _build_node_llm_name_map,
        _format_audit_content,
    )

    llm_name_map = _build_node_llm_name_map(session_id)
    ctx_map = _build_audit_context_map(session_id)

    # Transform to a format compatible with the AuditView
    result = []
    for entry in events:
        node_id = entry.get("node_id", "")
        llm_pid = entry.get("llm_profile_id", "")
        llm_display = llm_name_map.get(node_id, "") or llm_pid
        ctx = ctx_map.get(node_id, {})
        output_content = entry.get("output_content", "")
        event_type = entry.get("event_type", "")
        result.append(
            {
                "session_id": entry.get("session_id"),
                "workflow_id": entry.get("workflow_id"),
                "event_type": event_type,
                "node_id": node_id,
                "actor": entry.get("actor"),
                "timestamp": entry.get("timestamp"),
                "input_content": entry.get("input_content", ""),
                "output_content": output_content,
                "content_formatted": _format_audit_content(output_content, event_type),
                "round": ctx.get("round"),
                "phase": ctx.get("phase", ""),
                "llm_profile_id": llm_pid,
                "llm_profile_name": llm_display,
                "latency_ms": entry.get("latency_ms"),
                "prompt_tokens": entry.get("prompt_tokens"),
                "completion_tokens": entry.get("completion_tokens"),
            }
        )

    return result


@router.get("/{session_id}/phase-snapshots")
async def get_phase_snapshots(session_id: str) -> list[dict]:
    """Return phase-level state snapshots for a workflow session.

    Phase snapshots are saved at gate nodes and provide a state
    checkpoint for each phase boundary, useful for debugging and
    comparing state before/after phase transitions.
    """
    snapshot_store = _get_snapshot_store()
    snapshots = snapshot_store.get_by_type(session_id, "phase_checkpoint")
    # Strip the heavy state dict from the list view — include only metadata
    result = []
    for snap in snapshots:
        result.append(
            {
                "id": snap.get("id"),
                "session_id": snap.get("session_id"),
                "node_id": snap.get("node_id"),
                "node_type": snap.get("node_type"),
                "round_number": snap.get("round_number"),
                "created_at": snap.get("created_at"),
                "state_keys": list(snap.get("state", {}).keys()),
            }
        )
    return result


@router.get("/{session_id}/phase-snapshots/{node_id:path}")
async def get_phase_snapshot_detail(session_id: str, node_id: str) -> dict | None:
    """Return the full state for a specific phase checkpoint."""
    snapshot_store = _get_snapshot_store()
    snap = snapshot_store.get_by_node(session_id, node_id)
    if snap is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Phase snapshot '{node_id}' not found")
    return snap


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
