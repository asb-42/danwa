"""Node functions for LangGraph workflow execution.

Each function (or factory) produces a partial state update dict that LangGraph
merges into the shared ``WorkflowState``.  Agent nodes resolve their
``AgentBlueprint`` at runtime and call the LLM via ``LLMService``.

This module serves as the backward-compatible entry point.  The actual node
implementations live in the ``backend.workflow.nodes`` sub-package:

- ``backend.workflow.nodes.agent_nodes``   — agent_node_factory
- ``backend.workflow.nodes.moderator_nodes`` — moderator_node_factory, gate_node_factory, tone_profile_node_factory
- ``backend.workflow.nodes.system_nodes``  — input_node, initialize_wf_node, complete_wf_node, interjection_node

Shared utilities (service singletons, search helpers, prompt resolution)
remain defined here and are imported by the sub-modules.
"""

from __future__ import annotations

import logging

from backend.api.events import publish_async
from backend.services.profile_service import ProfileService
from backend.services.prompt_service import PromptService
from backend.services.web_search import (
    WebSearchTool,
    extract_search_markers,
    extract_search_queries,
    format_search_results,
)
from backend.workflow.workflow_state import WorkflowState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level service singletons (lazy-initialized)
# ---------------------------------------------------------------------------

_profile_service: ProfileService | None = None
_prompt_service: PromptService | None = None


def _get_profile_service() -> ProfileService:
    """Return (or lazily create) profile service."""
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service


def _get_prompt_service() -> PromptService:
    """Return (or lazily create) prompt service."""
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


_search_tool: WebSearchTool | None = None


def _get_search_tool() -> WebSearchTool:
    """Return (or lazily create) search tool."""
    global _search_tool
    if _search_tool is None:
        from backend.core.config import settings

        _search_tool = WebSearchTool(
            url=settings.searxng_url,
            max_results=settings.searxng_max_results,
            region=settings.searxng_region,
        )
    return _search_tool


# ---------------------------------------------------------------------------
# Web search helpers (required / optional modes)
# ---------------------------------------------------------------------------

