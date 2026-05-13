"""Node functions for LangGraph debate workflow.

Sprint 3: Real LLM calls via litellm with profile-based configuration.
Sprint 5: Web search integration (required / optional modes).
Falls back to dummy output if litellm is not available or LLM call fails.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.api.events import publish_async
from backend.core.config import settings
from backend.models.project import ProjectConfig
from backend.services.llm_service import GenerationResult, LLMService
from backend.services.profile_service import ProfileService
from backend.services.prompt_service import PromptService
from backend.services.web_search import (
    WebSearchTool,
    extract_search_markers,
    extract_search_queries,
    format_search_results,
)
from backend.workflow.state import (
    AgentOutputState,
    DebateState,
    RoundDataState,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level service singletons (lazy-initialized)
#
# Project-scoped services are cached per project_id to avoid re-creating
# ProfileService/PromptService on every node invocation.  The global
# (no-project) singletons remain for backwards compatibility.
# ---------------------------------------------------------------------------

_profile_service: ProfileService | None = None
_prompt_service: PromptService | None = None
_search_tool: WebSearchTool | None = None

# Per-project caches: project_id → service instance
_profile_service_cache: dict[str, ProfileService] = {}
_prompt_service_cache: dict[str, PromptService] = {}


def _get_project_dir(project_id: str | None) -> Path | None:
    """Return the project directory for a given project_id, or None."""
    if not project_id:
        return None
    from backend.persistence.project_store import ProjectStore

    store = ProjectStore()
    return store.get_project_dir(project_id)


def _get_project_config(project_id: str | None) -> ProjectConfig | None:
    """Return the ProjectConfig for a given project_id, or None."""
    if not project_id:
        return None
    from backend.persistence.project_store import ProjectStore

    store = ProjectStore()
    project = store.get(project_id)
    return project.config if project else None


def _get_profile_service(project_id: str | None = None) -> ProfileService:
    """Return a ProfileService, project-scoped if project_id is given."""
    global _profile_service
    if project_id:
        if project_id not in _profile_service_cache:
            config = _get_project_config(project_id)
            _profile_service_cache[project_id] = ProfileService(project_config=config)
        return _profile_service_cache[project_id]
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service


def _get_prompt_service(project_id: str | None = None) -> PromptService:
    """Return a PromptService wired to the project's ProfileService for DB-first prompt resolution."""
    global _prompt_service
    profile_svc = _get_profile_service(project_id)
    if project_id:
        if project_id not in _prompt_service_cache:
            _prompt_service_cache[project_id] = PromptService(
                profile_service=profile_svc,
            )
        return _prompt_service_cache[project_id]
    if _prompt_service is None:
        _prompt_service = PromptService(profile_service=profile_svc)
    return _prompt_service


def _get_search_tool() -> WebSearchTool:
    global _search_tool
    if _search_tool is None:
        _search_tool = WebSearchTool(
            url=settings.searxng_url,
            max_results=settings.searxng_max_results,
            region=settings.searxng_region,
        )
    return _search_tool


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def initialize_node(state: DebateState) -> dict:
    """Set up initial runtime state."""
    return {
        "current_round": 1,
        "current_agent_index": 0,
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "validation_report": [],
        "used_variant": state.get("prompt_variant", "default"),
        "anomalies": [],
    }


