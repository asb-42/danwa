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
from pydantic import BaseModel, Field

from backend.api.deps import (
    get_audit_service,
    get_debate_store_for_project,
    get_project_id,
    get_project_store,
)
from backend.api.events import publish_async
from backend.models.schemas import (
    DebateContinueBody,
    DebateListItem,
    DebateRequest,
    DebateResponse,
    DebateStatus,
    DebateStatusResponse,
    ForkDebateBody,
    ForkFromConsensusBody,
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
            )
        )

    return items[offset : offset + limit]


@router.get("/cross-project/running")
async def find_running_debate_across_projects(
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateListItem | None:
    """Find the first running debate across ALL projects.

    Used by the Dashboard to detect externally-started debates (e.g. via A2A)
    that may live in a different project than the active one.
    """
    for project in project_store.list_all():
        try:
            store = get_debate_store_for_project(project.id, project_store)
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
    rag_preview = build_rag_preview(project_id, document_ids, project_store) if document_ids else ""

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

    background_tasks.add_task(run_debate_workflow, debate_id, project_id, audit, store, project_store)

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
    llm_profile_id: str = Field(default="openrouter-claude")


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
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateResponse:
    """Start a debate directly from a canvas layout.

    Converts the layout to a WorkflowDefinition, creates a debate with
    bundle-resolved agent profiles, and launches the workflow.
    """
    from backend.api.deps import get_blueprint_repository
    from backend.blueprints.canvas_to_workflow import CanvasToWorkflowConverter, ConversionError
    from backend.blueprints.repository import BlueprintRepository
    from backend.services.debate_workflow import run_debate_workflow

    repo = get_blueprint_repository()
    store = get_debate_store_for_project(project_id, project_store)

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
    from backend.models.schemas import AgentConfig, CaseInput
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

    background_tasks.add_task(run_debate_workflow, debate_id, project_id, audit, store, project_store)

    return DebateResponse(debate_id=debate_id, status=DebateStatus.RUNNING, title="", created_at=now)


@router.post("/from-workflow/{workflow_id}", response_model=DebateResponse, status_code=201)
async def start_debate_from_workflow(
    workflow_id: str,
    body: StartFromWorkflowBody,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
    audit: AuditService = Depends(get_audit_service),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateResponse:
    """Start a debate from an existing WorkflowDefinition.

    The workflow's wf-agent nodes (with bundle_id references) are resolved
    during execution via the WorkflowCompiler.
    """
    from backend.api.deps import get_blueprint_repository
    from backend.blueprints.repository import BlueprintRepository
    from backend.services.debate_workflow import run_debate_workflow

    repo = get_blueprint_repository()
    store = get_debate_store_for_project(project_id, project_store)

    wf = repo.get_workflow_definition(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow definition not found")

    # Extract bundle_ids from wf-agent nodes
    bundle_ids = [n.bundle_id for n in wf.nodes if n.type == "wf-agent" and n.bundle_id]

    from backend.models.schemas import AgentConfig, CaseInput
    from backend.models.schemas import DebateRequest as ReqModel

    request = ReqModel(
        case=CaseInput(text=body.case_text),
        agent_profile=[],
        bundle_ids=bundle_ids,
        max_rounds=body.max_rounds,
        consensus_threshold=body.consensus_threshold,
        language=body.language,
    )

    debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

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

    background_tasks.add_task(run_debate_workflow, debate_id, project_id, audit, store, project_store)

    return DebateResponse(debate_id=debate_id, status=DebateStatus.RUNNING, title="", created_at=now)


# ---------------------------------------------------------------------------
# Continue Debate (P0)
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/continue", response_model=DebateResponse)
async def continue_debate(
    debate_id: str,
    body: DebateContinueBody,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateResponse:
    """Start a new debate continuing from a completed one (P0).

    The previous debate's results are used as context for the new case text.
    """
    from backend.services.debate_workflow import build_followup_case

    # Find the debate in the project's store
    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status_val = debate.get("status", "")
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val not in ("completed", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot continue debate with status '{status_val}'. Only completed or failed debates can be continued.",
        )

    # Build the follow-up case text from the previous debate
    followup_prompt = build_followup_case(debate_id, body.focus_topic, store=store)

    # Determine inherited settings
    req = debate.get("request", {})
    if isinstance(req, dict):
        inherit_llm = req.get("llm_profile_id", "openrouter-claude")
        inherit_personas = req.get("agent_persona_ids", {})
        inherit_prompt_variant = req.get("prompt_variant", "default")
        inherit_max_rounds = req.get("max_rounds", 3)
        inherit_consensus_threshold = req.get("consensus_threshold", 0.8)
        inherit_search_mode = req.get("search_mode", "off")
        inherit_language = req.get("language", "de")
        inherit_enable_extra_rounds = req.get("enable_extra_rounds", False)
    else:
        inherit_llm = getattr(req, "llm_profile_id", "openrouter-claude")
        inherit_personas = getattr(req, "agent_persona_ids", {})
        inherit_prompt_variant = getattr(req, "prompt_variant", "default")
        inherit_max_rounds = getattr(req, "max_rounds", 3)
        inherit_consensus_threshold = getattr(req, "consensus_threshold", 0.8)
        inherit_search_mode = getattr(req, "search_mode", "off")
        inherit_language = getattr(req, "language", "de")
        inherit_enable_extra_rounds = getattr(req, "enable_extra_rounds", False)

    from backend.models.schemas import (
        AgentConfig,
        CaseInput,
    )
    from backend.models.schemas import (
        DebateRequest as ReqModel,
    )

    new_request = ReqModel(
        case=CaseInput(text=followup_prompt),
        agent_profile=[
            AgentConfig(role="strategist", **inherit_personas.get("strategist", {"llm_profile": inherit_llm})),
            AgentConfig(role="critic", **inherit_personas.get("critic", {"llm_profile": inherit_llm})),
            AgentConfig(role="optimizer", **inherit_personas.get("optimizer", {"llm_profile": inherit_llm})),
            AgentConfig(role="moderator", **inherit_personas.get("moderator", {"llm_profile": inherit_llm})),
        ],
        max_rounds=inherit_max_rounds,
        consensus_threshold=inherit_consensus_threshold,
        search_mode=inherit_search_mode,
        llm_profile_id=inherit_llm,
        prompt_variant=inherit_prompt_variant,
        agent_persona_ids=inherit_personas,
        language=inherit_language,
        enable_extra_rounds=inherit_enable_extra_rounds,
    )

    # Create the new debate using the standard flow
    from datetime import UTC, datetime

    new_debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    new_title = body.new_title or f"Fortsetzung: {debate.get('title', 'Debatte')}"

    new_debate = {
        "debate_id": new_debate_id,
        "status": DebateStatus.PENDING,
        "title": "",
        "request": new_request,
        "max_rounds": new_request.max_rounds,
        "current_round": 0,
        "rounds": [],
        "created_at": now,
        "updated_at": now,
        "result": None,
    }

    store.put(new_debate_id, new_debate)

    return DebateResponse(debate_id=new_debate_id, status=DebateStatus.PENDING, title=new_title, created_at=now)


# ---------------------------------------------------------------------------
# Fork from Consensus (P2)
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/fork-from-consensus", response_model=DebateResponse)
async def fork_from_consensus(
    debate_id: str,
    body: ForkFromConsensusBody,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateResponse:
    """Create a new debate from the consensus of a completed one (P2).

    The consensus summary is used as the starting context.
    """

    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status_val = debate.get("status", "")
    if hasattr(status_val, "value"):
        status_val = status_val.value
    if status_val != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Cannot fork from consensus with status '{status_val}'. Only completed debates are supported.",
        )

    # Build consensus-aware case text
    result = debate.get("result", {})
    consensus = result.get("final_consensus", 0.0)
    output = result.get("output", "")
    req = debate.get("request", {})
    title = debate.get("title", "Debatte")

    if isinstance(req, dict):
        original_case = req.get("case", {}).get("text", "")
        inherit_language = req.get("language", "de")
        inherit_max_rounds = body.max_rounds
        inherit_threshold = body.consensus_threshold
        inherit_personas = req.get("agent_persona_ids", {})
        inherit_llm = req.get("llm_profile_id", "openrouter-claude")
        inherit_prompt_variant = req.get("prompt_variant", "default")
        inherit_search_mode = req.get("search_mode", "off")
    else:
        original_case = getattr(req.case, "text", "")
        inherit_language = getattr(req, "language", "de")
        inherit_max_rounds = body.max_rounds
        inherit_threshold = body.consensus_threshold
        inherit_personas = getattr(req, "agent_persona_ids", {})
        inherit_llm = getattr(req, "llm_profile_id", "openrouter-claude")
        inherit_prompt_variant = getattr(req, "prompt_variant", "default")
        inherit_search_mode = getattr(req, "search_mode", "off")

    # Extract top-3 arguments per role for context
    from backend.workflow.report_generator import WorkflowReportGenerator

    transcript = WorkflowReportGenerator._build_transcript(debate)
    summaries = []
    role_summaries: dict[str, list[str]] = {}
    for rd in transcript.get("rounds", []):
        for ao in rd.get("agent_outputs", []):
            role = ao.get("role", "unknown")
            content = ao.get("content", "")[:200]
            if role not in role_summaries:
                role_summaries[role] = []
            role_summaries[role].append(content)

    for role, contents in role_summaries.items():
        summaries.append(f"### {role.capitalize()}:\n" + "\n".join(f"- {c}" for c in contents[-3:]))

    summary_text = "\n\n".join(summaries)

    fork_case_text = (
        f"Kontext: Die Debatte '{title}' wurde mit einem Konsensgrad von {consensus * 100:.0f}% abgeschlossen.\n\n"
        f"Zusammenfassung der Ergebnisse:\n{output[:1000] if output else 'Kein Endergebnis verfügbar.'}\n\n"
        f"Wichtige Argumente aus der vorherigen Debatte:\n{summary_text}\n\n"
        f"Neues Thema: {body.new_topic}\n\n"
        f"Original-Falltext:\n{original_case}"
    )

    from backend.models.schemas import AgentConfig, CaseInput
    from backend.models.schemas import DebateRequest as ReqModel

    new_request = ReqModel(
        case=CaseInput(text=fork_case_text),
        agent_profile=[
            AgentConfig(role="strategist", **inherit_personas.get("strategist", {"llm_profile": inherit_llm})),
            AgentConfig(role="critic", **inherit_personas.get("critic", {"llm_profile": inherit_llm})),
            AgentConfig(role="optimizer", **inherit_personas.get("optimizer", {"llm_profile": inherit_llm})),
            AgentConfig(role="moderator", **inherit_personas.get("moderator", {"llm_profile": inherit_llm})),
        ],
        max_rounds=inherit_max_rounds,
        consensus_threshold=inherit_threshold,
        search_mode=inherit_search_mode,
        llm_profile_id=inherit_llm,
        prompt_variant=inherit_prompt_variant,
        agent_persona_ids=inherit_personas,
        language=inherit_language,
    )

    from datetime import UTC, datetime

    new_debate_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    new_debate = {
        "debate_id": new_debate_id,
        "status": DebateStatus.PENDING,
        "title": body.new_title,
        "request": new_request,
        "max_rounds": new_request.max_rounds,
        "current_round": 0,
        "rounds": [],
        "created_at": now,
        "updated_at": now,
        "result": None,
    }

    store.put(new_debate_id, new_debate)

    return DebateResponse(debate_id=new_debate_id, status=DebateStatus.PENDING, title=body.new_title, created_at=now)


# ---------------------------------------------------------------------------
# Fork Debate (P4)
# ---------------------------------------------------------------------------


@router.post("/{debate_id}/fork", response_model=DebateResponse)
async def fork_debate(
    debate_id: str,
    body: ForkDebateBody,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> DebateResponse:
    """Fork an existing debate with optional modifications (P4).

    Creates a deep copy with configurable fork point and persona/prompt changes.
    """
    from backend.services.debate_workflow import create_fork_debate

    store = get_debate_store_for_project(project_id, project_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    # Validate fork_from_round
    if body.fork_from_round is not None:
        max_round = debate.get("current_round", 0)
        if body.fork_from_round < 0 or body.fork_from_round > max_round:
            raise HTTPException(
                status_code=400,
                detail=f"fork_from_round must be between 0 and {max_round} (current round)",
            )

    # Prevent circular forks
    existing_parent = debate.get("fork_info", {}).get("parent_debate_id") if isinstance(debate.get("fork_info"), dict) else None
    if existing_parent == debate_id:
        raise HTTPException(status_code=400, detail="Circular fork detected")

    try:
        result = create_fork_debate(
            original_debate_id=debate_id,
            new_title=body.new_title,
            fork_from_round=body.fork_from_round,
            fork_reason=body.fork_reason,
            modified_personas=body.modified_personas,
            modified_prompt_variant=body.modified_prompt_variant,
            store=store,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return DebateResponse(
        debate_id=result["debate_id"],
        status=DebateStatus.PENDING,
        title=result["title"],
        created_at=result["created_at"],
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

    status = debate.get("status")
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


# ---------------------------------------------------------------------------
# List forks of a debate (P4 helper)
# ---------------------------------------------------------------------------


@router.get("/{debate_id}/forks", response_model=list[DebateListItem])
async def list_forks(
    debate_id: str,
    limit: int = 50,
    offset: int = 0,
    project_id: str = Depends(get_project_id),
    project_store: ProjectStore = Depends(get_project_store),
) -> list[DebateListItem]:
    """List all forks originating from a given debate (P4).

    Allows tracing the fork tree of a debate.
    """
    store = get_debate_store_for_project(project_id, project_store)
    debates = store.list_all(limit=limit + offset)

    project = project_store.get(project_id)
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
    project_store: ProjectStore = Depends(get_project_store),
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
