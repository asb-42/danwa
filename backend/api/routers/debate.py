"""Debate API router — create, query, and run debates."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
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
    OOBInputBody,
    OOBInputResponse,
    RoundData,
)
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore

logger = logging.getLogger(__name__)

router = APIRouter()

# Set of debate IDs that have been requested to cancel
_cancelled_debates: set[str] = set()

# OOB input queues per debate: debate_id → list of OOB inputs
_oob_queues: dict[str, list[dict]] = {}


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

        # Filter by search text (match against title, case_text, or debate_id)
        debate_title = d.get("title", "")
        if search:
            search_lower = search.lower()
            if (search_lower not in case_text.lower()
                    and search_lower not in debate_title.lower()
                    and search_lower not in d.get("debate_id", "").lower()):
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

    # Clean up HITL state
    from backend.workflow.hitl.api import cleanup_hitl_state
    cleanup_hitl_state(debate_id)

    logger.info(
        "Deleted debate %s (%d audit events removed)",
        debate_id,
        deleted_events,
    )
    return {"detail": "Debate deleted", "debate_id": debate_id}


def _extract_rag_info(req: object | dict) -> tuple[list[str], bool]:
    """Extract RAG fields from a request (DebateRequest object or dict)."""
    if hasattr(req, "document_ids"):
        return getattr(req, "document_ids", []), getattr(req, "rag_auto_retrieve", False)
    elif isinstance(req, dict):
        return req.get("document_ids", []), req.get("rag_auto_retrieve", False)
    return [], False


def _build_rag_preview(project_id: str, document_ids: list[str]) -> str:
    """Build a short preview of RAG context for the response."""
    if not document_ids:
        return ""
    try:
        from backend.services.dms.service import get_dms_for_project
        dms = get_dms_for_project(project_id)
        chunks = []
        for doc_id in document_ids:
            chunks.extend(dms.metadata_index.get_chunks_by_document(doc_id))
        if chunks:
            return dms.format_rag_context(chunks[:3], max_chars=500)
    except Exception:
        pass
    return ""


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

    # RAG info
    document_ids, rag_auto_retrieve = _extract_rag_info(req)
    rag_enabled = bool(document_ids) or rag_auto_retrieve
    rag_preview = _build_rag_preview(project_id, document_ids) if document_ids else ""

    # HITL info
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

    # Count interactions from result
    result_interactions = []
    if isinstance(result, dict):
        result_interactions = result.get("interactions", [])

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

    # RAG info
    document_ids, rag_auto_retrieve = _extract_rag_info(req)
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
    store = get_debate_store_for_project(project_id)
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

    if debate_id not in _oob_queues:
        _oob_queues[debate_id] = []
    _oob_queues[debate_id].append(oob_entry)

    # Emit SSE event for frontend visualization
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


def get_oob_for_debate(debate_id: str) -> list[dict]:
    """Get all pending OOB inputs for a debate (used by workflow nodes)."""
    return [
        oob for oob in _oob_queues.get(debate_id, [])
        if oob["status"] == "pending"
    ]


def consume_oob(debate_id: str, oob_ids: list[str]) -> None:
    """Mark OOB inputs as consumed."""
    for oob in _oob_queues.get(debate_id, []):
        if oob["oob_id"] in oob_ids:
            oob["status"] = "consumed"


def clear_oob_queue(debate_id: str) -> None:
    """Clean up OOB queue after debate completes."""
    _oob_queues.pop(debate_id, None)


# ---------------------------------------------------------------------------
# A2A configuration
# ---------------------------------------------------------------------------


def _build_a2a_config(a2a_agents_raw: list) -> dict:
    """Build A2A configuration dict from the request's a2a_agents list.

    Returns a dict with ``enabled``, ``agent_url``, ``role``, etc.
    If no A2A agents are configured, returns ``{"enabled": False}``.
    """
    if not a2a_agents_raw:
        return {"enabled": False}

    # Use the first configured A2A agent
    first = a2a_agents_raw[0]
    if hasattr(first, "url"):
        # Pydantic model
        agent_url = first.url
        role = first.role
    elif isinstance(first, dict):
        agent_url = first.get("url", "")
        role = first.get("role", "a2a_agent")
    else:
        return {"enabled": False}

    if not agent_url:
        return {"enabled": False}

    return {
        "enabled": True,
        "agent_url": agent_url,
        "role": role,
        "external_agents": [
            {
                "url": a.url if hasattr(a, "url") else a.get("url", ""),
                "role": a.role if hasattr(a, "role") else a.get("role", "a2a_agent"),
            }
            for a in a2a_agents_raw
        ],
    }


# ---------------------------------------------------------------------------
# RAG context resolution
# ---------------------------------------------------------------------------


def _resolve_rag_context(
    project_id: str,
    case_text: str,
    document_ids: list[str] | None = None,
    rag_auto_retrieve: bool = False,
) -> tuple[str, int]:
    """Resolve RAG context for a debate.

    Returns (rag_context_string, document_count).
    """
    from backend.services.dms.service import get_dms_for_project

    try:
        dms = get_dms_for_project(project_id)
    except Exception as exc:
        logger.warning("Could not initialize DMS for project %s: %s", project_id, exc)
        return "", 0

    all_chunks: list[dict] = []

    # 1. Manual RAG: explicit document_ids from request
    if document_ids:
        for doc_id in document_ids:
            try:
                chunks = dms.metadata_index.get_chunks_by_document(doc_id)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning("Failed to get chunks for document %s: %s", doc_id, exc)

    # 2. Auto-retrieve: search RAG based on case text
    if rag_auto_retrieve and case_text:
        try:
            auto_chunks = dms.auto_retrieve_for_topic(case_text, project_id=project_id, k=10)
            all_chunks.extend(auto_chunks)
        except Exception as exc:
            logger.warning("Auto-retrieve failed for project %s: %s", project_id, exc)

    if not all_chunks:
        return "", 0

    # Deduplicate by text content
    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for chunk in all_chunks:
        text = chunk.get("text", "")
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_chunks.append(chunk)

    # For explicitly selected documents, use a much higher limit so
    # agents can see the complete documents.  Only apply the default
    # truncation for auto-retrieved chunks.
    if document_ids:
        # ~200,000 chars ≈ 50,000 tokens — covers large documents
        rag_context = dms.format_rag_context(
            unique_chunks, max_chars=200_000
        )
    else:
        rag_context = dms.format_rag_context(unique_chunks)
    doc_count = len(document_ids) if document_ids else 0

    logger.info(
        "RAG context resolved for project %s: %d unique chunks from %d documents",
        project_id,
        len(unique_chunks),
        doc_count,
    )
    return rag_context, doc_count


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
    store = get_debate_store_for_project(project_id)
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

    # Update the request's document_ids and rag_auto_retrieve
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


async def _generate_debate_title(
    case_text: str, llm_profile_id: str, language: str, project_id: str | None = None
) -> str:
    """Generate a concise debate title (60-150 chars) from the case description using LLM."""
    from backend.services.llm_service import LLMService
    from backend.services.profile_service import ProfileService

    try:
        profile_service = ProfileService()
        llm_service = LLMService(
            profile_id=llm_profile_id,
            profile_service=profile_service,
        )

        if language == "en":
            system_prompt = (
                "You are a debate title generator. Your task is to output ONLY a concise, "
                "descriptive title for a legal/policy debate based on the user's case description. "
                "CRITICAL RULES:\n"
                "- Output ONLY the title text — no explanations, no introductions, no meta-commentary\n"
                "- Do NOT start with phrases like 'Here is a title', 'The title is', 'I suggest', etc.\n"
                "- Do NOT describe what you are doing or what the user wants\n"
                "- The title MUST be between 60 and 150 characters\n"
                "- No quotes, no punctuation at the end\n"
                "- Example good output: 'The Role of Universal Basic Income in Reducing Social Inequality'\n"
                "- Example bad output: 'The user wants me to generate a title for...'\n"
                "- Just output the title directly as a single line."
            )
        else:
            system_prompt = (
                "Du bist ein Titel-Generator für Debatten. Deine einzige Aufgabe ist es, NUR einen "
                "prägnanten, beschreibenden Titel für eine rechtliche/politische Debatte basierend "
                "auf der Fallbeschreibung auszugeben.\n"
                "KRITISCHE REGELN:\n"
                "- Gib AUSSCHLIESSLICH den Titeltext aus — keine Erklärungen, keine Einleitungen\n"
                "- Beginne NICHT mit Sätzen wie 'Hier ist ein Titel', 'Der Titel lautet', 'Ich schlage vor' usw.\n"
                "- Beschreibe NICHT, was du tust oder was der Benutzer möchte\n"
                "- Der Titel MUSS zwischen 60 und 150 Zeichen lang sein\n"
                "- Keine Anführungszeichen, kein Satzzeichen am Ende\n"
                "- Beispiel guter Output: 'Die Rolle des bedingungslosen Grundeinkommens bei der Reduzierung sozialer Ungleichheit'\n"
                "- Beispiel schlechter Output: 'Der Benutzer möchte, dass ich einen Titel erstelle für...'\n"
                "- Gib den Titel direkt als einzelne Zeile aus."
            )

        user_prompt = f"Fallbeschreibung / Case description:\n\n{case_text[:2000]}"

        result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=100,
        )

        title = result.content.strip().strip('"').strip("'").strip()
        # Strip common verbose LLM prefixes (e.g., "Here is a title:", "Der Titel lautet:")
        verbose_prefixes = [
            r'^(?:Here(?:’s| is) (?:a |the |an )?(?:suggested |proposed )?(?:debate )?title[:\s]*|The title is[:\s]*|Title[:\s]*|I suggest[:\s]*|I propose[:\s]*|I would suggest[:\s]*|I think[:\s]*)',
            r'^(?:Der Titel lautet[:\s]*|Titel[:\s]*|Hier ist ein Titel[:\s]*|Ich schlage vor[:\s]*|Ich würde vorschlagen[:\s]*|Ich denke[:\s]*|Ein passender Titel (?:wäre|ist)[:\s]*)',
            r'^(?:Here is my title suggestion[:\s]*|My suggested title[:\s]*|Suggested title[:\s]*|Proposed title[:\s]*)',
            r'^(?:Mein Titelvorschlag[:\s]*|Vorgeschlagener Titel[:\s]*|Passender Titel[:\s]*)',
        ]
        for pattern in verbose_prefixes:
            title = re.sub(pattern, '', title, count=1, flags=re.IGNORECASE).strip()
        # Remove leading/trailing quotes, dashes, colons, dots
        title = title.strip('"\'„“”’`-–:.;, ')

        # Enforce length constraints
        if len(title) > 150:
            title = title[:147] + "..."
        elif len(title) < 10:
            # If absurdly short, use a padded fallback
            fallback = case_text[:120].strip()
            if len(fallback) > 150:
                fallback = fallback[:147] + "..."
            title = title or fallback

        logger.info("Generated debate title (%d chars): %s", len(title), title)
        return title

    except Exception as exc:
        logger.warning("Title generation failed (non-fatal): %s", exc)
        # Fallback: truncate case text
        fallback = case_text[:120].strip()
        if len(fallback) > 150:
            fallback = fallback[:147] + "..."
        return fallback


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

    # --- Generate debate title via LLM ---
    req = debate.get("request", {})
    if hasattr(req, "case"):
        _case_text = req.case.text
        _language = getattr(req, "language", "de")
        _llm_profile_id = req.llm_profile_id
    elif isinstance(req, dict):
        _case_text = req.get("case", {}).get("text", "") if isinstance(req.get("case"), dict) else ""
        _language = req.get("language", "de")
        _llm_profile_id = req.get("llm_profile_id", "openrouter-claude")
    else:
        _case_text = ""
        _language = "de"
        _llm_profile_id = "openrouter-claude"

    # Publish: title generation started
    await publish_async(
        debate_id,
        "title_generating",
        {
            "type": "title_generating",
            "message": "Generating debate title...",
        },
    )

    generated_title = await _generate_debate_title(
        _case_text, _llm_profile_id, _language, project_id
    )

    # Persist title in debate store
    store.update(debate_id, title=generated_title)

    # Publish: title ready (SSE event for frontend)
    await publish_async(
        debate_id,
        "title_ready",
        {
            "type": "title_ready",
            "title": generated_title,
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
        document_ids = getattr(req, "document_ids", [])
        rag_auto_retrieve = getattr(req, "rag_auto_retrieve", False)
        a2a_agents_raw = getattr(req, "a2a_agents", [])
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
        document_ids = req.get("document_ids", [])
        rag_auto_retrieve = req.get("rag_auto_retrieve", False)
        a2a_agents_raw = req.get("a2a_agents", [])
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

    # --- RAG context resolution ---
    rag_context, rag_doc_count = _resolve_rag_context(
        project_id=project_id,
        case_text=case_text,
        document_ids=document_ids,
        rag_auto_retrieve=rag_auto_retrieve,
    )
    if rag_context:
        logger.info(
            "RAG context injected for debate %s (%d chars from %d documents)",
            debate_id,
            len(rag_context),
            rag_doc_count,
        )

    # Build initial state for LangGraph
    initial_state = {
        "context": case_text,
        "agent_profile": agent_profile_list,
        "max_rounds": max_rounds,
        "threshold": consensus_threshold,
        "enable_fact_check": enable_fact_check,
        "enable_memory": enable_memory,
        "rag_context": rag_context,
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
        # --- HITL (Human-in-the-Loop) ---
        "interactions": [],
        "active_interrupt": None,
        "hitl_enabled": True,
        "hitl_mode": "full",
        "auto_query_threshold": 0.4,
        "max_interrupts_per_round": 3,
        "interrupt_timeout_seconds": 300,
        "pending_injects": [],
        "round_interrupt_count": 0,
        "is_paused": False,
    }

    # --- A2A configuration ---
    a2a_config = _build_a2a_config(a2a_agents_raw)
    initial_state["a2a_config"] = a2a_config

    # Run graph — async because nodes may call LLM APIs
    # Priority: A2A-aware graph > HITL-aware graph > standard graph
    a2a_enabled = a2a_config.get("enabled", False)
    hitl_enabled = initial_state.get("hitl_enabled", False)
    if a2a_enabled:
        from backend.workflow.debate_graph import a2a_debate_graph
        graph = a2a_debate_graph
        logger.info("Using A2A-aware graph for debate %s", debate_id)
    elif hitl_enabled:
        from backend.workflow.hitl.graph import hitl_debate_graph
        graph = hitl_debate_graph
        logger.info("Using HITL-aware graph for debate %s", debate_id)
    else:
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

    # Clean up HITL state
    from backend.workflow.hitl.api import cleanup_hitl_state
    cleanup_hitl_state(debate_id)

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