async def run_agent_node(state: DebateState) -> dict:
    """Run the current agent with a real LLM call.

    Uses the configured LLM profile and prompt variant.  Falls back to
    dummy output if the LLM call fails (e.g. missing API key, litellm
    not installed).
    """
    agents = state["agent_profile"]
    idx = state["current_agent_index"]
    agent = agents[idx]
    role = agent["role"]
    session_id = state.get("session_id", "")
    project_id = state.get("project_id")

    # Profile configuration from state
    llm_profile_id = state.get("llm_profile_id", "openrouter-claude")
    prompt_variant = state.get("prompt_variant", "default")
    persona_ids = state.get("agent_persona_ids", {})
    language = state.get("language", "de")
    search_mode = state.get("search_mode", "off")
    agent_total = len(agents)

    # --- Publish: agent preparing (immediate feedback before any heavy work) ---
    await publish_async(
        session_id,
        "agent_preparing",
        {
            "type": "agent_preparing",
            "round": state["current_round"],
            "role": role,
            "agent_index": idx,
            "agent_total": agent_total,
            "phase": "resolving_profile",
        },
    )

    # --- Resolve LLM profile info ---
    llm_profile_obj = _get_profile_service(project_id).get_llm_profile(llm_profile_id)
    model_name = llm_profile_obj.model if llm_profile_obj else "N/A"
    provider_name = llm_profile_obj.provider.value if llm_profile_obj else "N/A"

    # --- Publish: agent started (profile resolved, now resolving prompts) ---
    await publish_async(
        session_id,
        "agent_started",
        {
            "round": state["current_round"],
            "role": role,
            "profile": llm_profile_id,
            "model": model_name,
            "provider": provider_name,
            "agent_index": idx,
            "agent_total": agent_total,
        },
    )

    # --- Publish: resolving prompts ---
    await publish_async(
        session_id,
        "agent_preparing",
        {
            "type": "agent_preparing",
            "round": state["current_round"],
            "role": role,
            "agent_index": idx,
            "agent_total": agent_total,
            "phase": "resolving_prompts",
        },
    )

    # --- Resolve system prompt ---
    project_dir = _get_project_dir(project_id)
    system_prompt = _resolve_system_prompt(
        role,
        prompt_variant,
        persona_ids,
        state,
        language,
        search_mode,
        project_id=project_id,
        project_dir=project_dir,
    )

    # --- Build user prompt ---
    user_prompt = _build_user_prompt(state, role, language)

    # --- OOB: Inject out-of-band user context before LLM call ---
    try:
        from backend.services.debate_workflow import consume_oob, get_oob_for_debate

        debate_id = state.get("debate_id", "")
        if debate_id:
            oob_inputs = get_oob_for_debate(debate_id)
            # Filter for this agent role and round
            relevant_oob = [oob for oob in oob_inputs if _is_oob_relevant(oob, role, state["current_round"])]
            if relevant_oob:
                oob_context = "\n\n--- ADDITIONAL CONTEXT (User) ---\n"
                oob_context += "\n".join(f"- {oob['content']}" for oob in relevant_oob)
                user_prompt += oob_context
                # Mark as consumed
                consume_oob(debate_id, [oob["oob_id"] for oob in relevant_oob])
                # Emit SSE event for visualization
                await publish_async(
                    session_id,
                    "oob_consumed",
                    {
                        "type": "oob_consumed",
                        "oob_ids": [oob["oob_id"] for oob in relevant_oob],
                        "by_agent": role,
                        "round": state["current_round"],
                    },
                )
                logger.info(
                    "Injected %d OOB inputs for %s (round %d)",
                    len(relevant_oob),
                    role,
                    state["current_round"],
                )
    except Exception as exc:
        logger.warning("OOB injection failed (non-fatal): %s", exc)

    # --- HITL: Inject user context before LLM call ---
    try:
        from backend.workflow.hitl.nodes import build_inject_context

        hitl_context = build_inject_context(state, role)
        if hitl_context:
            user_prompt += hitl_context
            logger.info(
                "HITL inject context added for %s (round %d)",
                role,
                state["current_round"],
            )
    except Exception as exc:
        logger.warning("HITL inject failed (non-fatal): %s", exc)

    # --- Required mode: auto-search before LLM call ---
    if search_mode == "required":
        user_prompt = await _perform_required_search(state, role, language, user_prompt, session_id)

    # --- Publish: LLM call starting ---
    await publish_async(
        session_id,
        "llm_call_started",
        {
            "type": "llm_call_started",
            "round": state["current_round"],
            "role": role,
            "model": model_name,
            "provider": provider_name,
            "agent_index": idx,
            "agent_total": agent_total,
        },
    )

    # --- LLM call with graceful fallback ---
    llm_failed = False
    anomaly_detail = ""
    gen_result: GenerationResult | None = None
    try:
        llm_service = LLMService(
            profile_id=llm_profile_id,
            profile_service=_get_profile_service(project_id),
        )
        logger.info(
            "Agent %s (round %d): calling LLM profile '%s' (model=%s, api_base=%s)",
            role,
            state["current_round"],
            llm_profile_id,
            llm_service.profile.model if llm_service.profile else "N/A",
            llm_service.profile.api_base if llm_service.profile else "N/A",
        )
        gen_result = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=agent.get("temperature", 0.7),
        )
        content = gen_result.content
        tokens_in = gen_result.tokens_in
        tokens_out = gen_result.tokens_out
        duration_ms = gen_result.duration_ms
        model_used = gen_result.model
        tokens = tokens_out if tokens_out > 0 else len(content.split())
        logger.info(
            "Agent %s (round %d): LLM response (%d tokens in, %d out, %dms)",
            role,
            state["current_round"],
            tokens_in,
            tokens_out,
            duration_ms,
        )

        # --- Optional mode: check for [SEARCH: ...] markers ---
        if search_mode == "optional":
            content = await _perform_optional_search(content, role, language, session_id, state)
            tokens = len(content.split())

    except Exception as exc:
        logger.error(
            "LLM call FAILED for agent %s (round %d, profile=%s): %s",
            role,
            state["current_round"],
            llm_profile_id,
            exc,
            exc_info=True,
        )
        llm_failed = True
        anomaly_detail = f"{type(exc).__name__}: {exc}"
        content = f"[{role}] Round {state['current_round']}: LLM call failed ({anomaly_detail}). Profile: {llm_profile_id}"
        tokens = len(content.split())
        tokens_in = 0
        tokens_out = 0
        duration_ms = 0
        model_used = model_name

    output: AgentOutputState = {
        "role": role,
        "content": content,
        "tokens_used": tokens,
    }

    # --- Publish: agent completed ---
    await publish_async(
        session_id,
        "agent_output",
        {
            "round": state["current_round"],
            "role": role,
            "content": content,
            "tokens_used": tokens,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "duration_ms": duration_ms,
            "model": model_used,
        },
    )

    result: dict = {
        "agent_outputs": [output],
        "current_agent_index": idx + 1,
        "current_draft": state.get("current_draft", "") + "\n" + content,
    }

    # Track anomaly if LLM call failed
    if llm_failed:
        result["anomalies"] = [f"LLM call failed for {role} in round {state['current_round']} ({anomaly_detail})"]

    return result


