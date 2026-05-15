"""Debate workflow execution service.

Extracted from ``backend.api.routers.debate`` to separate business logic
(title generation, RAG resolution, LangGraph orchestration, OOB queues,
cancellation state) from HTTP routing concerns.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.api.events import publish_async
from backend.core.config import is_service_llm_eligible, settings
from backend.models.schemas import AuditEvent, DebateStatus
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.persistence.project_store import ProjectStore
from backend.services.dms.service import get_dms_for_project

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state (cancellation flags, OOB queues)
# ---------------------------------------------------------------------------

_cancelled_debates: set[str] = set()
_oob_queues: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Cancellation helpers
# ---------------------------------------------------------------------------


def is_cancelled(debate_id: str) -> bool:
    """Check if a debate has been cancelled."""
    return debate_id in _cancelled_debates


def clear_cancel(debate_id: str) -> None:
    """Remove cancellation flag after handling."""
    _cancelled_debates.discard(debate_id)


def mark_cancelled(debate_id: str) -> None:
    """Mark a debate as cancelled."""
    _cancelled_debates.add(debate_id)


# ---------------------------------------------------------------------------
# OOB (Out-of-Band) input helpers
# ---------------------------------------------------------------------------


def get_oob_for_debate(debate_id: str) -> list[dict]:
    """Get all pending OOB inputs for a debate (used by workflow nodes)."""
    return [oob for oob in _oob_queues.get(debate_id, []) if oob["status"] == "pending"]


def consume_oob(debate_id: str, oob_ids: list[str]) -> None:
    """Mark OOB inputs as consumed."""
    for oob in _oob_queues.get(debate_id, []):
        if oob["oob_id"] in oob_ids:
            oob["status"] = "consumed"


def clear_oob_queue(debate_id: str) -> None:
    """Clean up OOB queue after debate completes."""
    _oob_queues.pop(debate_id, None)


def enqueue_oob(debate_id: str, entry: dict) -> None:
    """Add an OOB entry to the queue."""
    if debate_id not in _oob_queues:
        _oob_queues[debate_id] = []
    _oob_queues[debate_id].append(entry)


# ---------------------------------------------------------------------------
# Request field extraction helpers
# ---------------------------------------------------------------------------


def extract_rag_info(req: object | dict) -> tuple[list[str], bool]:
    """Extract RAG fields from a request (DebateRequest object or dict)."""
    if hasattr(req, "document_ids"):
        return getattr(req, "document_ids", []), getattr(req, "rag_auto_retrieve", False)
    elif isinstance(req, dict):
        return req.get("document_ids", []), req.get("rag_auto_retrieve", False)
    return [], False


def build_rag_preview(project_id: str, document_ids: list[str], project_store: ProjectStore | None = None) -> str:
    """Build a short preview of RAG context for the response."""
    if not document_ids:
        return ""
    try:
        dms = get_dms_for_project(project_id, project_store)

        chunks = []
        for doc_id in document_ids:
            chunks.extend(dms.metadata_index.get_chunks_by_document(doc_id))
        if chunks:
            return dms.format_rag_context(chunks[:3], max_chars=500)
    except Exception as exc:
        logger.warning("build_rag_preview failed for project %s: %s", project_id, exc)
    return ""


def extract_request_fields(req: object | dict) -> dict:
    """Extract all common request fields from a DebateRequest or dict.

    Returns a dict with keys: case_text, max_rounds, consensus_threshold,
    enable_fact_check, enable_memory, llm_profile_id, prompt_variant,
    agent_persona_ids, language, document_ids, rag_auto_retrieve,
    a2a_agents_raw, search_mode, agent_profile_list.
    """
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
        raw_search_mode = getattr(req, "search_mode", None)
        if raw_search_mode is not None:
            search_mode = raw_search_mode.value if hasattr(raw_search_mode, "value") else str(raw_search_mode)
        elif enable_fact_check:
            search_mode = "required"
        else:
            search_mode = "off"
        enable_extra_rounds = getattr(req, "enable_extra_rounds", False)
        agent_profile_list = [{"role": a.role.value, "llm_profile": a.llm_profile, "temperature": a.temperature} for a in req.agent_profile]
    else:
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
        enable_extra_rounds = req.get("enable_extra_rounds", False)

    return {
        "case_text": case_text,
        "max_rounds": max_rounds,
        "consensus_threshold": consensus_threshold,
        "enable_fact_check": enable_fact_check,
        "enable_memory": enable_memory,
        "llm_profile_id": llm_profile_id,
        "prompt_variant": prompt_variant,
        "agent_persona_ids": agent_persona_ids,
        "language": language,
        "document_ids": document_ids,
        "rag_auto_retrieve": rag_auto_retrieve,
        "a2a_agents_raw": a2a_agents_raw,
        "search_mode": search_mode,
        "agent_profile_list": agent_profile_list,
        "enable_extra_rounds": enable_extra_rounds,
    }


# ---------------------------------------------------------------------------
# A2A configuration
# ---------------------------------------------------------------------------


def build_a2a_config(a2a_agents_raw: list) -> dict:
    """Build A2A configuration dict from the request's a2a_agents list.

    Returns a dict with ``enabled``, ``agent_url``, ``role``, etc.
    If no A2A agents are configured, returns ``{"enabled": False}``.
    """
    if not a2a_agents_raw:
        return {"enabled": False}

    first = a2a_agents_raw[0]
    if hasattr(first, "url"):
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


def resolve_rag_context(
    project_id: str,
    case_text: str,
    document_ids: list[str] | None = None,
    rag_auto_retrieve: bool = False,
    project_store: ProjectStore | None = None,
) -> tuple[str, int]:
    """Resolve RAG context for a debate.

    Returns (rag_context_string, document_count).
    """
    from backend.services.dms.service import get_dms_for_project

    try:
        dms = get_dms_for_project(project_id, project_store)
    except Exception as exc:
        logger.warning("Could not initialize DMS for project %s: %s", project_id, exc)
        return "", 0

    all_chunks: list[dict] = []

    if document_ids:
        for doc_id in document_ids:
            try:
                chunks = dms.metadata_index.get_chunks_by_document(doc_id)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning("Failed to get chunks for document %s: %s", doc_id, exc)

    if rag_auto_retrieve and case_text:
        try:
            auto_chunks = dms.auto_retrieve_for_topic(case_text, project_id=project_id, k=10)
            all_chunks.extend(auto_chunks)
        except Exception as exc:
            logger.warning("Auto-retrieve failed for project %s: %s", project_id, exc)

    if not all_chunks:
        return "", 0

    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for chunk in all_chunks:
        text = chunk.get("text", "")
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_chunks.append(chunk)

    if document_ids:
        rag_context = dms.format_rag_context(unique_chunks, max_chars=200_000)
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
# Title generation
# ---------------------------------------------------------------------------


async def generate_debate_title(
    case_text: str,
    llm_profile_id: str,
    language: str,
    project_id: str | None = None,
    use_service_llm: bool = True,
) -> str:
    """Generate a concise debate title (60-150 chars) using the best available LLM.

    If ``use_service_llm`` is True, selects a service-eligible LLM via
    ``_select_service_llm()`` for higher quality output.
    """
    from backend.services.llm_service import LLMService
    from backend.services.profile_service import ProfileService

    _title_system_prompts = {
        "en": (
            "You are an expert debate title generator. "
            "Produce ONLY a concise, descriptive title (60-150 characters) "
            "summarizing the core question. "
            "No introductions, no explanations, no quotes, no trailing punctuation."
        ),
        "de": (
            "Du bist ein Experte fuer Debattentitel. Erstelle AUSSCHLIESSLICH "
            "einen praegnanten Titel (60-150 Zeichen) zur zentralen Fragestellung. "
            "Keine Einleitungen, keine Erklaerungen, keine Anfuehrungszeichen."
        ),
    }

    try:
        ps = ProfileService()

        if use_service_llm:
            service_id = _select_service_llm(ps)
            llm_service = LLMService(profile_id=service_id, profile_service=ps)
        else:
            llm_service = LLMService(profile_id=llm_profile_id, profile_service=ps)

        system_prompt = _title_system_prompts.get(language, _title_system_prompts["de"])

        user_prompt = (
            f"Create ONE debate title (60-150 characters) for the following case. Output ONLY the title, nothing else.\n\n{case_text[:2000]}"
        )

        result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=100,
        )

        title = _post_process_title(result.content.strip(), case_text)
        logger.info("Generated debate title (%d chars, service=%s): %s", len(title), use_service_llm, title)
        return title

    except Exception as exc:
        logger.warning("Title generation failed (non-fatal): %s", exc)
        return _fallback_title(case_text)


def _select_service_llm(profile_service) -> str:
    """Select the best service LLM profile for system/background tasks.

    Strategy:
    1. Use configured settings.service_llm_profile_id if eligible.
    2. Otherwise find first eligible profile preferring openrouter + large context.
    3. Fall back to configured ID regardless.
    """
    try:
        preferred = profile_service.get_llm_profile(settings.service_llm_profile_id)
        if preferred and is_service_llm_eligible(preferred):
            return settings.service_llm_profile_id
    except Exception:
        pass
    try:
        all_profiles = profile_service.list_llm_profiles()
        eligible = [p for p in all_profiles if is_service_llm_eligible(p)]
        if eligible:
            eligible.sort(key=lambda p_: (0 if p_.provider.value == "openrouter" else 1, -(p_.context_window or 0)))
            return eligible[0].id
    except Exception:
        pass
    return settings.service_llm_profile_id


def _post_process_title(raw: str, case_text: str) -> str:
    """Clean and validate a generated title, falling back if needed."""
    _re = __import__("re")
    verbose = [
        r"^Here(?:’s| is) (?:a |the |an )?(?:suggested |proposed )?(?:debate )?title[:\s]*",
        r"^The title is[:\s]*",
        r"^Title[:\s]*",
        r"^I suggest[:\s]*",
        r"^I propose[:\s]*",
        r"^I think[:\s]*",
        r"^Der Titel lautet[:\s]*",
        r"^Titel[:\s]*",
        r"^Hier ist ein Titel[:\s]*",
        r"^Ich schlage vor[:\s]*",
        r"^Ein passender Titel (?:wäre|ist)[:\s]*",
    ]
    cleaned = raw.strip()
    for pat in verbose:
        cleaned = _re.sub(pat, "", cleaned, count=1, flags=_re.IGNORECASE).strip()
    for ch in ['"', "'", "„", "“", "”", "‘", "’", "`", "-", "–", ":", ".", ","]:
        cleaned = cleaned.strip(ch)
    cleaned = cleaned.strip()

    if not cleaned or len(cleaned) < 15 or len(cleaned) > 150:
        return _fallback_title(case_text)

    reflection = [
        r"(?:the user|der benutzer)",
        r"based on",
        r"basierend auf",
        r"(?:description|beschreibung).*(?:about|um)",
        r"^-\s",
    ]
    if any(_re.search(p, cleaned, _re.IGNORECASE) for p in reflection):
        return _fallback_title(case_text)

    return cleaned


def _fallback_title(case_text: str) -> str:
    """Fallback: use beginning of case text as title."""
    fallback = case_text[:120].strip()
    for sep in [".", "?", "!"]:
        if sep in fallback:
            fallback = fallback[: fallback.rfind(sep) + 1]
            break
    if len(fallback) > 150:
        fallback = fallback[:147] + "..."
    return fallback


async def run_debate_workflow(
    debate_id: str,
    project_id: str,
    audit: AuditService,
    store: DebateStore,
    project_store: ProjectStore | None = None,
) -> None:
    """Run the LangGraph workflow for a debate (called as background task)."""
    debate = store.get(debate_id)
    if not debate:
        return

    # --- Publish: workflow started ---
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
    fields = extract_request_fields(req)

    await publish_async(
        debate_id,
        "title_generating",
        {"type": "title_generating", "message": "Generating debate title..."},
    )

    generated_title = await generate_debate_title(fields["case_text"], fields["llm_profile_id"], fields["language"], project_id, use_service_llm=True)

    store.update(debate_id, title=generated_title)

    await publish_async(
        debate_id,
        "title_ready",
        {"type": "title_ready", "title": generated_title},
    )

    # --- RAG context resolution ---
    rag_context, rag_doc_count = resolve_rag_context(
        project_id=project_id,
        case_text=fields["case_text"],
        document_ids=fields["document_ids"],
        rag_auto_retrieve=fields["rag_auto_retrieve"],
        project_store=project_store,
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
        "context": fields["case_text"],
        "agent_profile": fields["agent_profile_list"],
        "max_rounds": fields["max_rounds"],
        "threshold": fields["consensus_threshold"],
        "enable_fact_check": fields["enable_fact_check"],
        "enable_memory": fields["enable_memory"],
        "rag_context": rag_context,
        "llm_profile_id": fields["llm_profile_id"],
        "prompt_variant": fields["prompt_variant"],
        "agent_persona_ids": fields["agent_persona_ids"],
        "language": fields["language"],
        "search_mode": fields["search_mode"],
        "project_id": project_id,
        "session_id": debate_id,
        "debate_id": debate_id,
        "current_round": 0,
        "current_agent_index": 0,
        "rounds": [],
        "agent_outputs": [],
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "validation_report": [],
        "used_variant": "default",
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
        "enable_extra_rounds": fields.get("enable_extra_rounds", False),
        "extension_granted": None,
    }

    # --- A2A configuration ---
    a2a_config = build_a2a_config(fields["a2a_agents_raw"])
    initial_state["a2a_config"] = a2a_config

    # Run graph
    a2a_enabled = a2a_config.get("enabled", False)
    hitl_enabled = initial_state.get("hitl_enabled", False)
    if a2a_enabled:
        from backend.workflow.debate_graph import get_a2a_debate_graph

        graph = get_a2a_debate_graph()
        logger.info("Using A2A-aware graph for debate %s", debate_id)
    elif hitl_enabled:
        from backend.workflow.hitl.graph import hitl_debate_graph

        graph = hitl_debate_graph
        logger.info("Using HITL-aware graph for debate %s", debate_id)
    else:
        from backend.api.deps import get_debate_graph

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
        await publish_async(
            debate_id,
            "status_change",
            {"status": "failed", "cancel_reason": "User cancelled the debate"},
        )
        clear_cancel(debate_id)
        logger.info("Debate %s was cancelled by user", debate_id)
        return

    # Update debate state
    anomalies = result.get("anomalies", [])
    has_failures = len(anomalies) > 0
    final_status = DebateStatus.FAILED if has_failures else DebateStatus.COMPLETED

    store.update(
        debate_id,
        status=final_status,
        current_round=result.get("current_round", fields["max_rounds"]),
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
            llm_model=fields["llm_profile_id"],
            tokens_used=agent_output.get("tokens_used", 0),
        )
        audit.record(event, project_id=project_id)

    # --- Build and save DebateArtifact for Output Composer ---
    if not has_failures:
        try:
            from backend.models.artifact import DebateArtifact, Turn
            from backend.services.artifact_store import ArtifactStore

            turns: list[Turn] = []
            for rd in result.get("rounds", []):
                for ao in rd.get("agent_outputs", []):
                    turns.append(
                        Turn(
                            round=rd.get("round", 0),
                            node_id=f"{ao.get('role', 'agent')}_round{rd.get('round', 0)}",
                            agent_name=ao.get("role", "agent"),
                            role_type=ao.get("role", "agent"),
                            content=ao.get("content", ""),
                            llm_profile_id=fields["llm_profile_id"],
                            token_usage={"total": ao.get("tokens_used", 0)},
                        )
                    )

            artifact = DebateArtifact(
                session_id=debate_id,
                workflow_id=f"debate_{debate_id[:8]}",
                workflow_version=1,
                workflow_name="debate",
                topic=fields["case_text"],
                transcript=turns,
                consensus_result={
                    "score": result.get("final_consensus", 0.0),
                    "summary": result.get("output", ""),
                },
                metadata={
                    "token_usage": {
                        "total": sum(t.token_usage.get("total", 0) for t in turns),
                    },
                    "rounds_completed": result.get("current_round", 0),
                    "language": fields["language"],
                },
            )

            artifact_store = ArtifactStore()
            artifact_store.save(artifact)
            logger.info("DebateArtifact saved for debate %s", debate_id)
        except Exception as exc:
            logger.warning("Failed to save DebateArtifact for debate %s: %s", debate_id, exc)

    clear_cancel(debate_id)

    from backend.workflow.hitl.api import cleanup_hitl_state

    cleanup_hitl_state(debate_id)

    logger.info(
        "Debate %s completed: %d rounds, consensus=%.3f",
        debate_id,
        result.get("current_round", 0),
        result.get("final_consensus", 0.0),
    )
