"""Input Composer API — endpoints for input plugin listing, submission, and job management.

Endpoints:
- GET  /api/v1/input-plugins                 — list input plugins
- POST /api/v1/input/submit                  — submit input
- GET  /api/v1/input/jobs/{job_id}           — job status
- DELETE /api/v1/input/jobs/{job_id}         — delete job
- POST /api/v1/input/stt/stream              — STT audio streaming (SSE)
- POST /api/v1/input/a2a/{task_id}/approve   — approve A2A request
- POST /api/v1/input/a2a/{task_id}/reject    — reject A2A request
- POST /api/v1/mcp/tools/call                — reserved for future MCP
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_debate_store_for_case, get_project_id
from backend.blueprints.compiler import CompilerService
from backend.blueprints.mvp_debate_canvas import _ensure_blueprint
from backend.blueprints.repository import BlueprintRepository
from backend.models.input_job import InputJobStatus
from backend.persistence.debate_store import DebateStatus
from backend.services.input.input_engine import InputComposerService
from backend.services.input.input_job_store import InputJobStore
from backend.services.input.registry import InputPluginRegistry
from backend.services.stt_service import STTService
from backend.workflow.state_snapshot import StateSnapshotStore
from backend.workflow.workflow_runner import (
    get_pause_event,
    set_session_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["input-composer"])

# Module-level singletons
_engine: InputComposerService | None = None
_job_store: InputJobStore | None = None
_repo: BlueprintRepository | None = None
_snapshot_store: StateSnapshotStore | None = None


def _get_engine() -> InputComposerService:
    """Return (or lazily create) engine."""
    global _engine
    if _engine is None:
        # Ensure plugins are imported (triggers @register_input_plugin)
        import backend.services.input.plugins  # noqa: F401

        _engine = InputComposerService()
    return _engine


def _get_job_store() -> InputJobStore:
    """Return (or lazily create) job store."""
    global _job_store
    if _job_store is None:
        _job_store = InputJobStore()
    return _job_store


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


class InputPluginInfo(BaseModel):
    """Information about a registered input plugin."""

    plugin_key: str
    plugin_name: str
    config_schema: dict[str, Any] = Field(description="JSON Schema for the plugin's config")
    ui_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="Frontend metadata (requires_microphone, supports_streaming, etc.)",
    )


class SubmitInputRequest(BaseModel):
    """Request body for submitting input."""

    plugin_key: str = Field(
        default="standard_text",
        description="Key of the input plugin to use",
    )
    config: dict = Field(
        default_factory=dict,
        description="Plugin-specific configuration",
    )
    topic: str = Field(
        default="",
        description="The debate topic / case description",
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional raw input data",
    )


class SubmitInputResponse(BaseModel):
    """Response after submitting input."""

    job_id: str
    plugin_key: str
    status: str


class InputJobStatusResponse(BaseModel):
    """Response for input job status query."""

    job_id: str
    plugin_key: str
    status: str
    processed_input: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: str
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/input-plugins", response_model=list[InputPluginInfo])
async def list_input_plugins() -> list[InputPluginInfo]:
    """List all registered input plugins with their config schemas and UI hints."""
    registry = InputPluginRegistry.instance()
    plugins = registry.list_plugins()
    result: list[InputPluginInfo] = []
    for p in plugins:
        try:
            instance = p()
            hints = instance.get_ui_hints()
        except Exception:
            hints = {}
        result.append(
            InputPluginInfo(
                plugin_key=p.plugin_key,
                plugin_name=p.plugin_name,
                config_schema=p.config_json_schema(),
                ui_hints=hints,
            )
        )
    return result


@router.post("/input/submit", response_model=SubmitInputResponse, status_code=202)
async def submit_input(body: SubmitInputRequest) -> SubmitInputResponse:
    """Submit input for processing by an Input Plugin."""
    engine = _get_engine()

    # Merge topic into raw_data
    raw_data = {**body.raw_data}
    if body.topic:
        raw_data["topic"] = body.topic

    try:
        job = await engine.submit_input(
            plugin_key=body.plugin_key,
            config=body.config,
            raw_data=raw_data,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return SubmitInputResponse(
        job_id=job.id,
        plugin_key=job.plugin_key,
        status=job.status.value,
    )


@router.get("/input/jobs", response_model=list[InputJobStatusResponse])
async def list_input_jobs(
    status: str | None = None,
    plugin_key: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[InputJobStatusResponse]:
    """List input jobs with optional filters.

    Query parameters:
    - ``status``: Filter by job status (queued, processing, completed, failed, pending_approval)
    - ``plugin_key``: Filter by plugin key (e.g. standard_text, a2a_inbound)
    - ``limit``: Max results (default 50)
    - ``offset``: Pagination offset (default 0)
    """
    store = _get_job_store()
    parsed_status = None
    if status is not None:
        try:
            parsed_status = InputJobStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{status}'. Valid: {[s.value for s in InputJobStatus]}",
            )
    jobs = store.list_jobs(
        plugin_key=plugin_key,
        status=parsed_status,
        limit=limit,
        offset=offset,
    )
    return [
        InputJobStatusResponse(
            job_id=j.id,
            plugin_key=j.plugin_key,
            status=j.status.value,
            processed_input=(j.processed_input.model_dump(mode="json") if j.processed_input else None),
            error_message=j.error_message,
            created_at=j.created_at.isoformat(),
            completed_at=j.completed_at.isoformat() if j.completed_at else None,
        )
        for j in jobs
    ]


@router.get("/input/jobs/{job_id}", response_model=InputJobStatusResponse)
async def get_input_job_status(job_id: str) -> InputJobStatusResponse:
    """Get the status and metadata of an input job."""
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Input job {job_id!r} not found")

    processed = None
    if job.processed_input:
        processed = job.processed_input.model_dump(mode="json")

    return InputJobStatusResponse(
        job_id=job.id,
        plugin_key=job.plugin_key,
        status=job.status.value,
        processed_input=processed,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.delete("/input/jobs/{job_id}", status_code=204)
async def delete_input_job(job_id: str) -> None:
    """Delete an input job."""
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Input job {job_id!r} not found")
    store.delete_job(job_id)


@router.post("/input/a2a/{task_id}/approve")
async def approve_a2a(task_id: str) -> dict:
    """Approve a pending A2A inbound request."""
    engine = _get_engine()
    try:
        job = await engine.approve_a2a(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {task_id!r} not found")
    return {"job_id": job.id, "status": job.status.value}


@router.post("/input/a2a/{task_id}/reject")
async def reject_a2a(task_id: str) -> dict:
    """Reject a pending A2A inbound request."""
    engine = _get_engine()
    try:
        job = await engine.reject_a2a(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {task_id!r} not found")
    return {"job_id": job.id, "status": job.status.value}


@router.post("/input/stt/stream")
async def stt_stream(request: Request) -> StreamingResponse:
    """STT audio streaming endpoint.

    Receives audio blobs via POST body and returns Server-Sent Events (SSE)
    with ``event: partial`` for intermediate results and ``event: final``
    for the completed transcript.

    The request body should be raw audio bytes (WebM/Opus or WAV).
    Query parameters:
    - ``profile_id``: LLM profile ID with protocol='stt' (optional, uses default)
    - ``language``: Language code (default: 'de')
    """
    # Read audio bytes from request body
    audio_bytes = await request.body()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio data provided")

    language = request.query_params.get("language", "de")

    # Get STT profile (for now, use a default local whisper config)
    # In the future, profile_id query param will select from blueprint_llm_profiles
    profile_type = type(
        "STTProfile",
        (),
        {"provider": "whisper-local", "model": "base"},
    )()

    stt_service = STTService()

    async def event_generator():
        """Yield SSE events for STT transcription."""
        try:
            # For now, we transcribe the full chunk and send as final
            # Future: implement streaming/chunked transcription for partial results
            transcript = await stt_service.transcribe_chunk(audio_bytes, profile_type, language)

            if transcript.strip():
                # Send partial event (simulated — full text as "partial")
                yield f"event: partial\ndata: {json.dumps({'text': transcript})}\n\n"

                # Send final event
                yield f"event: final\ndata: {json.dumps({'text': transcript})}\n\n"
            else:
                yield f"event: final\ndata: {json.dumps({'text': ''})}\n\n"

        except RuntimeError as exc:
            yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"
        except Exception as exc:
            logger.exception("STT streaming error")
            yield f"event: error\ndata: {json.dumps({'error': f'STT failed: {exc}'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/mcp/tools/call")
async def mcp_tools_call() -> dict:
    """Reserved endpoint for future MCP server integration.

    Currently returns 501 Not Implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="MCP tools/call is not yet implemented. This is a reserved endpoint.",
    )