# ---------------------------------------------------------------------------
# Web search helpers
# ---------------------------------------------------------------------------


async def _perform_required_search(
    state: DebateState,
    role: str,
    language: str,
    user_prompt: str,
    session_id: str,
) -> str:
    """Required mode: auto-search before LLM call and inject results into prompt."""
    search_tool = _get_search_tool()
    queries = extract_search_queries(state["context"], role)
    if not queries:
        return user_prompt

    all_results = []
    for query in queries:
        try:
            results = await search_tool.search(query)
            all_results.extend(results)
            # Publish SSE event for each search
            await publish_async(
                session_id,
                "web_search",
                {
                    "type": "web_search",
                    "round": state["current_round"],
                    "role": role,
                    "query": query,
                    "result_count": len(results),
                    "results": results,
                },
            )
        except Exception as exc:
            logger.warning("Web search failed for '%s': %s", query, exc)

    if all_results:
        user_prompt += format_search_results(all_results, language)
    return user_prompt


async def _perform_optional_search(
    content: str,
    role: str,
    language: str,
    session_id: str,
    state: DebateState,
) -> str:
    """Optional mode: check for [SEARCH: ...] markers and fulfill them."""
    markers = extract_search_markers(content)
    if not markers:
        return content

    search_tool = _get_search_tool()
    all_results = []
    for query in markers:
        try:
            results = await search_tool.search(query)
            all_results.extend(results)
            await publish_async(
                session_id,
                "web_search",
                {
                    "type": "web_search",
                    "round": state["current_round"],
                    "role": role,
                    "query": query,
                    "result_count": len(results),
                    "results": results,
                },
            )
        except Exception as exc:
            logger.warning("Web search failed for '%s': %s", query, exc)

    if all_results:
        content += format_search_results(all_results, language)
    return content


