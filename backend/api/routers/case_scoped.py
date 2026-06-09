"""Case-scoped API router — tenant/case-aware endpoints for debates and DMS.

These routes replace the legacy ``X-Project-Id`` header pattern with
path-based tenant + case resolution:

  ``/api/v1/tenants/{tid}/cases/{cid}/debates/...``
  ``/api/v1/tenants/{tid}/cases/{cid}/dms/...``
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query

from backend.api.deps import (
    get_audit_service,
    get_case_store,
    get_project_store,
    get_tag_store,
    get_tenant_store,
)
from backend.models.schemas import (
    DebateListItem,
    DebateRequest,
    DebateResponse,
    DebateStatus,
    DebateStatusResponse,
    OOBInputBody,
    OOBInputResponse,
    RoundData,
    TagInfo,
)
from backend.persistence.audit import AuditService
from backend.persistence.case_store import CaseStore
from backend.persistence.debate_store import DebateStore
from backend.persistence.tag_store import TagStore
from backend.persistence.tenant_store import TenantStore

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_case_dir(tenant_id: str, case_id: str, case_store: CaseStore) -> Path:
    """Resolve case dir internally."""
    case = case_store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case_store.get_case_dir(tenant_id, case_id)


def _get_debate_store_for_case(tenant_id: str, case_id: str, case_store: CaseStore) -> DebateStore:
    """Return (or lazily create) debate store for case."""
    case_dir = _resolve_case_dir(tenant_id, case_id, case_store)
    debates_dir = case_dir / "debates"
    debates_dir.mkdir(parents=True, exist_ok=True)
    return DebateStore(data_dir=debates_dir)


def _resolve_llm_model(llm_profile_id: str, project_id: str) -> str:
    """Resolve llm model internally."""
    if not llm_profile_id:
        return ""
    try:
        from backend.api.deps import get_blueprint_repository

        repo = get_blueprint_repository()
        profile = repo.get_llm_profile(llm_profile_id)
        if profile:
            return profile.model
    except Exception as e:
        logger.warning("Failed to resolve LLM profile %s: %s", llm_profile_id, e)
    return llm_profile_id


def _resolve_tags(tenant_id: str, tag_ids: list[str], tag_store: TagStore) -> list[TagInfo]:
    """Resolve a list of tag IDs to TagInfo objects."""
    if not tag_ids:
        return []
    result = []
    for tid in tag_ids:
        tag = tag_store.get(tenant_id, tid)
        if tag:
            result.append(TagInfo(id=tag.id, name=tag.name, color=tag.color))
    return result


def _build_debate_item(
    d: dict,
    debates: list[dict],
    *,
    tenant_id: str = "",
    tenant_name: str = "",
    case_id: str = "",
    case_title: str = "",
    tags: list[TagInfo] | None = None,
) -> DebateListItem:
    """Build a DebateListItem from raw debate dict with optional tenant/case context."""
    req = d.get("request", {})
    if hasattr(req, "case"):
        case_text = req.case.text
        language = getattr(req, "language", "de") or "de"
    elif isinstance(req, dict):
        case_text = req.get("case", {}).get("text", "") or ""
        language = req.get("language", "de") or "de"
    else:
        case_text = ""
        language = "de"

    result = d.get("result")
    consensus = result.get("final_consensus") if isinstance(result, dict) else None

    fork_info = d.get("fork_info")
    parent_id = fork_info.get("parent_debate_id") if isinstance(fork_info, dict) else None

    debate_id_current = d["debate_id"]
    forks_count = sum(
        1 for other_d in debates if isinstance(other_d.get("fork_info"), dict) and other_d["fork_info"].get("parent_debate_id") == debate_id_current
    )

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
        project_id=case_id,
        project_name=case_title or case_id,
        parent_debate_id=parent_id,
        forks_count=forks_count,
        is_mvp=d.get("is_mvp", False),
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        case_id=case_id,
        case_title=case_title,
        tags=tags or [],
    )


# ---------------------------------------------------------------------------
# Tenant-scoped debates — /tenants/{tid}/debates
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}/debates", response_model=list[DebateListItem])
async def list_tenant_debates(
    tenant_id: str,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    case_store: CaseStore = Depends(get_case_store),
    tag_store: TagStore = Depends(get_tag_store),
    tenant_store: TenantStore = Depends(get_tenant_store),
) -> list[DebateListItem]:
    """List ALL debates across all cases in a tenant (newest first).

    Aggregates debates from every case belonging to the tenant,
    enriching each item with case title, tenant name, and tag information.
    """
    tenant = tenant_store.get(tenant_id)
    tenant_name = tenant.name if tenant else tenant_id

    all_cases = case_store.list_by_tenant(tenant_id)
    all_items: list[DebateListItem] = []

    for case_obj in all_cases:
        try:
            store = _get_debate_store_for_case(tenant_id, case_obj.id, case_store)
            debates = store.list_all(limit=1000)
            tags = _resolve_tags(tenant_id, case_obj.tags, tag_store)

            for d in debates:
                req = d.get("request", {})
                if hasattr(req, "case"):
                    case_text = req.case.text
                elif isinstance(req, dict):
                    case_text = req.get("case", {}).get("text", "") or ""
                else:
                    case_text = ""

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

                item = _build_debate_item(
                    d,
                    debates,
                    tenant_id=tenant_id,
                    tenant_name=tenant_name,
                    case_id=case_obj.id,
                    case_title=case_obj.title,
                    tags=tags,
                )
                all_items.append(item)
        except Exception:
            logger.warning("Failed to load debates for case %s in tenant %s", case_obj.id, tenant_id, exc_info=True)
            continue

    # Sort by created_at descending, apply pagination
    all_items.sort(key=lambda x: x.created_at, reverse=True)
    return all_items[offset : offset + limit]


# ---------------------------------------------------------------------------
# Debate endpoints — /tenants/{tid}/cases/{cid}/debates
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}/cases/{case_id}/debates", response_model=list[DebateListItem])
async def list_case_debates(
    tenant_id: str,
    case_id: str,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    search: str | None = None,
    case_store: CaseStore = Depends(get_case_store),
    tag_store: TagStore = Depends(get_tag_store),
    tenant_store: TenantStore = Depends(get_tenant_store),
) -> list[DebateListItem]:
    """List debates in a case (newest first)."""
    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
    debates = store.list_all(limit=limit + offset)

    case_obj = case_store.get(tenant_id, case_id)
    case_title = case_obj.title if case_obj else case_id
    tags = _resolve_tags(tenant_id, case_obj.tags if case_obj else [], tag_store)

    tenant = tenant_store.get(tenant_id)
    tenant_name = tenant.name if tenant else tenant_id

    items = []
    for d in debates:
        req = d.get("request", {})
        if hasattr(req, "case"):
            case_text = req.case.text
        elif isinstance(req, dict):
            case_text = req.get("case", {}).get("text", "") or ""
        else:
            case_text = ""

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

        items.append(
            _build_debate_item(
                d,
                debates,
                tenant_id=tenant_id,
                tenant_name=tenant_name,
                case_id=case_id,
                case_title=case_title,
                tags=tags,
            )
        )

    return items[offset : offset + limit]


@router.post(
    "/tenants/{tenant_id}/cases/{case_id}/debates",
    response_model=DebateResponse,
    status_code=201,
)
async def create_case_debate(
    tenant_id: str,
    case_id: str,
    request: DebateRequest,
    audit: AuditService = Depends(get_audit_service),
    case_store: CaseStore = Depends(get_case_store),
) -> DebateResponse:
    """Create a new debate within a case (status = pending)."""
    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
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


@router.get("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}", response_model=DebateStatusResponse)
async def get_case_debate(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    case_store: CaseStore = Depends(get_case_store),
) -> DebateStatusResponse:
    """Get a single debate's status and progress."""
    from backend.services.debate_workflow import build_rag_preview, extract_rag_info

    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
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
        case_text = req.get("case", {}).get("text", "") or ""
        language = req.get("language", "de")
        llm_profile_id = req.get("llm_profile_id", "")
    else:
        case_text = ""
        language = "de"
        llm_profile_id = ""

    result = debate.get("result")
    consensus = result.get("final_consensus") if isinstance(result, dict) else None
    anomalies = result.get("anomalies", []) if isinstance(result, dict) else []

    project = get_project_store().get(case_id)
    project_name = project.name if project else case_id

    document_ids, rag_auto_retrieve = extract_rag_info(req)
    rag_enabled = bool(document_ids) or rag_auto_retrieve
    rag_preview = build_rag_preview(case_id, document_ids) if document_ids else ""

    from backend.workflow.hitl.api import get_active_interrupt, get_hitl_config
    from backend.workflow.hitl.api import is_paused as hitl_is_paused

    hitl_config = get_hitl_config(debate_id)
    hitl_enabled = hitl_config.get("hitl_enabled", False)
    hitl_mode = hitl_config.get("hitl_mode", "off")
    paused = hitl_is_paused(debate_id)
    active_interrupt = get_active_interrupt(debate_id)

    result_interactions = result.get("interactions", []) if isinstance(result, dict) else []

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
        llm_profile_model=_resolve_llm_model(llm_profile_id, case_id),
        anomalies=anomalies,
        project_id=case_id,
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