# ---------------------------------------------------------------------------
# Input → Workflow bridge
# ---------------------------------------------------------------------------


class LaunchWorkflowRequest(BaseModel):
    """Request body for launching a workflow from a completed input job."""

    job_id: str = Field(..., description="InputJob ID (must have status=completed)")
    workflow_id: str | None = Field(
        default=None,
        description="WorkflowDefinition ID to execute. If omitted, uses workflow_template_id or first available active workflow.",
    )
    workflow_template_id: str | None = Field(
        default=None,
        description="WorkflowTemplate ID to instantiate into a WorkflowDefinition. Ignored if workflow_id is provided.",
    )
    max_rounds: int = Field(default=5, ge=1, le=50)
    consensus_threshold: float = Field(default=0.9, ge=0.0, le=1.0)
    language: str | None = Field(default=None, description="Language code (uses user preference if not set)")

    # DMS / RAG fields
    document_ids: list[str] = Field(
        default_factory=list,
        description="Document IDs to include as RAG context (explicit selection).",
    )
    rag_auto_retrieve: bool = Field(
        default=False,
        description="Automatically retrieve relevant chunks for the topic from project documents.",
    )
    include_debate_results: bool = Field(
        default=False,
        description="Include previous completed debate results in RAG context.",
    )
    debate_result_ids: list[str] | None = Field(
        default=None,
        description="Specific debate result IDs to include (if include_debate_results is True).",
    )
    include_document_analysis: bool = Field(
        default=False,
        description="Include LLM-generated document analysis in RAG context.",
    )


