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
# Document analysis formatting helper
# ---------------------------------------------------------------------------


def _format_analysis_for_rag(analysis: dict) -> str:
    """Format a document analysis dict as RAG context text.

    Shared helper used by ``resolve_rag_context`` and
    ``resolve_rag_context_with_debate_results``.
    """
    parts = [
        "=== DOCUMENT ANALYSIS ===",
        "The following is a structured case analysis of the uploaded documents. "
        "Use it as your PRIMARY source of case context — it summarizes the key facts, "
        "parties, timeline, and issues. The raw document excerpts below are for "
        "fact-checking and finding exact quotes.",
        "",
        f"Case Summary: {analysis.get('case_summary', '')}",
    ]
    if analysis.get("key_facts"):
        parts.append("Key Facts:\n- " + "\n- ".join(analysis["key_facts"]))
    if analysis.get("parties"):
        lines = [f"  {p['name']} ({p['role']}): {p['positions']}" for p in analysis["parties"]]
        parts.append("Parties:\n" + "\n".join(lines))
    if analysis.get("timeline"):
        lines = [f"  {t['date']} — {t['event']}" for t in analysis["timeline"]]
        parts.append("Timeline:\n" + "\n".join(lines))
    if analysis.get("key_issues"):
        parts.append("Key Issues:\n- " + "\n- ".join(analysis["key_issues"]))
    return "\n\n".join(parts)