@router.post("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}/start", response_model=DebateStatusResponse)
async def start_case_debate(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    background_tasks: BackgroundTasks,
    audit: AuditService = Depends(get_audit_service),
    case_store: CaseStore = Depends(get_case_store),
) -> DebateStatusResponse:
    """Start a pending debate — launches the workflow in a background task."""
    from backend.services.debate_workflow import extract_rag_info
    from backend.tasks.dispatch import dispatch_debate_task

    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    if debate["status"] != DebateStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Debate is already {debate['status'].value}")

    debate["status"] = DebateStatus.RUNNING
    debate["updated_at"] = datetime.now(UTC)
    store.put(debate_id, debate)

    dispatch_debate_task(background_tasks, debate_id, case_id, audit, store)

    req = debate.get("request", {})
    max_rounds = getattr(req, "max_rounds", None) if hasattr(req, "max_rounds") else req.get("max_rounds", 3) if isinstance(req, dict) else 3

    if hasattr(req, "case"):
        case_text = req.case.text
        language = getattr(req, "language", "de")
        llm_profile_id = req.llm_profile_id
    elif isinstance(req, dict):
        case_text = req.get("case", {}).get("text", "") or ""
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


@router.delete("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}")
async def delete_case_debate(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    audit: AuditService = Depends(get_audit_service),
    case_store: CaseStore = Depends(get_case_store),
) -> dict:
    """Delete a debate and its associated audit events."""
    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
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

    logger.info("Deleted debate %s from case %s (%d audit events)", debate_id, case_id, deleted_events)
    return {"detail": "Debate deleted", "debate_id": debate_id}


