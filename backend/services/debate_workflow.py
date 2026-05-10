"""Debate workflow execution service.

Extracted from ``backend.api.routers.debate`` to separate business logic
(title generation, RAG resolution, LangGraph orchestration, OOB queues,
cancellation state) from HTTP routing concerns.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime

from backend.api.events import publish_async
from backend.models.schemas import AuditEvent, DebateStatus
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore

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


def build_rag_preview(project_id: str, document_ids: list[str]) -> str:
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

        user_prompt = (
            "Create ONE debate title (60-150 characters) for the following case description. "
            "Output ONLY the title, nothing else. No quotes, no explanation.\n\n"
            f"{case_text[:2000]}"
        )

        result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=100,
        )

        title = result.content.strip().strip('"').strip("'").strip()

        # --- Step 1: Strip known verbose prefixes ---
        verbose_prefixes = [
            r"^(?:Here(?:\u2019s| is) (?:a |the |an )?(?:suggested |proposed )?(?:debate )?title[:\s]*|The title is[:\s]*|Title[:\s]*|I suggest[:\s]*|I propose[:\s]*|I would suggest[:\s]*|I think[:\s]*)",
            r"^(?:Der Titel lautet[:\s]*|Titel[:\s]*|Hier ist ein Titel[:\s]*|Ich schlage vor[:\s]*|Ich w\u00fcrde vorschlagen[:\s]*|Ich denke[:\s]*|Ein passender Titel (?:w\u00e4re|ist)[:\s]*)",
            r"^(?:Here is my title suggestion[:\s]*|My suggested title[:\s]*|Suggested title[:\s]*|Proposed title[:\s]*)",
            r"^(?:Mein Titelvorschlag[:\s]*|Vorgeschlagener Titel[:\s]*|Passender Titel[:\s]*)",
        ]
        for pattern in verbose_prefixes:
            title = re.sub(pattern, '', title, count=1, flags=re.IGNORECASE).strip()
        title = title.strip('"\'\u201e\u201c\u201d\u2018\u2019`-\u2013:.;, ')

        # --- Step 2: Detect prompt reflection / meta-commentary ---
        # If the LLM returned its thinking instead of a title, the output
        # will contain phrases like "The user wants", "based on", "characters",
        # "needs to be", bullet points, etc.  In that case we discard it.
        reflection_indicators = [
            r"\b(?:the user|der benutzer)\b",
            r"\b(?:wants|needs|muss|soll)\b.*\b(?:title|titel|character|zeichen)\b",
            r"\bbased on\b",
            r"\bbasierend auf\b",
            r"\bcharacters?\b.*\b(?:long|min|max)\b",
            r"\bzeichen\b.*\b(?:lang|min|max)\b",
            r"^-\s",  # bullet points
            r"\b(?:description|beschreibung)\b.*\b(?:about|um)\b",
        ]
        is_reflection = any(re.search(p, title, re.IGNORECASE) for p in reflection_indicators)

        # --- Step 3: Validate length and coherence ---
        if is_reflection or len(title) > 200:
            # LLM returned meta-commentary - use case text as fallback
            logger.warning(
                "Title generation returned prompt reflection (%d chars, reflection=%s), "
                "using case text fallback",
                len(title), is_reflection,
            )
            fallback = case_text[:120].strip()
            if len(fallback) > 150:
                fallback = fallback[:147] + "..."
            title = fallback
        elif len(title) > 150:
            title = title[:147] + "..."
        elif len(title) < 10:
            fallback = case_text[:120].strip()
            if len(fallback) > 150:
                fallback = fallback[:147] + "..."
            title = title or fallback

        logger.info("Generated debate title (%d chars): %s", len(title), title)
        return title

    except Exception as exc:
        logger.warning("Title generation failed (non-fatal): %s", exc)
        fallback = case_text[:120].strip()
        if len(fallback) > 150:
            fallback = fallback[:147] + "..."
        return fallback


# ---------------------------------------------------------------------------
# Workflow execution (background task)
# ---------------------------------------------------------------------------


async def run_debate_workflow(
    debate_id: str, project_id: str, audit: AuditService, store: DebateStore
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

    generated_title = await generate_debate_title(
        fields["case_text"], fields["llm_profile_id"], fields["language"], project_id
    )

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
    }

    # --- A2A configuration ---
    a2a_config = build_a2a_config(fields["a2a_agents_raw"])
    initial_state["a2a_config"] = a2a_config

    # Run graph
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