def _load_analysis_text(project_id: str, project_store=None) -> str:
    """Load and format document analysis for a project, or return empty string."""
    from backend.services.dms.document_analyzer import load_analysis

    try:
        if project_store:
            project_dir = project_store.get_project_dir(project_id)
        else:
            from backend.persistence.project_store import ProjectStore

            ps = ProjectStore()
            project_dir = ps.get_project_dir(project_id)
        analysis = load_analysis(project_dir)
        if analysis and "error" not in analysis:
            logger.info("Loaded document analysis for project %s", project_id)
            return _format_analysis_for_rag(analysis)
    except Exception as exc:
        logger.debug("Could not load document analysis for project %s: %s", project_id, exc)
    return ""


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
    a2a_agents_raw, search_mode, agent_profile_list, bundle_ids,
    enable_extra_rounds.

    If language is None, resolves to the user's configured UI language
    (from config/settings.yaml), falling back to 'de' if not configured.
    """
    from backend.api.deps import get_user_language

    user_lang = get_user_language()

    if hasattr(req, "case"):
        case_text = req.case.text
        max_rounds = req.max_rounds
        consensus_threshold = req.consensus_threshold
        enable_fact_check = req.enable_fact_check
        enable_memory = req.enable_memory
        llm_profile_id = req.llm_profile_id
        prompt_variant = req.prompt_variant
        agent_persona_ids = req.agent_persona_ids
        language = getattr(req, "language", None) or user_lang
        document_ids = getattr(req, "document_ids", [])
        rag_auto_retrieve = getattr(req, "rag_auto_retrieve", False)
        include_debate_results = getattr(req, "include_debate_results", False)
        a2a_agents_raw = getattr(req, "a2a_agents", [])
        bundle_ids = getattr(req, "bundle_ids", [])
        raw_search_mode = getattr(req, "search_mode", None)
        if raw_search_mode is not None:
            search_mode = raw_search_mode.value if hasattr(raw_search_mode, "value") else str(raw_search_mode)
        elif enable_fact_check:
            search_mode = "required"
        else:
            search_mode = "off"
        enable_extra_rounds = getattr(req, "enable_extra_rounds", False)
        agent_profile_list = [{"role": a.role, "llm_profile": a.llm_profile, "temperature": a.temperature} for a in req.agent_profile]
    else:
        case_text = req.get("case", {}).get("text", "")
        max_rounds = req.get("max_rounds", 3)
        consensus_threshold = req.get("consensus_threshold", 0.8)
        enable_fact_check = req.get("enable_fact_check", False)
        enable_memory = req.get("enable_memory", False)
        llm_profile_id = req.get("llm_profile_id", "openrouter-claude")
        prompt_variant = req.get("prompt_variant", "default")
        agent_persona_ids = req.get("agent_persona_ids", {})
        language = req.get("language") or user_lang
        document_ids = req.get("document_ids", [])
        rag_auto_retrieve = req.get("rag_auto_retrieve", False)
        include_debate_results = req.get("include_debate_results", False)
        a2a_agents_raw = req.get("a2a_agents", [])
        bundle_ids = req.get("bundle_ids", [])
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
        "include_debate_results": include_debate_results,
        "a2a_agents_raw": a2a_agents_raw,
        "search_mode": search_mode,
        "agent_profile_list": agent_profile_list,
        "bundle_ids": bundle_ids,
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
# Bundle-based agent profile builder
# ---------------------------------------------------------------------------


def build_agent_profile_from_bundles(bundle_ids: list[str]) -> list[dict]:
    """Build agent_profile list from AgentBundle IDs.

    Each bundle resolves to an agent config with its LLM profile and role type.

    Args:
        bundle_ids: List of AgentBundle IDs.

    Returns:
        List of agent config dicts: [{role, llm_profile, temperature, bundle_id}, ...]
    """
    from backend.blueprints.repository import BlueprintRepository
    from backend.blueprints.resolver import BundleResolver

    repo = BlueprintRepository()
    resolver = BundleResolver(repo)
    profile = []

    for bid in bundle_ids:
        try:
            bundle = repo.get_bundle(bid)
            if not bundle:
                logger.warning("Bundle '%s' not found, skipping", bid)
                continue
            resolved = resolver.resolve(bundle)
            profile.append(
                {
                    "role": resolved.role_type.id,
                    "llm_profile": resolved.llm_profile.id,
                    "temperature": resolved.llm_profile.temperature,
                    "bundle_id": bid,
                    "system_prompt": resolved.system_prompt,
                    "model_params": resolved.model_params,
                }
            )
        except Exception as exc:
            logger.warning("Failed to resolve bundle '%s': %s", bid, exc)

    return profile


# ---------------------------------------------------------------------------
# RAG context resolution
# ---------------------------------------------------------------------------


def resolve_rag_context(
    project_id: str,
    case_text: str,
    document_ids: list[str] | None = None,
    rag_auto_retrieve: bool = False,
    include_debate_results: bool = False,
    debate_result_ids: list[str] | None = None,
    project_store: ProjectStore | None = None,
    store: DebateStore | None = None,
) -> tuple[str, int]:
    """Resolve RAG context for a debate.

    Returns (rag_context_string, document_count).
    """
    from backend.services.dms.service import get_dms_for_project

    analysis_text = _load_analysis_text(project_id, project_store)

    try:
        dms = get_dms_for_project(project_id, project_store)
    except Exception as exc:
        logger.warning("Could not initialize DMS for project %s: %s", project_id, exc)
        if analysis_text:
            return analysis_text, 0
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

    if include_debate_results:
        try:
            ps = project_store or ProjectStore()
            project_dir = ps.get_project_dir(project_id)
            proj_store = DebateStore(data_dir=project_dir / "debates")

            debates = proj_store.list_all(limit=50)

            if debate_result_ids:
                debate_ids_set = set(debate_result_ids)
                debates = [d for d in debates if d.get("debate_id") in debate_ids_set]
                logger.info(
                    "Including %d specific debate result(s) for project %s",
                    len(debates),
                    project_id,
                )
            else:
                logger.info(
                    "Auto-selecting up to 5 recent completed debates for project %s",
                    project_id,
                )

            debate_count = 0

            for d in debates:
                if d.get("status") in ("completed",) and d.get("debate_id"):
                    if debate_result_ids and d.get("debate_id") not in debate_ids_set:
                        continue
                    transcript = _build_transcript_for_followup(d)
                    summary = _generate_rag_friendly_summary(transcript)
                    from backend.services.dms.chunker import TextChunker

                    chunker = TextChunker()
                    raw_chunks = chunker.chunk(summary)
                    chunks = [{"text": t, "document_id": f"debate_result_{d.get('debate_id', '')[:8]}"} for t in raw_chunks]
                    all_chunks.extend(chunks[:3])

                    debate_count += 1
                    if not debate_result_ids and debate_count >= 5:
                        break
        except Exception as exc:
            logger.warning("Failed to include debate results in RAG context: %s", exc)

    if not all_chunks:
        if analysis_text:
            logger.info("Document analysis available but no chunks — returning analysis-only RAG context")
            return analysis_text, 0
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

    if analysis_text:
        rag_context = f"{analysis_text}\n\n=== DOCUMENT EXCERPTS ===\n\n{rag_context}" if rag_context else analysis_text
        logger.info("Prepended document analysis to RAG context for project %s", project_id)

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

SYSTEM_PROMPT_TITLES: dict[str, str] = {
    "en": (
        "You are a precise debate title generator.\n"
        "Rules — follow ALL of them:\n"
        "1. Output ONLY the title. Nothing else. No intro, no explanation.\n"
        "2. The title must be 40-120 characters.\n"
        '3. Do NOT start with "Here is", "The title is", "I suggest", etc.\n'
        "4. Do NOT describe the task or the user's request.\n"
        "5. Do NOT use quotation marks around the title.\n"
        "6. Do NOT end with punctuation.\n"
        "7. Format: concise noun phrase or simple sentence.\n\n"
        'BAD: "The user wants a debate about climate change"\n'
        'BAD: "Here is my suggested title: ..."\n'
        'GOOD: "Climate Change and Economic Growth: Compatible or Contradictory?"'
    ),
    "de": (
        "Du bist ein praeziser Titel-Generator fuer Debatten.\n"
        "Regeln — befolge ALLE:\n"
        "1. Gib AUSSCHLIESSLICH den Titel aus. Nichts anderes. Keine Einleitung.\n"
        "2. Der Titel muss 40-120 Zeichen lang sein.\n"
        '3. Beginne NICHT mit "Hier ist", "Der Titel lautet", etc.\n'
        "4. Beschreibe NICHT die Aufgabe oder den Wunsch des Benutzers.\n"
        "5. Keine Anfuehrungszeichen um den Titel.\n"
        "6. Kein Satzzeichen am Ende.\n"
        "7. Format: kompakte Nominalphrase oder einfacher Satz.\n\n"
        'BAD: "Der Benutzer moechte einen Titel ueber Klimawandel"\n'
        'BAD: "Hier ist mein vorgeschlagener Titel: ..."\n'
        'GOOD: "Klimawandel und Wirtschaftswachstum: Vereinbar oder Widerspruechlich?"'
    ),
}


async def generate_debate_title(
    case_text: str,
    llm_profile_id: str,
    language: str,
    project_id: str | None = None,
    use_service_llm: bool = True,
) -> str:
    """Generate a concise debate title (40-120 chars) using the best available LLM.

    If ``use_service_llm`` is True, selects a service-eligible LLM via
    ``_select_service_llm()`` for higher quality output.
    """
    from backend.services.llm_service import LLMService
    from backend.services.profile_service import ProfileService

    try:
        ps = ProfileService()

        if use_service_llm:
            service_id = _select_service_llm(ps)
            llm_service = LLMService(profile_id=service_id, profile_service=ps)
        else:
            llm_service = LLMService(profile_id=llm_profile_id, profile_service=ps)

        system_prompt = SYSTEM_PROMPT_TITLES.get(language, SYSTEM_PROMPT_TITLES["de"])

        user_prompt = (
            f"Generate ONE debate title (40-120 characters) for the following case. Output ONLY the title, nothing else.\n\n{case_text[:2000]}"
        )

        result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=100,
            context="Debate",
            stop=["\n\n", "---", "Titel:", "Title:"],
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
    3. Fall back to first available text-LLM.
    """
    try:
        if settings.service_llm_profile_id:
            preferred = profile_service.get_llm_profile(settings.service_llm_profile_id)
            if preferred and is_service_llm_eligible(preferred)[0]:
                return settings.service_llm_profile_id
    except Exception:
        pass
    try:
        all_profiles = profile_service.list_llm_profiles()
        eligible = [p for p in all_profiles if is_service_llm_eligible(p)[0]]
        if eligible:
            eligible.sort(key=lambda p_: (0 if p_.provider.value == "openrouter" else 1, -(p_.context_window or 0)))
            return eligible[0].id
    except Exception:
        pass
    # Last resort: return first text-LLM
    try:
        all_profiles = profile_service.list_llm_profiles()
        text_profiles = [p for p in all_profiles if getattr(p, "profile_type", "text") == "text"]
        if text_profiles:
            return text_profiles[0].id
    except Exception:
        pass
    raise RuntimeError("No suitable LLM profile available for service tasks")