@router.post("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}/cancel")
async def cancel_case_debate(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    case_store: CaseStore = Depends(get_case_store),
) -> dict:
    """Cancel a running debate (idempotent)."""
    from backend.services.debate_workflow import mark_cancelled

    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status

    if status_val in ("completed", "failed"):
        return {"status": status_val, "message": f"Debate already {status_val}"}

    mark_cancelled(debate_id)
    logger.info("Debate %s in case %s cancellation requested", debate_id, case_id)
    return {"status": "ok", "message": "Cancellation requested"}


@router.post("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}/force-reset")
async def force_reset_case_debate(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    case_store: CaseStore = Depends(get_case_store),
) -> dict:
    """Force-reset a stuck 'running' debate to 'failed' (idempotent)."""
    from datetime import UTC, datetime

    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
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
    logger.info("Force-reset debate %s in case %s from 'running' to 'failed'", debate_id, case_id)
    return {"status": "ok", "message": "Debate reset to 'failed'"}


@router.post("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}/oob", response_model=OOBInputResponse)
async def submit_case_oob_input(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    body: OOBInputBody,
    case_store: CaseStore = Depends(get_case_store),
) -> OOBInputResponse:
    """Submit an out-of-band input for a running debate in a case."""
    from backend.api.events import publish_async
    from backend.services.debate_workflow import enqueue_oob

    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "running":
        raise HTTPException(status_code=409, detail=f"Debate is not running (current status: {status_val})")

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

    logger.info("OOB input %s queued for debate %s in case %s", oob_id, debate_id, case_id)
    return OOBInputResponse(oob_id=oob_id, status="pending", target_resolved=body.target.type.value)


# ---------------------------------------------------------------------------
# Fork endpoint
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}/cases/{case_id}/debates/{debate_id}/forks", response_model=list[DebateListItem])
async def list_case_forks(
    tenant_id: str,
    case_id: str,
    debate_id: str,
    limit: int = 50,
    offset: int = 0,
    case_store: CaseStore = Depends(get_case_store),
) -> list[DebateListItem]:
    """List all forks originating from a given debate in a case."""
    store = _get_debate_store_for_case(tenant_id, case_id, case_store)
    debates = store.list_all(limit=limit + offset)

    project = get_project_store().get(case_id)
    project_name = project.name if project else case_id

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
            case_text = req.get("case", {}).get("text", "") or ""
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
                project_id=case_id,
                project_name=project_name,
                parent_debate_id=parent,
            )
        )

    return items[offset : offset + limit]


