"""Debate workflow execution service.

Extracted from ``backend.api.routers.debate`` to separate business logic
(title generation, RAG resolution, LangGraph orchestration, OOB queues,
cancellation state) from HTTP routing concerns.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from backend.api.events import publish_async
from backend.core.config import is_service_llm_eligible, settings  # noqa: F401
from backend.models.schemas import AuditEvent, DebateStatus
from backend.persistence.audit import AuditService
from backend.persistence.debate_store import DebateStore
from backend.services.debate import (  # noqa: F401  # re-exports for backward compat
    SYSTEM_PROMPT_TITLES,
    _fallback_title,
    _format_analysis_for_rag,
    _load_analysis_text,
    _oob_queues,
    _post_process_title,
    _select_service_llm,
    clear_cancel,
    clear_oob_queue,
    consume_oob,
    enqueue_oob,
    generate_debate_title,
    get_oob_for_debate,
    is_cancelled,
    mark_cancelled,
    resolve_rag_context,
    resolve_rag_context_with_debate_results,
    validate_title,
)
from backend.services.dms.service import get_dms_for_project

logger = logging.getLogger(__name__)


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


def build_rag_preview(project_id: str, document_ids: list[str], project_store=None) -> str:
    """Build a short preview of RAG context for the response."""
    if not document_ids:
        return ""
    try:
        dms = get_dms_for_project(project_id)

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
    enable_extra_rounds, include_document_analysis.

    If language is None, resolves to the user's configured UI language
    (from config/settings.yaml), falling back to 'de' if not configured.
    """
    from backend.api.deps import get_user_language

    user_lang = get_user_language()

    from backend.core.llm_id_aliases import get_default_llm_profile_id, resolve_llm_id

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
        include_document_analysis = getattr(req, "include_document_analysis", False)
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
        llm_profile_id = resolve_llm_id(req.get("llm_profile_id", "")) or get_default_llm_profile_id() or settings.service_llm_profile_id
        prompt_variant = req.get("prompt_variant", "default")
        agent_persona_ids = req.get("agent_persona_ids", {})
        language = req.get("language") or user_lang
        document_ids = req.get("document_ids", [])
        rag_auto_retrieve = req.get("rag_auto_retrieve", False)
        include_debate_results = req.get("include_debate_results", False)
        include_document_analysis = req.get("include_document_analysis", False)
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
        "include_document_analysis": include_document_analysis,
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
# Core workflow orchestration
# ---------------------------------------------------------------------------


async def run_debate_workflow(
    debate_id: str,
    project_id: str,
    audit: AuditService,
    store: DebateStore,
    project_store=None,
) -> None:
    """Run the LangGraph workflow for a debate (called as background task).

    The ``project_store`` parameter is kept for backward compatibility but
    is no longer required.
    """
    debate = store.get(debate_id)
    if not debate:
        return

    try:
        await _run_debate_workflow_inner(debate_id, project_id, audit, store, debate)
    except Exception as exc:
        logger.error("Debate %s failed with unhandled exception: %s", debate_id, exc, exc_info=True)
        store.update(debate_id, status=DebateStatus.FAILED, updated_at=datetime.now(UTC))
        clear_cancel(debate_id)


async def _run_debate_workflow_inner(
    debate_id: str,
    project_id: str,
    audit: AuditService,
    store: DebateStore,
    debate: dict,
) -> None:
    """Inner workflow body — separated so the outer wrapper can catch all exceptions."""

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

    fields["title"] = generated_title
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
        include_document_analysis=fields.get("include_document_analysis", False),
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
        "bundle_ids": fields.get("bundle_ids", []),
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
        "hitl_enabled": False,
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

    # Log which LLM profile this debate will use — helps debug hardcoded-model bugs
    from backend.services.profile_service import ProfileService

    _llm_profile = ProfileService().get_llm_profile(fields["llm_profile_id"]) if fields["llm_profile_id"] else None
    if _llm_profile:
        logger.info(
            "Debate %s starting with LLM profile %s (model=%s, provider=%s)",
            debate_id,
            _llm_profile.id,
            _llm_profile.model,
            _llm_profile.provider.value,
        )
    else:
        logger.warning(
            "Debate %s has no resolvable LLM profile (requested=%s) — will fall back at agent-run time",
            debate_id,
            fields["llm_profile_id"],
        )

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
                title=fields.get("title", ""),
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
    """Erzeugt automatisch ein DMS-Dokument mit den Debattenergebnissen (P3).

    Multi-tenant safety: the previous implementation silently fell back
    to the ``_default`` project when ``project_id`` could not be
    resolved, which caused a completed debate from one tenant to land
    in another tenant's DMS. We now fail loud (log + return) instead of
    writing the summary to a different project.
    """
    from backend.api.deps import get_case_dir
    from backend.services.dms.service import get_dms_for_project
    from backend.workflow.report_generator import WorkflowReportGenerator

    # Resolve DMS strictly for the given project. No fallback to
    # _default — that path is a cross-tenant write hazard.
    try:
        dms = get_dms_for_project(project_id)
    except Exception as exc:
        logger.warning(
            "Could not initialize DMS for project %s (debate %s): %s — skipping RAG document creation",
            project_id,
            debate_id,
            exc,
        )
        return None

    # Look up the debate directly in the known project. No fallback to
    # the global default store either.
    debate_data = None
    try:
        project_dir = get_case_dir(project_id)
        store = DebateStore(data_dir=project_dir / "debates")
        debate_data = store.get(debate_id)
    except Exception as exc:
        logger.warning(
            "Could not load debate %s from project %s store: %s",
            debate_id,
            project_id,
            exc,
        )

    if not debate_data:
        logger.warning(
            "Debate %s not found in project %s — skipping RAG document creation",
            debate_id,
            project_id,
        )
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