def validate_title(title: str, case_text: str) -> tuple[bool, str]:
    """Check whether a generated title is acceptable.

    Returns:
        (valid: bool, reason: str) — reason explains why validation failed.
    """
    import re as _re

    if len(title) < 10:
        return False, "Zu kurz (< 10 Zeichen)"
    if len(title) > 150:
        return False, "Zu lang (> 150 Zeichen)"
    if title.lower()[:15] in case_text.lower()[:50]:
        return False, "Identisch mit Fallbeschreibung"
    meta_patterns = [
        "the user",
        "the case",
        "this debate",
        "würde gerne",
        "der benutzer",
        "der fall",
        "diese debatte",
        "hier ist",
        "here is",
        "i suggest",
        "ich schlage",
    ]
    if any(p in title.lower() for p in meta_patterns):
        return False, "Enthält Meta-Text"
    if _re.match(r"^[\s\"'„" r"''`\-–:.,!?]+$", title):
        return False, "Nur Sonderzeichen"
    return True, "OK"


def _post_process_title(raw: str, case_text: str) -> str:
    """Clean and validate a generated title, falling back if needed."""
    _re = __import__("re")
    verbose = [
        r"^Here(?:'s| is) (?:a |the |an )?(?:suggested |proposed )?(?:debate )?title[:\s]*",
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
    for ch in ['"', "'", "„", """, """, """, """, "`", "-", "–", ":", ".", ","]:
        cleaned = cleaned.strip(ch)
    cleaned = cleaned.strip()

    if not cleaned or len(cleaned) < 15 or len(cleaned) > 150:
        return _fallback_title(case_text)

    reflection = [
        r"\b(?:the user|der benutzer)\b",
        r"\bbased on\b",
        r"\bbasierend auf\b",
        r"\b(?:description|beschreibung)\b.*\b(?:about|um)\b",
        r"^-\s",
    ]
    if any(_re.search(p, cleaned, _re.IGNORECASE) for p in reflection):
        return _fallback_title(case_text)

    # Final validation using standalone validate_title()
    valid, reason = validate_title(cleaned, case_text)
    if not valid:
        logger.debug("Title validation failed: %s — %s", reason, cleaned[:80])
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
        include_debate_results=fields.get("include_debate_results", False),
        project_store=project_store,
        store=store,
    )
    if rag_context:
        logger.info(
            "RAG context injected for debate %s (%d chars from %d documents)",
            debate_id,
            len(rag_context),
            rag_doc_count,
        )

    # Build initial state for LangGraph
    agent_profile = fields["agent_profile_list"]

    # If bundle_ids are provided, override agent_profile with bundle-resolved configs
    if fields.get("bundle_ids"):
        bundle_profile = build_agent_profile_from_bundles(fields["bundle_ids"])
        if bundle_profile:
            agent_profile = bundle_profile
            logger.info(
                "Using %d bundle-resolved agent profiles for debate %s",
                len(bundle_profile),
                debate_id,
            )

    initial_state = {
        "context": fields["case_text"],
        "agent_profile": agent_profile,
        "max_rounds": fields["max_rounds"],
        "threshold": fields["consensus_threshold"],
        "enable_fact_check": fields["enable_fact_check"],
        "enable_memory": fields["enable_memory"],
        "rag_context": rag_context,
        "llm_profile_id": fields["llm_profile_id"],
        "prompt_variant": fields["prompt_variant"],
        "agent_persona_ids": fields["agent_persona_ids"],
        "language": fields["language"],
        "prompt_language": fields["language"],  # Updated when actual prompts are loaded
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
    # Save artifact whenever we have rounds completed, even with anomalies
    rounds_completed = result.get("rounds", [])
    if rounds_completed:
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
                    "prompt_language": result.get("prompt_language", fields["language"]),
                },
            )

            artifact_store = ArtifactStore()
            artifact_store.save(artifact)
            logger.info("DebateArtifact saved for debate %s", debate_id)
        except Exception as exc:
            logger.warning("Failed to save DebateArtifact for debate %s: %s", debate_id, exc)

    clear_cancel(debate_id)

    from backend.workflow.hitl.api import cleanup_hitl_state

    # Auto-create DMS document for RAG retrieval (Plan 19, P3)
    await on_debate_completed(debate_id, project_id)
    cleanup_hitl_state(debate_id)

    logger.info(
        "Debate %s completed: %d rounds, consensus=%.3f",
        debate_id,
        result.get("current_round", 0),
        result.get("final_consensus", 0.0),
    )