# ---------------------------------------------------------------------------
# DMS endpoints — /tenants/{tid}/cases/{cid}/dms
# ---------------------------------------------------------------------------


def _get_dms_for_case(tenant_id: str, case_id: str, case_store: CaseStore):
    """Get or create a DMS instance for a case.

    Multi-tenant safety:
      - The DMS cache is keyed by ``(tenant_id, case_id)`` (not by
        ``case_id`` alone), which prevents a case_id in one tenant
        from colliding with a project_id (or another case_id) in a
        different tenant.
      - Validates the case belongs to the given tenant before returning.
    """
    from backend.services.dms.config import load_dms_config
    from backend.services.dms.service import DMS, _dms_cache, _dms_cache_lock

    case = case_store.get(tenant_id, case_id)
    if not case or case.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Case not found")

    cache_key = ("case", tenant_id, case_id)
    with _dms_cache_lock:
        if cache_key in _dms_cache:
            return _dms_cache[cache_key]

        case_dir = case_store.get_case_dir(tenant_id, case_id)
        dms_dir = case_dir / "dms"
        dms_dir.mkdir(parents=True, exist_ok=True)

        try:
            dms_config = load_dms_config()
        except Exception:
            dms_config = {}

        # Bind the DMS to a synthetic project_id that encodes both
        # the tenant and the case. This way ``MetadataIndex`` (which
        # tags every ChromaDB document with ``project_id``) and the
        # ``rag_context`` table never see a cross-tenant collision even
        # if two cases happen to share a numeric id.
        scope_id = f"case:{tenant_id}:{case_id}"

        dms = DMS(
            db_path=str(dms_dir / "dms.db"),
            chroma_path=str(dms_dir / "chroma_db"),
            config=dms_config,
            project_id=scope_id,
        )
        _dms_cache[cache_key] = dms
        return dms