def _append_language_instruction(prompt: str, language: str) -> str:
    """Append a language instruction to a system prompt.

    Ensures the LLM responds in the debate language even when the persona
    template is written in a different language (e.g. English persona with
    German debate language).
    """
    if language == "en":
        instruction = "\n\nIMPORTANT: You MUST respond in English. Write all your analysis and conclusions in English."
    else:
        instruction = "\n\nWICHTIG: Du MUSST auf Deutsch antworten. Schreibe deine gesamte Analyse und deine Schlussfolgerungen auf Deutsch."
    return prompt + instruction


def _append_search_instruction(prompt: str, search_mode: str, language: str = "de") -> str:
    """Append web search instructions to a system prompt based on the search mode."""
    if search_mode == "off":
        return prompt

    if search_mode == "required":
        if language == "en":
            instruction = (
                "\n\n## Web Research\n"
                "You have access to current web search results which are provided "
                "in the user message under 'Web Research'. You MUST incorporate and "
                "reference this external information in your analysis. "
                "Cite sources where possible. If search results contradict your analysis, "
                "address the discrepancy explicitly."
            )
        else:
            instruction = (
                "\n\n## Web-Recherche\n"
                "Du hast Zugriff auf aktuelle Websuchergebnisse, die in der "
                "Benutzernachricht unter 'Web-Recherche' bereitgestellt werden. "
                "Du MUSST diese externen Informationen in deine Analyse einbeziehen "
                "und darauf verweisen. Zitiere Quellen, wo möglich. Wenn Suchergebnisse "
                "deiner Analyse widersprechen, gehe explizit auf die Diskrepanz ein."
            )
    elif search_mode == "optional":
        if language == "en":
            instruction = (
                "\n\n## Web Search Capability\n"
                "You have access to web search. If you need to verify facts, find current "
                "information, or research specific claims, include [SEARCH: your search query] "
                "in your response. Each [SEARCH: ...] marker will be fulfilled and the results "
                "appended to your output. Use this capability sparingly and only when factual "
                "verification is needed."
            )
        else:
            instruction = (
                "\n\n## Web-Suche\n"
                "Du hast Zugriff auf Websuche. Wenn du Fakten überprüfen, aktuelle "
                "Informationen finden oder spezifische Aussagen recherchieren musst, "
                "füge [SEARCH: deine Suchanfrage] in deine Antwort ein. Jeder "
                "[SEARCH: ...]-Marker wird ausgeführt und die Ergebnisse deiner "
                "Ausgabe angehängt. Nutze diese Fähigkeit sparsam und nur wenn "
                "faktische Überprüfung sinnvoll ist."
            )
    else:
        return prompt

    return prompt + instruction


def _resolve_system_prompt(
    role: str,
    prompt_variant: str,
    persona_ids: dict[str, str],
    state: DebateState,
    language: str = "de",
    search_mode: str = "off",
    *,
    project_id: str | None = None,
    project_dir: Path | None = None,
) -> str:
    """Resolve the system prompt for an agent role.

    Priority: prompt service template (language-aware) → persona system_prompt → generic default.

    The prompt service is tried first because it supports language variants
    (e.g. ``strategist.md`` for German, ``strategist-en.md`` for English).
    Persona system prompts are used as fallback when no template exists.

    If ``project_dir`` is provided, project-specific prompt templates are
    checked first (``{project_dir}/prompts/{variant}/{role}.md``).
    """
    # 1. Try prompt service template (language-aware) — highest priority
    try:
        rendered = _get_prompt_service(project_id).render(
            variant=prompt_variant,
            role=role,
            variables={"context": state["context"]},
            language=language,
            project_dir=project_dir,
        )
        logger.debug("Using prompt template for %s/%s (lang=%s)", prompt_variant, role, language)
        prompt = rendered
    except FileNotFoundError:
        logger.debug("No prompt template for %s/%s (lang=%s), trying persona", prompt_variant, role, language)
        prompt = None

    # 2. Try persona-specific system prompt (always in persona's language)
    if prompt is None:
        persona_id = persona_ids.get(role)
        if persona_id:
            persona = _get_profile_service(project_id).get_agent_persona(persona_id)
            if persona:
                logger.debug("Using persona system_prompt for %s (persona=%s)", role, persona_id)
                prompt = persona.system_prompt
                # Append language instruction so the LLM responds in the debate language
                prompt = _append_language_instruction(prompt, language)

    # 3. Generic fallback (language-aware)
    if prompt is None:
        logger.warning(
            "No prompt found for %s/%s (lang=%s), using generic default",
            prompt_variant,
            role,
            language,
        )
        if language == "en":
            prompt = f"You are a {role} agent analyzing a legal case. Provide your expert analysis."
        else:
            prompt = f"Du bist ein {role}-Agent, der einen Rechtsfall analysiert. Gib deine Expertenanalyse ab."

    # 4. Append search instructions based on mode
    prompt = _append_search_instruction(prompt, search_mode, language)

    return prompt