# ---------------------------------------------------------------------------
# Follow-up debate helpers (Plan 19, P0 + P1)
# ---------------------------------------------------------------------------


def build_followup_case(debate_id: str, focus_topic: str | None = None, store: DebateStore | None = None) -> str:
    """Baut einen neuen case_text aus den Ergebnissen der Vordebatte (P0)."""
    debate = store.get(debate_id) if store else None
    if not debate:
        return focus_topic or "Fortsetzung einer vorherigen Debatte."

    transcript = _build_transcript_for_followup(debate)

    # Die stärksten Argumente pro Rolle extrahieren
    summaries = []
    for round_data in transcript.get("rounds", []):
        for output in round_data.get("agent_outputs", []):
            if output.get("role") in ("strategist", "moderator", "critic", "optimizer"):
                content = output.get("content", "")
                if content:
                    summaries.append(f"[{output['role']}]: {content[:250]}")

    consensus = transcript.get("final_consensus", 0.0)
    current_round = transcript.get("current_round", 0)
    title = debate.get("title", "unbenannte Debatte")

    prompt = (
        f"Kontext aus der vorherigen Debatte (ID: {debate_id}):\n\n"
        f"Die Debatte '{title}' wurde nach "
        f"{current_round} Runden mit einem "
        f"Konsensgrad von {consensus * 100:.0f}% abgeschlossen.\n\n"
        f"Wichtigste Argumente:\n" + "\n\n".join(summaries[-10:]) + f"\n\nNeuer Fokus: {focus_topic or 'Vertiefung des Themas'}\n\n"
        "Führe diese Debatte fort und baue auf den vorherigen Ergebnissen auf."
    )
    return prompt