@router.get("/tenants/{tenant_id}/cases/{case_id}/dms/documents")
def list_case_documents(
    tenant_id: str,
    case_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """List documents in the case DMS."""
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    return dms.list_documents(case_id)


@router.get("/tenants/{tenant_id}/cases/{case_id}/dms/documents/{document_id}")
def get_case_document(
    tenant_id: str,
    case_id: str,
    document_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Get a single document with its content for viewing."""
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    try:
        doc = dms.get_document(document_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.post("/tenants/{tenant_id}/cases/{case_id}/dms/documents")
async def upload_case_document(
    tenant_id: str,
    case_id: str,
    file_bytes: bytes = File(...),
    filename: str = Query(default="uploaded.pdf"),
    case_store: CaseStore = Depends(get_case_store),
):
    """Upload a document to the case DMS."""
    import tempfile

    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
    try:
        tmp.write(file_bytes)
        tmp.close()
        result = dms.add_document(tmp.name, filename=filename)
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    return result


@router.delete("/tenants/{tenant_id}/cases/{case_id}/dms/documents/{document_id}")
def delete_case_document(
    tenant_id: str,
    case_id: str,
    document_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Delete a document from the case DMS."""
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    dms.delete_document(document_id)
    return {"detail": "Document deleted"}


@router.post("/tenants/{tenant_id}/cases/{case_id}/dms/documents/{document_id}/rag")
def add_case_document_rag(
    tenant_id: str,
    case_id: str,
    document_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Add a document to the RAG index for a case.

    Multi-tenant safety: the underlying ``add_to_rag_context`` validates
    that the document belongs to the active project; if it does not, the
    call returns 404 rather than silently attaching a foreign document.
    """
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    if dms.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found in this case")
    added = dms.add_to_rag_context(document_id)
    if not added:
        raise HTTPException(status_code=400, detail="Document already in RAG context")
    return {"detail": "Document added to RAG index"}


@router.delete("/tenants/{tenant_id}/cases/{case_id}/dms/documents/{document_id}/rag")
def remove_case_document_rag(
    tenant_id: str,
    case_id: str,
    document_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Remove a document from the RAG index for a case."""
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    removed = dms.remove_from_rag_context(document_id)
    if not removed:
        raise HTTPException(status_code=400, detail="Document not in RAG context")
    return {"detail": "Document removed from RAG index"}


@router.get("/tenants/{tenant_id}/cases/{case_id}/dms/rag/search")
def search_case_rag(
    tenant_id: str,
    case_id: str,
    query: str = Query(default=""),
    limit: int = Query(default=5),
    case_store: CaseStore = Depends(get_case_store),
):
    """Search the RAG index for a case (hybrid retriever, project-scoped)."""
    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    return {"results": dms.get_rag_context(query, project_id=dms._project_id, k=limit)}


# ---------------------------------------------------------------------------
# DMS Analysis
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/cases/{case_id}/dms/analyze")
async def analyze_case_documents(
    tenant_id: str,
    case_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Analyze all documents in the case DMS."""
    from backend.services.dms.document_analyzer import analyze_documents as run_document_analysis

    dms = _get_dms_for_case(tenant_id, case_id, case_store)
    result = await run_document_analysis(dms)
    return result


@router.get("/tenants/{tenant_id}/cases/{case_id}/dms/analyze")
def get_case_analysis(
    tenant_id: str,
    case_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Get the latest analysis for the case DMS."""
    from backend.services.dms.document_analyzer import load_analysis

    return load_analysis(case_id)


# ---------------------------------------------------------------------------
# Audit endpoints — /tenants/{tid}/cases/{cid}/audit
# ---------------------------------------------------------------------------


@router.get("/tenants/{tenant_id}/cases/{case_id}/audit/{debate_id_or_title}")
def list_case_audit_events(
    tenant_id: str,
    case_id: str,
    debate_id_or_title: str,
    limit: int = 100,
    offset: int = 0,
    audit: AuditService = Depends(get_audit_service),
    case_store: CaseStore = Depends(get_case_store),
):
    """List audit events for a debate within a case.

    Falls back to workflow audit_log table for MVP debates (same logic as
    the legacy ``/api/v1/audit`` endpoint).
    """
    from backend.api.routers.audit import (
        _enrich_events_with_debate_data,
        _resolve_debate_id,
        _transform_workflow_audit_events,
    )

    debate_id, debate_data = _resolve_debate_id(debate_id_or_title, case_id)
    events = audit.get_events(debate_id=debate_id)
    if events:
        return _enrich_events_with_debate_data(events, debate_data)

    # Fallback: check workflow audit_log table for MVP debates
    if debate_data and debate_data.get("session_id"):
        from backend.workflow.audit_logger import get_audit_logger

        session_id = debate_data["session_id"]
        al = get_audit_logger()
        wf_events = al.get_audit_log(session_id)
        if wf_events:
            return _transform_workflow_audit_events(wf_events, session_id)

    return []


# ---------------------------------------------------------------------------
# Workflow endpoints (case-scoped)
# ---------------------------------------------------------------------------


@router.post("/tenants/{tenant_id}/cases/{case_id}/workflows/{workflow_id}/start")
async def start_case_workflow(
    tenant_id: str,
    case_id: str,
    workflow_id: str,
    body: dict,
    background_tasks: BackgroundTasks,
    case_store: CaseStore = Depends(get_case_store),
):
    """Start a workflow within a case context.

    Delegates to the workflow_exec router but resolves the project_id
    from the tenant/case path.
    """
    case = case_store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Import and delegate to the existing start_workflow logic
    from backend.api.routers.workflow_exec import StartWorkflowRequest, start_workflow

    project_id = case_id
    req = StartWorkflowRequest(
        context=body.get("context", ""),
        language=body.get("language"),
        project_id=project_id,
        max_rounds=body.get("max_rounds", 10),
        threshold=body.get("threshold", 0.7),
        document_ids=body.get("document_ids", []),
        rag_auto_retrieve=body.get("rag_auto_retrieve", False),
        include_document_analysis=body.get("include_document_analysis", False),
    )
    return await start_workflow(workflow_id, req, background_tasks, project_id=project_id)


@router.get("/tenants/{tenant_id}/cases/{case_id}/workflows/{session_id}/state")
async def get_case_workflow_state(
    tenant_id: str,
    case_id: str,
    session_id: str,
    case_store: CaseStore = Depends(get_case_store),
):
    """Get workflow execution state within a case context."""
    case = case_store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    from backend.api.routers.workflow_exec import get_session_state

    return await get_session_state(session_id)