def _build_user_prompt(state: DebateState, role: str, language: str = "de") -> str:
    """Build the user prompt for an agent based on debate context."""
    parts = [f"## Case\n{state['context']}"]

    if state.get("rag_context"):
        parts.append(f"## Additional Context\n{state['rag_context']}")

    # Include the running draft (accumulated agent outputs so far)
    draft = state.get("current_draft", "").strip()
    if draft:
        parts.append(f"## Previous Analysis\n{draft}")

    # Include previous round summaries
    rounds = state.get("rounds", [])
    if rounds:
        parts.append("## Previous Rounds Summary")
        for rd in rounds:
            parts.append(f"Round {rd['round']}: Consensus = {rd['consensus']:.2f}")

    parts.append(f"## Your Role: {role}")

    if language == "en":
        parts.append("Please provide your analysis based on the case and previous discussion.")
        parts.append(
            "IMPORTANT: If you disagree with the majority position or previous analyses, "
            "you MUST clearly state your dissent and explain your reasoning. "
            "Document any minority viewpoints explicitly. "
            "Do not simply agree for the sake of consensus — intellectual honesty is required."
        )
    else:
        parts.append("Bitte gib deine Analyse basierend auf dem Fall und der bisherigen Diskussion.")
        parts.append(
            "WICHTIG: Wenn du mit der Mehrheitsposition oder früheren Analysen "
            "nicht einverstanden bist, musst du deine abweichende Meinung klar "
            "darlegen und deine Begründung erklären. "
            "Dokumentiere explizit alle Minderheitenstandpunkte. "
            "Stimme nicht einfach nur der Konsens wegen zu — "
            "intellektuelle Ehrlichkeit ist erforderlich."
        )

    return "\n\n".join(parts)


async def check_consensus_node(state: DebateState) -> dict:
    """Evaluate consensus (linear progression toward threshold).

    TODO: Replace with LLM-based consensus evaluation in a future sprint.

    If any LLM failures occurred in this round, consensus is capped at 0
    to prevent false consensus claims.
    """
    current_round = state["current_round"]
    max_rounds = state["max_rounds"]
    threshold = state["threshold"]
    session_id = state.get("session_id", "")
    anomalies = state.get("anomalies", [])
    enable_extra_rounds = state.get("enable_extra_rounds", False)

    # Check if any LLM failures occurred in this round
    has_failures = any("LLM call failed" in a for a in anomalies)

    if has_failures:
        # Cap consensus at 0 when LLM failures occurred — no false consensus
        consensus = 0.0
        logger.warning(
            "Round %d: LLM failures detected (%d anomalies), consensus capped at 0",
            current_round,
            len(anomalies),
        )
    else:
        # Linear consensus progression
        consensus = min(threshold, current_round / max_rounds * threshold * 1.2)

    # Include agent outputs from this round in the round data
    round_data: RoundDataState = {
        "round": current_round,
        "consensus": round(consensus, 3),
        "agent_outputs": list(state.get("agent_outputs", [])),
    }

    # --- Publish: round completed ---
    total_tokens = sum(ao.get("tokens_used", 0) for ao in state.get("agent_outputs", []))
    await publish_async(
        session_id,
        "round_update",
        {
            "round": current_round,
            "consensus": round(consensus, 3),
            "agent_count": len(state.get("agent_outputs", [])),
            "total_tokens": total_tokens,
        },
    )

    # --- Extension logic: reset extension_granted for the new round ---
    # When a new round starts (current_round incremented), reset the decision
    next_round = current_round + 1
    extension_granted = None  # Reset — must be decided again for the new round

    # If consensus is NOT reached and extra rounds are enabled,
    # the HITL extension_request_node will decide whether to grant more rounds
    needs_extension = (
        enable_extra_rounds and consensus < threshold and next_round <= max_rounds + 2  # Allow up to 2 extra rounds beyond max
    )

    return {
        "rounds": [round_data],
        "final_consensus": round(consensus, 3),
        "current_agent_index": 0,
        "current_round": next_round,
        "extension_granted": extension_granted,
        "needs_extension": needs_extension,
    }