def build_followup_prompt(previous_debate: dict, new_topic: str) -> str:
    """Erstellt einen strukturierten Prompt mit Rollen-Anweisungen (P1)."""

    strongest: dict[str, list[str]] = {}
    for round_data in previous_debate.get("rounds", []):
        for output in round_data.get("agent_outputs", []):
            role = output.get("role", "unknown")
            if role not in strongest:
                strongest[role] = []
            content = output.get("content", "")
            if content:
                strongest[role].append(content[:200])

    prompt_parts = [
        f"""Du bist Teil eines Multi-Agenten-Debattensystems.

## Kontext
Eine vorherige Debatte zum Thema "{previous_debate.get("title", "")}"
wurde nach {previous_debate.get("current_round", "?")} Runden mit einem
Konsensgrad von {previous_debate.get("final_consensus", 0) * 100:.0f}% abgeschlossen.
""",
    ]

    for role, contents in strongest.items():
        prompt_parts.append(f"\n### {role.upper()} — Wichtigste Argumente:\n")
        for c in contents[-3:]:
            prompt_parts.append(f"- {c}")

    prompt_parts.extend(
        [
            "\n## Neue Aufgabe",
            f"Diskutiere nun: **{new_topic}**",
            "",
            "Richtlinien:",
            "1. Baue auf den vorherigen Erkenntnissen auf",
            "2. Widerlege oder bestätige frühere Schlussfolgerungen",
            "3. Bringe neue Perspektiven ein, die in der Origin-Debatte fehlten",
            "",
            "Halte den Prompt unter 4.000 Tokens.",
        ]
    )

    return "\n".join(prompt_parts)