_SEARCH_INSTRUCTIONS: dict[str, dict[str, str]] = {
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
            "und darauf verweisen. Zitiere Quellen, wo moeglich. Wenn Suchergebnisse "
            "deiner Analyse widersprechen, gehe explizit auf die Diskrepanz ein."
        ),
        "optional": (
            "\n\n## Web-Suche\n"
            "Du hast Zugriff auf Websuche. Wenn du Fakten ueberpruefen, aktuelle "
            "Informationen finden oder spezifische Aussagen recherchieren musst, "
            "fuege [SEARCH: deine Suchanfrage] in deine Antwort ein. Jeder "
            "[SEARCH: ...]-Marker wird ausgefuehrt und die Ergebnisse deiner "
            "Ausgabe angehaengt. Nutze diese Faehigkeit sparsam und nur wenn "
            "faktische Ueberpruefung sinnvoll ist."
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


async def _perform_required_search(
    state: WorkflowState,
    role: str,
    language: str,
    user_prompt: str,
    session_id: str,
) -> str:
    """Required mode: auto-search before LLM call and inject results into prompt."""
    search_tool = _get_search_tool()
    queries = extract_search_queries(state.get("context", ""), role)
    if not queries:
        return user_prompt

    all_results = []
    for query in queries:
        try:
            results = await search_tool.search(query)
            all_results.extend(results)
            await publish_async(
                session_id,
                "web_search",
                {
                    "type": "web_search",
                    "round": state.get("current_round", 1),
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
    state: WorkflowState,
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
                    "round": state.get("current_round", 1),
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


# ---------------------------------------------------------------------------
# Prompt resolution helper
# ---------------------------------------------------------------------------


def _resolve_system_prompt(resolved_config: dict, state: WorkflowState) -> str:
    """Resolve the system prompt for an agent node using the assembly pipeline.

    Prompt Assembly Pipeline (layered approach):
      0. Pre-assembled system_prompt from Bundle (highest priority)
      1. Argumentation Pattern base (philosophical/sachliche Ausrichtung)
      2. Workflow-variant prompt overlay (Formatierungsvorgaben etc.)
      3. Tone Profile injection (Stimmung/Aszendenz) — handled in agent_node_factory
      4. Fallback to default role prompt if nothing else is configured
    """
    # --- Layer 0: Pre-assembled system_prompt from Bundle ---
    bundle_system_prompt = resolved_config.get("system_prompt")
    if bundle_system_prompt and bundle_system_prompt.strip():
        return bundle_system_prompt

    role = resolved_config.get("role", "agent")
    role_type_name = resolved_config.get("role_type_name", "")
    role_type_icon = resolved_config.get("role_type_icon", "\U0001f464")
    argumentation_pattern = resolved_config.get("argumentation_pattern")
    mode = resolved_config.get("mode")
    language = state.get("language", "de")

    # --- Layer 1+2: Use PromptService assemble_prompt ---
    try:
        prompt_service = _get_prompt_service()
        assembled = prompt_service.assemble_prompt(
            role_type_id=role,
            argumentation_pattern=argumentation_pattern,
            workflow_variant="default",
            language=language,
            translate=(language != "en"),
        )
        if assembled.strip():
            prompt = assembled
            # Enhance with Mode info if available
            if mode:
                mode_hints = {
                    "interviewer": "Stelle gezielte Nachfolgefragen und vertiefe die Antworten.",
                    "advocate": "Verteide die Position ueberzeugend und einseitig.",
                    "adversary": "Nimm aktiv die Gegenposition ein und widerlege die Argumente.",
                    "mediator": "Vermittle zwischen den Positionen und suche Gemeinsamkeiten.",
                    "referee": "Bewerte die Fairness und Relevanz der Argumente.",
                    "facilitator": "Foerder den strukturierten Dialog und halte den Prozess auf Kurs.",
                }
                hint = mode_hints.get(mode)
                if hint:
                    if language == "en":
                        prompt = f"{prompt}\n\n[{mode.title()} mode: {hint}]"
                    else:
                        prompt = f"{prompt}\n\n[{mode.title()}-Modus: {hint}]"
            return prompt
    except Exception:
        logger.exception(
            "Failed to assemble prompt for role='%s' pattern='%s' language='%s'",
            role,
            argumentation_pattern,
            language,
        )

    # Fallback: generic system prompt based on role
    role_prompts = {
        "strategist": "You are a strategic analyst. Analyze the case and provide a structured initial assessment.",
        "critic": "You are a critical reviewer. Identify weaknesses, gaps, and potential issues in the analysis.",
        "fact-checker": "You are a fact-checker. Verify factual claims against reliable sources and flag inaccuracies.",
        "optimizer": "You are an optimization expert. Refine and improve the draft by addressing the critiques.",
        "moderator": "You are a debate moderator. Synthesize all contributions and evaluate consensus.",
        "analyst": "You are an analyst. Conduct in-depth analysis of data and identify key patterns.",
        "creative": "You are a creative thinker. Generate unconventional ideas and new perspectives.",
    }
    prompt = role_prompts.get(role, f"You are a {role} participating in a structured debate.")

    # Enhance with RoleType name if available (for custom role types)
    if role_type_name and role_type_name.lower() != role.lower():
        prompt = f"{role_type_icon} You are a {role_type_name} ({role}). " + prompt.split(". ", 1)[-1] if ". " in prompt else prompt

    # Append web search instructions based on search_mode
    search_mode = state.get("search_mode", "off")
    prompt = _append_search_instruction(prompt, search_mode, language)

    return prompt


# ---------------------------------------------------------------------------
# Backward-compatible re-exports from the nodes sub-package
#
# These are loaded lazily via __getattr__ to avoid circular imports
# (the sub-modules import shared utilities from this module).
# ---------------------------------------------------------------------------

_LAZY_IMPORT_MAP: dict[str, tuple[str, str]] = {
    "agent_node_factory": ("backend.workflow.nodes.agent_nodes", "agent_node_factory"),
    "moderator_node_factory": ("backend.workflow.nodes.moderator_nodes", "moderator_node_factory"),
    "gate_node_factory": ("backend.workflow.nodes.moderator_nodes", "gate_node_factory"),
    "tone_profile_node_factory": ("backend.workflow.nodes.moderator_nodes", "tone_profile_node_factory"),
    "input_node": ("backend.workflow.nodes.system_nodes", "input_node"),
    "initialize_wf_node": ("backend.workflow.nodes.system_nodes", "initialize_wf_node"),
    "complete_wf_node": ("backend.workflow.nodes.system_nodes", "complete_wf_node"),
    "interjection_node": ("backend.workflow.nodes.system_nodes", "interjection_node"),
    "builder_node_factory": ("backend.workflow.nodes.builder_nodes", "builder_node_factory"),
    "pragmatist_node_factory": ("backend.workflow.nodes.pragmatist_nodes", "pragmatist_node_factory"),
    "angels_advocate_node_factory": ("backend.workflow.nodes.angels_advocate_nodes", "angels_advocate_node_factory"),
    "route_decision": ("backend.workflow.workflow_routers", "route_decision"),
}


def __getattr__(name: str):
    """Getattr   the instance."""
    if name in _LAZY_IMPORT_MAP:
        import importlib

        module_path, attr_name = _LAZY_IMPORT_MAP[name]
        module = importlib.import_module(module_path)
        return getattr(module, attr_name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