async def complete_node(state: DebateState) -> dict:
    """Finalize the debate."""
    session_id = state.get("session_id", "")
    anomalies = state.get("anomalies", [])

    # --- Publish: debate completed ---
    await publish_async(
        session_id,
        "status_change",
        {
            "status": "completed",
            "final_consensus": state.get("final_consensus", 0.0),
            "total_rounds": state.get("current_round", 1) - 1,
        },
    )

    return {
        "output": state.get("current_draft", "No output generated."),
        "anomalies": anomalies,
    }


# ---------------------------------------------------------------------------
# Conditional edge functions
# ---------------------------------------------------------------------------


def should_continue_agents(state: DebateState) -> str:
    """Check if more agents need to run in this round."""
    if state["current_agent_index"] < len(state["agent_profile"]):
        return "next_agent"
    return "check_consensus"


def should_continue_rounds(state: DebateState) -> str:
    """Check if consensus reached or max rounds exceeded.

    Note: current_round is incremented by check_consensus_node before
    this function is called, so we use ``>`` (strict) to allow exactly
    max_rounds iterations.

    Extension logic: if enable_extra_rounds is set and the extension was
    granted by the moderator, allow additional rounds beyond max_rounds.
    """
    if state["final_consensus"] >= state["threshold"]:
        return "complete"

    current_round = state["current_round"]
    max_rounds = state["max_rounds"]
    extension_granted = state.get("extension_granted")

    # Within normal round budget
    if current_round <= max_rounds:
        return "next_round"

    # Beyond normal budget — only continue if extension was explicitly granted
    # and we haven't exceeded max + 2 extra rounds (hard safety cap)
    hard_cap = max_rounds + 2
    if extension_granted and current_round <= hard_cap:
        return "next_round"

    return "complete"


# ---------------------------------------------------------------------------
# OOB helper
# ---------------------------------------------------------------------------

_AGENT_ORDER = ["strategist", "critic", "optimizer", "moderator"]


def _is_oob_relevant(oob: dict, role: str, current_round: int) -> bool:
    """Check if an OOB input is relevant for the given agent role and round."""
    target = oob.get("target", {})
    target_type = target.get("type", "")

    if target_type == "specific_agent":
        return target.get("agent_role") == role and (target.get("round") is None or target.get("round") == current_round)

    if target_type == "next_agent":
        prev_role = target.get("current_agent_role", "")
        idx = _AGENT_ORDER.index(prev_role) if prev_role in _AGENT_ORDER else -1
        next_role = _AGENT_ORDER[idx + 1] if 0 <= idx < len(_AGENT_ORDER) - 1 else ""
        if not next_role:
            # If prev_role is unknown (e.g. "input") or is the last agent,
            # default to the first agent in the order so the OOB doesn't get lost
            next_role = _AGENT_ORDER[0]
        return role == next_role

    if target_type == "all_future":
        from_round = target.get("from_round", 0)
        return current_round >= from_round

    if target_type == "current_active":
        return True

    return False