class LaunchWorkflowResponse(BaseModel):
    """Response after launching a workflow from input."""

    session_id: str
    status: str
    workflow_id: str
    debate_id: str | None = None
    title: str = ""


@router.post("/input/launch", response_model=LaunchWorkflowResponse)
async def launch_workflow_from_input(
    body: LaunchWorkflowRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
) -> LaunchWorkflowResponse:
    """Launch a workflow execution from a completed input job.

    Takes a completed InputJob (with its DebateInput artifact), resolves
    a workflow definition, and starts execution via the workflow runner.

    This bridges the Input Composer pipeline to the Workflow Execution
    pipeline — the missing link between input capture and debate execution.
    """
    job_store = _get_job_store()
    repo = _get_repo()
    snapshot_store = _get_snapshot_store()

    # 1. Load and validate the input job
    job = job_store.get_job(body.job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"InputJob '{body.job_id}' not found",
        )
    if job.status != InputJobStatus.COMPLETED:
        raise HTTPException(
            status_code=422,
            detail=f"InputJob '{body.job_id}' has status '{job.status}', expected 'completed'",
        )
    if job.processed_input is None:
        raise HTTPException(
            status_code=422,
            detail=f"InputJob '{body.job_id}' has no processed_input (DebateInput)",
        )

    debate_input = job.processed_input
    topic = debate_input.topic

    # 2. Resolve workflow definition
    workflow_id = body.workflow_id
    if workflow_id is None and body.workflow_template_id is not None:
        # Instantiate template into a WorkflowDefinition
        from backend.api.routers.workflow_templates import InstantiateRequest

        template = repo.get_workflow_template(body.workflow_template_id)
        if template is None:
            raise HTTPException(
                status_code=404,
                detail=f"WorkflowTemplate '{body.workflow_template_id}' not found",
            )

        # Use debate topic as name if no specific name is provided
        topic_name = topic[:80] if topic else f"Workflow from {body.job_id}"
        inst_req = InstantiateRequest(
            name=f"{topic_name} ({template.name})",
            placeholder_values={},
        )

        # Auto-resolve blueprint_ref placeholders with default AgentBlueprints
        for p in template.placeholders:
            if p.key not in inst_req.placeholder_values and p.type == "blueprint_ref":
                role = p.key.replace("_blueprint_id", "")
                try:
                    from backend.core.config import settings

                    default_llm = settings.service_llm_profile_id
                    if not default_llm or not repo.get_llm_profile(default_llm):
                        profiles = repo.list_llm_profiles(limit=1)
                        default_llm = profiles[0].id if profiles else "opencodezen-minimax-m2.5-free-ry6l"
                    bp = _ensure_blueprint(repo, role, default_llm)
                    inst_req.placeholder_values[p.key] = bp.id
                    logger.info(
                        "Auto-resolved placeholder '%s' → AgentBlueprint '%s' (LLM: %s)",
                        p.key,
                        bp.id,
                        default_llm,
                    )
                except Exception as exc:
                    logger.warning("Could not auto-resolve placeholder '%s': %s", p.key, exc)

        missing_keys = {p.key for p in template.placeholders if p.default is None and p.key not in inst_req.placeholder_values}
        if missing_keys:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "missing_placeholders",
                    "missing": sorted(missing_keys),
                    "message": f"Template '{template.name}' requires placeholder values: {', '.join(sorted(missing_keys))}",
                },
            )

        resolved_data = template.instantiate(inst_req.placeholder_values)

        # Build WorkflowDefinition

        wf_id = f"wf-{uuid.uuid4().hex[:8]}"
        from backend.blueprints.workflow_models import WorkflowDefinition

        try:
            workflow_def = WorkflowDefinition(
                id=wf_id,
                name=inst_req.name or template.name,
                description=f"Instantiated from template '{template.name}' via Input Composer",
                nodes=resolved_data.get("nodes", []),
                edges=resolved_data.get("edges", []),
                entry_point=resolved_data.get("entry_point"),
                termination_conditions=resolved_data.get("termination_conditions", []),
                template_id=body.workflow_template_id,
                is_active=True,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Instantiated template produces invalid workflow: {exc}",
            )
        repo.save_workflow_definition(workflow_def)
        workflow_id = wf_id
        logger.info(
            "Instantiated WorkflowTemplate '%s' into WorkflowDefinition '%s'",
            body.workflow_template_id,
            workflow_id,
        )

    if workflow_id is None:
        # Use the first available active workflow
        workflows = repo.list_workflow_definitions(limit=10)
        active = [w for w in workflows if w.is_active]
        if not active:
            raise HTTPException(
                status_code=422,
                detail="No active WorkflowDefinition found. Create a workflow in the Blueprint Canvas first.",
            )
        workflow_id = active[0].id
        logger.info(
            "No workflow_id specified, using first active: '%s' (%s)",
            active[0].name,
            workflow_id,
        )

    workflow = repo.get_workflow_definition(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=404,
            detail=f"WorkflowDefinition '{workflow_id}' not found",
        )

    # 3. Compile workflow
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

    # 4. Resolve RAG context from DMS
    rag_context = ""
    if project_id:
        try:
            from backend.services.debate_workflow import resolve_rag_context

            rag_context, _ = resolve_rag_context(
                project_id=project_id,
                case_text=topic,
                document_ids=body.document_ids or None,
                rag_auto_retrieve=body.rag_auto_retrieve,
                include_debate_results=body.include_debate_results,
                debate_result_ids=body.debate_result_ids or None,
                include_document_analysis=body.include_document_analysis,
            )
        except Exception:
            logger.warning("Failed to resolve RAG context for input-composer workflow", exc_info=True)
    logger.info(
        "RAG context resolved for input-composer workflow: %d chars",
        len(rag_context),
    )

    # 5. Generate session ID and title, then build initial state
    session_id = f"wf-{uuid.uuid4().hex[:12]}"

    wf_template_slug = ""
    if body.workflow_template_id:
        wf_template_slug = body.workflow_template_id.replace("tpl-", "").replace("-", "_")

    title = topic[:80] if topic else f"Input Job {body.job_id}"
    try:
        from backend.services.debate_workflow import generate_debate_title

        generated = await generate_debate_title(
            case_text=topic,
            llm_profile_id="",
            language=body.language or "de",
            project_id=project_id,
            use_service_llm=True,
        )
        if generated:
            title = generated
    except Exception:
        logger.warning("Title generation failed for input-composer workflow, using fallback", exc_info=True)

    initial_state: dict[str, Any] = {
        "workflow_id": workflow_id,
        "workflow_template": wf_template_slug,
        "session_id": session_id,
        "project_id": project_id,
        "title": title,
        "context": topic,
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
            }
            for agent in compiled.resolved_agents
        },
        "edge_map": {},
        "termination_conditions": [],
        "current_node_id": "",
        "current_round": 1,
        "max_rounds": body.max_rounds,
        "threshold": body.consensus_threshold,
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

    # 7. Create debate record so the workflow appears in Dashboard/Archive
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
                "request": {"case": {"text": topic}, "max_rounds": body.max_rounds},
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
        logger.info("Created debate record %s for input-composer session %s", debate_id, session_id)
    except Exception as e:
        logger.warning("Failed to create debate record for input-composer session %s: %s", session_id, e, exc_info=True)

    initial_state["debate_id"] = debate_id

    # 8. Launch as background task
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

    logger.info(
        "Launched workflow '%s' from InputJob '%s' (plugin=%s) as session '%s' (debate %s)",
        workflow_id,
        body.job_id,
        job.plugin_key,
        session_id,
        debate_id,
    )

    return LaunchWorkflowResponse(
        session_id=session_id,
        status="running",
        workflow_id=workflow_id,
        debate_id=debate_id,
        title=title,
    )