def _build_transcript_for_followup(debate: dict) -> dict:
    """Hilfsfunktion: Erzeugt Transcript-Dict aus roher Debate-Daten."""
    result = debate.get("result", {})
    rounds = debate.get("rounds", [])
    if not rounds and result:
        rounds = result.get("rounds", [])
    return {
        "current_round": debate.get("current_round", result.get("current_round", 0)),
        "final_consensus": result.get("final_consensus", debate.get("final_consensus", 0.0)),
        "rounds": rounds,
    }


# ---------------------------------------------------------------------------
# Fork debate helper (Plan 19, P4)
# ---------------------------------------------------------------------------


def create_fork_debate(
    original_debate_id: str,
    new_title: str,
    fork_from_round: int | None,
    fork_reason: str | None,
    modified_personas: dict[str, str] | None,
    modified_prompt_variant: str | None,
    store: DebateStore,
    inherit_personas: bool = True,
    inherit_llm_profile: bool = True,
) -> dict:
    """Erstellt eine Deep-Copy einer Debatte als Fork (P4)."""
    import copy
    import uuid
    from datetime import UTC, datetime

    original = store.get(original_debate_id)
    if not original:
        raise ValueError(f"Original debate {original_debate_id} not found")

    new_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    # Deep-Copy des Original-Debatte-Dicts
    fork = copy.deepcopy(original)
    fork["debate_id"] = new_id
    fork["title"] = new_title
    fork["status"] = "pending"
    fork["created_at"] = now
    fork["updated_at"] = now
    fork["current_round"] = 0

    # Fork-Metadaten setzen
    fork["fork_info"] = {
        "parent_debate_id": original_debate_id,
        "fork_round": fork_from_round,
        "fork_reason": fork_reason,
    }

    # Runden nach fork_from_round abschneiden
    if fork_from_round is not None and fork_from_round >= 0:
        fork["rounds"] = [r for r in fork.get("rounds", []) if r.get("round", 0) <= fork_from_round]

    # Agent-Personas anpassen
    if modified_personas and isinstance(fork.get("request"), dict):
        original_personas = fork["request"].get("agent_persona_ids", {})
        original_personas.update(modified_personas)
        fork["request"]["agent_persona_ids"] = original_personas
    elif modified_personas and hasattr(fork.get("request", None), "agent_persona_ids"):
        req = fork["request"]
        for role, persona_id in modified_personas.items():
            setattr(req, "agent_persona_ids", {**req.agent_persona_ids, role: persona_id})

    # Prompt-Variante anpassen
    if modified_prompt_variant and isinstance(fork.get("request"), dict):
        fork["request"]["prompt_variant"] = modified_prompt_variant
    elif modified_prompt_variant and hasattr(fork.get("request", None), "prompt_variant"):
        fork["request"].prompt_variant = modified_prompt_variant

    # Vorbefüllung des case_text mit Kontext aus der Original-Debatte
    if isinstance(fork.get("request"), dict):
        original_case = fork["request"].get("case", {})
        if isinstance(original_case, dict):
            original_text = original_case.get("text", "")
        else:
            original_text = str(original_case)
        fork["request"]["case"] = {"text": original_text}
    elif hasattr(fork.get("request", None), "case"):
        # Fallback: bereits vorhanden
        pass

    # Fork-Historie im debate_json pflegen
    existing_forks = original.get("fork_history", [])
    fork["fork_history"] = existing_forks + [
        {
            "parent_id": original_debate_id,
            "fork_round": fork_from_round,
            "reason": fork_reason,
        }
    ]

    store.put(new_id, fork)
    return {
        "debate_id": new_id,
        "title": new_title,
        "status": "pending",
        "created_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# RAG integration for follow-up debates (Plan 19, P3)
# ---------------------------------------------------------------------------


async def on_debate_completed(debate_id: str, project_id: str):
    """Erzeugt automatisch ein DMS-Dokument mit den Debattenergebnissen (P3)."""
    from backend.persistence.project_store import ProjectStore
    from backend.services.dms.service import get_dms_for_project
    from backend.workflow.report_generator import WorkflowReportGenerator

    ps = ProjectStore()

    # Resolve DMS for the given project (fallback to _default)
    try:
        dms = get_dms_for_project(project_id, ps)
    except Exception:
        try:
            dms = get_dms_for_project("_default", ps)
            project_id = "_default"
        except Exception:
            logger.warning("Could not initialize DMS for debate completion callback")
            return None

    # Look up the debate directly in the known project
    debate_data = None
    try:
        project_dir = ps.get_project_dir(project_id)
        store = DebateStore(data_dir=project_dir / "debates")
        debate_data = store.get(debate_id)
    except Exception:
        pass

    if not debate_data:
        # Fallback: try default project store
        try:
            default_store = DebateStore()
            debate_data = default_store.get(debate_id)
        except Exception:
            pass

    if not debate_data:
        logger.warning("Debate %s not found for RAG document creation", debate_id)
        return None

    transcript = WorkflowReportGenerator._build_transcript(debate_data)
    document_text = _generate_rag_friendly_summary(transcript)

    try:
        doc = dms.db.add_document(
            project_id=project_id,
            filename=f"debate_{debate_id[:8]}.md",
            file_path="",
            file_type="md",
            file_size=len(document_text),
            original_filename=f"Debatte: {debate_data.get('title', 'unbenannt')}",
        )
        doc_id = doc["id"]

        # Write content to the document file path if available
        doc_entry = dms.db.get_document(doc_id)
        if doc_entry and doc_entry.get("file_path"):
            from pathlib import Path as PLPath

            PLPath(doc_entry["file_path"]).parent.mkdir(parents=True, exist_ok=True)
            PLPath(doc_entry["file_path"]).write_text(document_text, encoding="utf-8")
            proc_result = await dms.rag_pipeline.process_file(doc_id, doc_entry["file_path"])
            chunk_count = len(proc_result.get("chunk_ids", []))
            logger.info("Created DMS document %s for debate %s (%d chunks)", doc_id, debate_id, chunk_count)
        else:
            chunk_ids = dms.rag_pipeline.process_document(doc_id, document_text)
            logger.info("Created DMS document %s for debate %s (%d chunks)", doc_id, debate_id, len(chunk_ids))

        return doc_id
    except Exception as exc:
        logger.error("Failed to create DMS document for debate %s: %s", debate_id, exc)
        return None


def _generate_rag_friendly_summary(transcript: dict) -> str:
    """Generiert eine RAG-freundliche Zusammenfassung des Debattentranskripts."""
    title = transcript.get("title", "Debatte")
    case_text = transcript.get("case_text", "")
    status = transcript.get("status", "unknown")
    consensus = transcript.get("final_consensus", 0.0)
    current_round = transcript.get("current_round", 0)

    lines = [
        f"# Debatte: {title}",
        "",
        f"**Status:** {status}",
        f"**Runden:** {current_round}",
        f"**Konsensgrad:** {consensus * 100:.1f}%",
        "",
        "## Fallbeschreibung",
        case_text,
        "",
        "## Zusammenfassung der Argumente",
        "",
    ]

    role_names = {"strategist": "Stratege", "critic": "Kritiker", "optimizer": "Optimierer", "moderator": "Moderator"}

    for round_data in transcript.get("rounds", []):
        round_num = round_data.get("round", "?")
        round_consensus = round_data.get("consensus", 0.0)
        lines.append(f"### Runde {round_num} (Konsens: {round_consensus * 100:.1f}%)")
        for output in round_data.get("agent_outputs", []):
            role = output.get("role", "unknown")
            role_label = role_names.get(role, role.capitalize())
            content = output.get("content", "").strip()
            if content:
                lines.append(f"\n**{role_label}:**\n{content}\n")

    final_output = transcript.get("output", "")
    if final_output:
        lines.extend(["## Endergebnis", final_output, ""])

    lines.append("---")
    lines.append(f"*Dies ist eine automatisch generierte Zusammenfassung der Debatte '{title}' für die RAG-Wiederverwendung.*")

    return "\n".join(lines)


def resolve_rag_context_with_debate_results(
    project_id: str,
    case_text: str,
    document_ids: list[str] | None = None,
    rag_auto_retrieve: bool = False,
    include_debate_results: bool = True,
    store: DebateStore | None = None,
) -> tuple[str, int]:
    """Erweitert RAG-Kontext um vorherige Debattenergebnisse (P3)."""
    from backend.services.dms.service import get_dms_for_project

    analysis_text = _load_analysis_text(project_id)

    try:
        dms = get_dms_for_project(project_id)
    except Exception:
        if analysis_text:
            return analysis_text, 0
        return "", 0

    all_chunks = []

    # Standard-DMS-RAG
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

    # Zusätzlich: Debattenergebnisse als Kontext einbeziehen
    if include_debate_results:
        try:
            # Finde alle abgeschlossenen Debatten des Projekts
            if store is None:
                store = DebateStore()

            # Suche im Projektverzeichnis
            from backend.persistence.project_store import ProjectStore

            ps = ProjectStore()
            project_dir = ps.get_project_dir(project_id)
            project_store = DebateStore(data_dir=project_dir / "debates")

            debates = project_store.list_all(limit=50)
            debate_count = 0

            for d in debates:
                if d.get("status") in ("completed",) and d.get("debate_id") != "":
                    debate_json = d
                    # Extrahiere Transcript-Text
                    debate_json.get("request", {})
                    transcript = _build_transcript_for_followup(debate_json)

                    # Baue Zusammenfassung
                    summary = _generate_rag_friendly_summary(transcript)

                    # Chunke die Zusammenfassung
                    from backend.services.dms.chunker import TextChunker

                    chunker = TextChunker()
                    raw_chunks = chunker.chunk(summary)
                    chunks = [{"text": t, "document_id": f"debate_result_{d.get('debate_id', '')[:8]}"} for t in raw_chunks]
                    all_chunks.extend(chunks[:3])  # Max 3 Chunks pro Debatte

                    debate_count += 1
                    if debate_count >= 5:  # Max. 5 vorherige Ergebnisse
                        break
        except Exception as exc:
            logger.warning("Failed to include debate results in RAG context: %s", exc)

    if not all_chunks:
        if analysis_text:
            logger.info("Document analysis available but no chunks — returning analysis-only RAG context")
            return analysis_text, 0
        return "", 0

    # Deduplizierung
    seen_texts: set[str] = set()
    unique_chunks: list[dict] = []
    for chunk in all_chunks:
        text = chunk.get("text", "")
        if text and text not in seen_texts:
            seen_texts.add(text)
            unique_chunks.append(chunk)

    rag_context = dms.format_rag_context(unique_chunks)

    if analysis_text:
        rag_context = f"{analysis_text}\n\n=== DOCUMENT EXCERPTS ===\n\n{rag_context}" if rag_context else analysis_text

    return rag_context, len(unique_chunks)
