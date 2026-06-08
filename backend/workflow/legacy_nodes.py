"""Node functions for LangGraph debate workflow.

Sprint 3: Real LLM calls via litellm with profile-based configuration.
Sprint 5: Web search integration (required / optional modes).
Falls back to dummy output if litellm is not available or LLM call fails.
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.api.events import publish_async
from backend.core.config import is_service_llm_eligible, settings
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
from backend.workflow.nodes._draft_helpers import truncate_running_draft
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
    from backend.api.deps import get_case_dir

    return get_case_dir(project_id)


def _get_project_config(project_id: str | None) -> ProjectConfig | None:
    """Return the ProjectConfig for a given project_id, or None."""
    if not project_id:
        return None
    from backend.api.deps import get_project_store

    store = get_project_store()
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
    """Return a PromptService for module-based prompt resolution."""
    global _prompt_service
    if project_id:
        if project_id not in _prompt_service_cache:
            _prompt_service_cache[project_id] = PromptService()
        return _prompt_service_cache[project_id]
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


def _get_search_tool() -> WebSearchTool:
    """Return (or lazily create) search tool."""
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
        # --- HITL fields (safe defaults when HITL is not enabled) ---
        "interactions": [],
        "active_interrupt": None,
        "hitl_enabled": state.get("hitl_enabled", False),
        "hitl_mode": state.get("hitl_mode", "off"),
        "auto_query_threshold": state.get("auto_query_threshold", 0.4),
        "max_interrupts_per_round": state.get("max_interrupts_per_round", 3),
        "interrupt_timeout_seconds": state.get("interrupt_timeout_seconds", 300),
        "pending_injects": [],
        "round_interrupt_count": 0,
        "is_paused": False,
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
    from backend.core.llm_id_aliases import get_default_llm_profile_id, resolve_llm_id

    llm_profile_id = resolve_llm_id(state.get("llm_profile_id", "")) or get_default_llm_profile_id() or settings.service_llm_profile_id
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

    # Fallback: if configured profile doesn't exist, try to find an eligible local profile
    if llm_profile_obj is None:
        logger.warning(
            "LLM profile '%s' not found, attempting fallback to available profile",
            llm_profile_id,
        )
        try:
            all_profiles = _get_profile_service(project_id).list_llm_profiles()
            local_profiles = [p for p in all_profiles if is_service_llm_eligible(p)[0] and p.provider.value in ("local", "ollama")]
            if local_profiles:
                llm_profile_obj = local_profiles[0]
                llm_profile_id = llm_profile_obj.id
                logger.info("Fallback: using local profile '%s'", llm_profile_id)
            elif all_profiles:
                eligible = [p for p in all_profiles if is_service_llm_eligible(p)[0]]
                llm_profile_obj = (eligible or all_profiles)[0]
                llm_profile_id = llm_profile_obj.id
                logger.info("Fallback: using profile '%s'", llm_profile_id)
        except Exception as exc:
            logger.error("Profile fallback resolution failed: %s", exc)

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
    # Priority 0: Pre-resolved prompt from bundle resolution (ComposerService)
    pre_resolved = agent.get("system_prompt")
    if pre_resolved:
        logger.debug("Using bundle-resolved system_prompt for %s", role)
        system_prompt = _append_language_instruction(pre_resolved, language)
        system_prompt = _append_search_instruction(system_prompt, search_mode, language)
    else:
        # Legacy path: PromptService template → ComposerService module → Persona → Generic
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
        logger.debug("OOB check: debate_id=%r, role=%s, round=%d", debate_id, role, state.get("current_round", 0))
        if debate_id:
            oob_inputs = get_oob_for_debate(debate_id)
            logger.debug("OOB check: %d pending OOB inputs for debate %s", len(oob_inputs), debate_id)
            # Filter for this agent role and round
            relevant_oob = [oob for oob in oob_inputs if _is_oob_relevant(oob, role, state["current_round"], state)]
            logger.debug("OOB check: %d relevant for role=%s", len(relevant_oob), role)
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
            extra_kwargs=agent.get("model_params"),
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
        # Sprint 39 (H2 fix): bound the running ``current_draft``
        # log via the shared helper.  Previously the legacy
        # ``run_agent_node`` accumulated without any cap, so a
        # long debate would grow the draft without bound and bloat
        # every subsequent agent's user prompt.  See
        # ``_draft_helpers.py`` for the tail-only truncation
        # semantics shared with the wf-compiler flow.
        "current_draft": truncate_running_draft(state.get("current_draft", "") + "\n" + content),
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


# Language instruction templates for all supported locales
_LANGUAGE_INSTRUCTIONS = {
    "en": "\n\nIMPORTANT: You MUST respond in English. Write all your analysis and conclusions in English.",
    "de": "\n\nWICHTIG: Du MUSST auf Deutsch antworten. Schreibe deine gesamte Analyse und deine Schlussfolgerungen auf Deutsch.",
    "fr": "\n\nIMPORTANT : Vous DEVEZ répondre en français. Rédigez toute votre analyse et vos conclusions en français.",
    "es": "\n\nIMPORTANTE: DEBES responder en español. Escribe todo tu análisis y conclusiones en español.",
    "it": "\n\nIMPORTANTE: DEVI rispondere in italiano. Scrivi tutta la tua analisi e le tue conclusioni in italiano.",
    "pt": "\n\nIMPORTANTE: Você DEVE responder em português. Escreva toda a sua análise e conclusões em português.",
    "ru": "\n\nВАЖНО: Вы ДОЛЖНЫ отвечать на русском языке. Пишите весь анализ и выводы на русском языке.",
    "zh": "\n\n重要提示：你必须用中文回复。请用中文撰写所有分析和结论。",
    "ja": "\n\n重要：必ず日本語で回答してください。すべての分析と結論を日本語で記述してください。",
    "ko": "\n\n중요: 반드시 한국어로 응답해야 합니다. 모든 분석과 결론을 한국어로 작성하십시오.",
    "sv": "\n\nVIKTIGT: Du MÅSTE svara på svenska. Skriv hela din analys och dina slutsatser på svenska.",
    "el": "\n\nΣΗΜΑΝΤΙΚΟ: Πρέπει να απαντήσετε στα ελληνικά. Γράψτε όλη την ανάλυση και τα συμπεράσματά σας στα ελληνικά.",
    "ar": "\n\nمهم: يجب أن ترد باللغة العربية. اكتب كل تحليلك واستنتاجاتك باللغة العربية.",
    "he": "\n\nחשוב: עליך להגיב בעברית. כתוב את כל הניתוח והמסקנות שלך בעברית.",
}


def _append_language_instruction(prompt: str, language: str) -> str:
    """Append a language instruction to a system prompt.

    Ensures the LLM responds in the debate language even when the persona
    template is written in a different language (e.g. English persona with
    German debate language).

    Falls back to English instruction if language is not supported.
    """
    instruction = _LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["en"])
    return prompt + instruction


# Search instruction templates for all supported locales
_SEARCH_INSTRUCTIONS = {
    "en": {
        "required": (
            "\n\n## Web Research\n"
            "You have access to current web search results which are provided "
            "in the user message under 'Web Research'. You MUST incorporate and "
            "reference this external information in your analysis. "
            "Cite sources where possible. If search results contradict your analysis, "
            "address the discrepancy explicitly."
        ),
        "optional": (
            "\n\n## Web Search Capability\n"
            "You have access to web search. If you need to verify facts, find current "
            "information, or research specific claims, include [SEARCH: your search query] "
            "in your response. Each [SEARCH: ...] marker will be fulfilled and the results "
            "appended to your output. Use this capability sparingly and only when factual "
            "verification is needed."
        ),
    },
    "de": {
        "required": (
            "\n\n## Web-Recherche\n"
            "Du hast Zugriff auf aktuelle Websuchergebnisse, die in der "
            "Benutzernachricht unter 'Web-Recherche' bereitgestellt werden. "
            "Du MUSST diese externen Informationen in deine Analyse einbeziehen "
            "und darauf verweisen. Zitiere Quellen, wo möglich. Wenn Suchergebnisse "
            "deiner Analyse widersprechen, gehe explizit auf die Diskrepanz ein."
        ),
        "optional": (
            "\n\n## Web-Suche\n"
            "Du hast Zugriff auf Websuche. Wenn du Fakten überprüfen, aktuelle "
            "Informationen finden oder spezifische Aussagen recherchieren musst, "
            "füge [SEARCH: deine Suchanfrage] in deine Antwort ein. Jeder "
            "[SEARCH: ...]-Marker wird ausgeführt und die Ergebnisse deiner "
            "Ausgabe angehängt. Nutze diese Fähigkeit sparsam und nur wenn "
            "faktische Überprüfung sinnvoll ist."
        ),
    },
    "fr": {
        "required": (
            "\n\n## Recherche Web\n"
            "Vous avez accès aux résultats de recherche web actuels fournis "
            "dans le message utilisateur sous 'Recherche Web'. Vous DEVEZ intégrer "
            "et référencer ces informations externes dans votre analyse. "
            "Citez les sources si possible. Si les résultats contredisent votre analyse, "
            "abordez explicitement la divergence."
        ),
        "optional": (
            "\n\n## Capacité de Recherche Web\n"
            "Vous avez accès à la recherche web. Si vous devez vérifier des faits, "
            "trouver des informations actuelles ou rechercher des affirmations spécifiques, "
            "incluez [SEARCH: votre requête] dans votre réponse. Chaque marqueur "
            "[SEARCH: ...] sera exécuté et les résultats ajoutés à votre sortie. "
            "Utilisez cette capacité avec parcimonie et uniquement lorsque la vérification "
            "factuelle est nécessaire."
        ),
    },
    "es": {
        "required": (
            "\n\n## Investigación Web\n"
            "Tienes acceso a resultados de búsqueda web actuales que se proporcionan "
            "en el mensaje del usuario bajo 'Investigación Web'. DEBES incorporar y "
            "referenciar esta información externa en tu análisis. "
            "Cita fuentes donde sea posible. Si los resultados contradicen tu análisis, "
            "aborda la discrepancia explícitamente."
        ),
        "optional": (
            "\n\n## Capacidad de Búsqueda Web\n"
            "Tienes acceso a búsqueda web. Si necesitas verificar hechos, encontrar "
            "información actual o investigar afirmaciones específicas, incluye "
            "[SEARCH: tu consulta] en tu respuesta. Cada marcador [SEARCH: ...] "
            "se cumplirá y los resultados se añadirán a tu salida. Usa esta capacidad "
            "con moderación y solo cuando se necesite verificación factual."
        ),
    },
    "ja": {
        "required": (
            "\n\n## Webリサーチ\n"
            "ユーザーメッセージの「Webリサーチ」セクションで提供されている最新のWeb検索結果にアクセスできます。"
            "この外部情報を分析に組み込み、参照しなければなりません。"
            "可能であれば情報源を引用してください。検索結果があなたの分析と矛盾する場合は、"
            "その不一致に明示的に対処してください。"
        ),
        "optional": (
            "\n\n## Web検索機能\n"
            "Web検索にアクセスできます。事実の確認、最新情報の検索、"
            "特定の主張の調査が必要な場合は、回答に[SEARCH: 検索クエリ]を含めてください。"
            "各[SEARCH: ...]マーカーが実行され、結果が出力に追加されます。"
            "この機能は控えめに使用し、事実確認が必要な場合にのみ使用してください。"
        ),
    },
}


def _append_search_instruction(prompt: str, search_mode: str, language: str = "de") -> str:
    """Append web search instructions to a system prompt based on the search mode."""
    if search_mode == "off":
        return prompt

    lang_instructions = _SEARCH_INSTRUCTIONS.get(language, _SEARCH_INSTRUCTIONS["en"])
    instruction = lang_instructions.get(search_mode)
    if not instruction:
        return prompt

    return prompt + instruction


def _is_module_id(value: str) -> bool:
    """Return True if *value* looks like a UUID module ID."""
    try:
        import uuid

        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


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

    # 2. Try module-based agent core (if persona_id is a UUID module ID)
    if prompt is None:
        persona_id = persona_ids.get(role)
        if persona_id and _is_module_id(persona_id):
            try:
                from backend.services.composer_service import ComposerService, Composition

                composition = Composition(agent_core_id=persona_id)
                composed = ComposerService().compose(composition)
                if composed.strip():
                    logger.debug("Using ComposerService for %s (module=%s)", role, persona_id)
                    prompt = composed
                    prompt = _append_language_instruction(prompt, language)
            except Exception as exc:
                logger.warning("ComposerService failed for %s (module=%s): %s", role, persona_id, exc)

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

    # 5. Append search instructions based on mode
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
    """Evaluate consensus using LLM-based analysis of agent outputs.

    The LLM evaluates the content of all agent outputs in the current round
    and produces a consensus score between 0.0 and 1.0, along with a
    natural-language justification.

    Falls back to a weighted heuristic if the LLM call fails.

    If any LLM failures occurred in this round, consensus is capped at 0
    to prevent false consensus claims.
    """
    current_round = state["current_round"]
    max_rounds = state["max_rounds"]
    threshold = state["threshold"]
    session_id = state.get("session_id", "")
    anomalies = state.get("anomalies", [])
    enable_extra_rounds = state.get("enable_extra_rounds", False)
    project_id = state.get("project_id")

    agent_outputs = state.get("agent_outputs", [])

    # Check if any LLM failures occurred in this round
    has_failures = any("LLM call failed" in a for a in anomalies)

    if has_failures:
        consensus = 0.0
        logger.warning(
            "Round %d: LLM failures detected (%d anomalies), consensus capped at 0",
            current_round,
            len(anomalies),
        )
    elif agent_outputs:
        consensus = await _evaluate_consensus_with_llm(
            agent_outputs=agent_outputs,
            current_round=current_round,
            max_rounds=max_rounds,
            threshold=threshold,
            session_id=session_id,
            project_id=project_id,
        )
    else:
        consensus = 0.0

    round_data: RoundDataState = {
        "round": current_round,
        "consensus": round(consensus, 3),
        "agent_outputs": list(agent_outputs),
    }

    total_tokens = sum(ao.get("tokens_used", 0) for ao in agent_outputs)
    await publish_async(
        session_id,
        "round_update",
        {
            "type": "round_update",
            "round": current_round,
            "consensus": round(consensus, 3),
            "threshold": threshold,
            "agent_count": len(agent_outputs),
            "total_tokens": total_tokens,
        },
    )

    next_round = current_round + 1
    extension_granted = None

    needs_extension = enable_extra_rounds and consensus < threshold and next_round <= max_rounds + 2

    return {
        "rounds": [round_data],
        "final_consensus": round(consensus, 3),
        "current_agent_index": 0,
        "current_round": next_round,
        "extension_granted": extension_granted,
        "needs_extension": needs_extension,
    }


# ---------------------------------------------------------------------------
# LLM-based Consensus: Helpers
# ---------------------------------------------------------------------------

_CONSENSUS_SYSTEM_PROMPT = (
    "You are an expert debate moderator. Evaluate the level of consensus "
    "among participants based on their latest responses. Return a single "
    "valid JSON object with keys: consensus_score (0.0-1.0), reasoning, "
    "areas_of_agreement (list), remaining_disagreements (list)."
)


def _build_consensus_prompt(agent_outputs, round_num, max_rounds):
    """Build consensus prompt internally."""
    parts = [
        f"Round {round_num} of {max_rounds}. Agent responses in this round:",
        "",
    ]
    for output in agent_outputs:
        role = output.get("role", "agent")
        text = output.get("content", "").strip()[:2000]
        parts.append("### " + role.capitalize())
        parts.append(text)
        parts.append("")
    parts.append(
        "Evaluate consensus: are agents converging on shared conclusions? Consider overlap in positions and acknowledgment of each other's points."
    )
    return "\n".join(parts)


async def _evaluate_consensus_with_llm(
    agent_outputs,
    current_round,
    max_rounds,
    threshold,
    session_id,
    project_id=None,
):
    """Evaluate consensus with llm the instance."""
    from backend.services.llm_service import LLMService
    from backend.services.profile_service import ProfileService

    prompt_text = _build_consensus_prompt(agent_outputs, current_round, max_rounds)
    try:
        ps = ProfileService()
        service_id = _select_consensus_llm(ps)
        svc = LLMService(profile_id=service_id, profile_service=ps)
        result = await svc.generate(
            prompt=prompt_text,
            system_prompt=_CONSENSUS_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=512,
        )
        score = _parse_consensus_score(result.content.strip())
        if score is not None:
            logger.info(
                "Round %d: LLM consensus=%.3f (model=%s)",
                current_round,
                score,
                service_id,
            )
            return _apply_consensus_floor(score, agent_outputs, threshold)
    except Exception as exc:
        logger.warning(
            "LLM consensus failed (round %d): %s - using heuristic",
            current_round,
            exc,
        )
    return _heuristic_consensus(agent_outputs, current_round, max_rounds, threshold)


def _select_consensus_llm(profile_service):
    """Select consensus llm the instance."""
    try:
        pref = profile_service.get_llm_profile(settings.service_llm_profile_id)
        if pref and is_service_llm_eligible(pref)[0]:
            return settings.service_llm_profile_id
    except Exception as exc:
        logger.debug("Primary service LLM '%s' not eligible: %s", settings.service_llm_profile_id, exc)
    try:
        eligible = [p for p in profile_service.list_llm_profiles() if is_service_llm_eligible(p)[0]]
        if eligible:
            eligible.sort(key=lambda p_: (0 if p_.provider.value == "openrouter" else 1, -(p_.context_window or 0)))
            return eligible[0].id
    except Exception as exc:
        logger.debug("Could not list eligible LLM profiles: %s", exc)
    return settings.service_llm_profile_id


def _parse_consensus_score(text):
    """Parse consensus score the instance."""
    import json
    import re as _re

    m = _re.search(r"\{[^{}]*\}", text, _re.DOTALL)
    if m:
        try:
            data = json.loads(m.group())
            s = data.get("consensus_score")
            if isinstance(s, (int, float)) and 0.0 <= s <= 1.0:
                return float(s)
        except (json.JSONDecodeError, TypeError):
            pass
    m = _re.search(r"consensus.score[\s:=]+([\d.]+)", text, _re.IGNORECASE)
    if m:
        try:
            v = float(m.group(1))
            if 0.0 <= v <= 1.0:
                return v
        except ValueError:
            pass
    m = _re.search(r"\b(0\.\d+|1\.0)\b", text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _apply_consensus_floor(score, agent_outputs, threshold):
    """Apply consensus floor the instance."""
    avg_len = sum(len(o.get("content", "").strip()) for o in agent_outputs) / max(len(agent_outputs), 1)
    if avg_len < 50:
        score = min(score, 0.3)
    if threshold <= score < threshold + 0.05:
        score = threshold - 0.01
    return max(0.0, min(1.0, score))


def _heuristic_consensus(agent_outputs, current_round, max_rounds, threshold):
    """Heuristic consensus the instance."""
    import re as _re

    progression = min(current_round / max_rounds, 1.0)
    if agent_outputs:
        avg_len = sum(len(o.get("content", "").strip()) for o in agent_outputs) / len(agent_outputs)
        length_score = min(avg_len / 300.0, 1.0)
    else:
        length_score = 0.0
    if len(agent_outputs) >= 2:
        wsets = [_re.findall(r"\w{4,}", o.get("content", "").lower()) for o in agent_outputs]
        wsets = [set(w) for w in wsets]
        overlaps = []
        for i in range(len(wsets)):
            for j in range(i + 1, len(wsets)):
                inter = len(wsets[i] & wsets[j])
                uni = len(wsets[i] | wsets[j])
                if uni > 0:
                    overlaps.append(inter / uni)
        overlap_score = sum(overlaps) / len(overlaps) if overlaps else 0.0
    else:
        overlap_score = 0.0
    c = (0.40 * progression) + (0.30 * length_score) + (0.30 * overlap_score)
    return round(min(threshold, c * threshold * 1.2), 3)


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
# Conditional edge functions# ---------------------------------------------------------------------------
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

#: Legacy agent order — used as fallback for OOB routing when state
#: does not provide an explicit agent_profile list.
_LEGACY_AGENT_ORDER = ["strategist", "critic", "optimizer", "moderator"]


def _get_agent_order(state: dict) -> list[str]:
    """Get the current agent execution order from state, or fall back to legacy order."""
    agent_profile = state.get("agent_profile", [])
    if agent_profile:
        return [a.get("role", "") if isinstance(a, dict) else a for a in agent_profile]
    return _LEGACY_AGENT_ORDER


def _is_oob_relevant(oob: dict, role: str, current_round: int, state: dict | None = None) -> bool:
    """Check if an OOB input is relevant for the given agent role and round."""
    target = oob.get("target", {})
    target_type = target.get("type", "")

    if target_type == "specific_agent":
        return target.get("agent_role") == role and (target.get("round") is None or target.get("round") == current_round)

    if target_type == "next_agent":
        agent_order = _get_agent_order(state) if state else _LEGACY_AGENT_ORDER
        prev_role = target.get("current_agent_role", "")
        idx = agent_order.index(prev_role) if prev_role in agent_order else -1
        next_role = agent_order[idx + 1] if 0 <= idx < len(agent_order) - 1 else ""
        if not next_role:
            # If prev_role is unknown (e.g. "input") or is the last agent,
            # default to the first agent in the order so the OOB doesn't get lost
            next_role = agent_order[0]
        return role == next_role

    if target_type == "all_future":
        from_round = target.get("from_round", 0)
        return current_round >= from_round

    if target_type == "current_active":
        return True

    return False
