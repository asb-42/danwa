"""Node functions for LangGraph workflow execution.

Each function (or factory) produces a partial state update dict that LangGraph
merges into the shared ``WorkflowState``.  Agent nodes resolve their
``AgentBlueprint`` at runtime and call the LLM via ``LLMService``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService
from backend.services.prompt_service import PromptService
from backend.services.web_search import (
    WebSearchTool,
    extract_search_markers,
    extract_search_queries,
    format_search_results,
)
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.interjection import interjection_service
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level service singletons (lazy-initialized)
# ---------------------------------------------------------------------------

_profile_service: ProfileService | None = None
_prompt_service: PromptService | None = None


def _get_profile_service() -> ProfileService:
    global _profile_service
    if _profile_service is None:
        _profile_service = ProfileService()
    return _profile_service


def _get_prompt_service() -> PromptService:
    global _prompt_service
    if _prompt_service is None:
        _prompt_service = PromptService()
    return _prompt_service


_search_tool: WebSearchTool | None = None


def _get_search_tool() -> WebSearchTool:
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
# Simple node functions
# ---------------------------------------------------------------------------


async def input_node(state: WorkflowState) -> dict:
    """Input node — sets the context from the workflow input.

    No LLM call.  Simply passes through the user's case text.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-input")

    await publish_async(
        session_id,
        "node.start",
        {
            "node_id": node_id,
            "node_type": "wf-input",
            "round": state.get("current_round", 1),
        },
    )

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-input",
        "role": "input",
        "content": state.get("context", ""),
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(
        session_id,
        "node.complete",
        {
            "node_id": node_id,
            "node_type": "wf-input",
            "role": "input",
            "content": output["content"][:200],
            "tokens_used": 0,
            "duration_ms": 0,
        },
    )

    # --- Audit log ---
    try:
        get_audit_logger().log_node_execution(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            node_id=node_id,
            actor="input",
            input_data={"context": state.get("context", "")},
            output_data=output,
        )
    except Exception:
        logger.debug("Audit logging failed for input_node", exc_info=True)

    return {
        "node_outputs": [output],
        "current_draft": state.get("context", ""),
    }


async def initialize_wf_node(state: WorkflowState) -> dict:
    """Initialize node — resets runtime state for a new workflow execution.

    Sets ``current_round=1``, clears accumulators.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-initialize")

    await publish_async(
        session_id,
        "node.start",
        {
            "node_id": node_id,
            "node_type": "wf-initialize",
            "round": 1,
        },
    )

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-initialize",
        "role": "initialize",
        "content": "Workflow initialized",
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(
        session_id,
        "node.complete",
        {
            "node_id": node_id,
            "node_type": "wf-initialize",
            "role": "initialize",
            "content": "Workflow initialized",
            "tokens_used": 0,
            "duration_ms": 0,
        },
    )

    # --- Audit log ---
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            event_type="workflow_started",
            actor="system",
        )
    except Exception:
        logger.debug("Audit logging failed for initialize_wf_node", exc_info=True)

    return {
        "current_round": 1,
        "current_draft": "",
        "final_consensus": 0.0,
        "output": "",
        "node_outputs": [output],
    }


async def complete_wf_node(state: WorkflowState) -> dict:
    """Complete node — assembles final output and marks workflow as done."""
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-complete")

    final_output = state.get("current_draft", "")

    output: WorkflowNodeOutput = {
        "node_id": node_id,
        "node_type": "wf-complete",
        "role": "complete",
        "content": final_output[:500],
        "tokens_used": 0,
        "duration_ms": 0,
        "status": "completed",
    }

    await publish_async(
        session_id,
        "workflow.complete",
        {
            "session_id": session_id,
            "total_rounds": state.get("current_round", 1),
            "final_consensus": state.get("final_consensus", 0.0),
        },
    )

    # --- Audit log ---
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id=state.get("workflow_id", ""),
            workflow_version=state.get("workflow_version", 1),
            event_type="workflow_completed",
            actor="system",
            metadata={"consensus": state.get("final_consensus", 0.0)},
        )
    except Exception:
        logger.debug("Audit logging failed for complete_wf_node", exc_info=True)

    return {
        "output": final_output,
        "status": "completed",
        "node_outputs": [output],
    }


# ---------------------------------------------------------------------------
# Agent node factory
# ---------------------------------------------------------------------------


def agent_node_factory(
    node_id: str,
    node_type: str,
    resolved_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create an agent node function for a workflow node.

    Args:
        node_id: The workflow node ID (e.g. ``"node_strategist_1"``).
        node_type: The node type (e.g. ``"wf-strategist"``).
        resolved_config: Dict with keys ``blueprint_id``, ``blueprint_name``,
            ``llm_profile_id``, ``llm_model``, ``role_definition_id``,
            ``role``, ``prompt_template_id``.

    Returns:
        An async callable that takes ``WorkflowState`` and returns a partial
        state update dict.
    """
    role = resolved_config.get("role", node_type.replace("wf-", ""))
    llm_profile_id = resolved_config.get("llm_profile_id", "")
    resolved_config.get("blueprint_name", role)

    # Extract tone_profile_source_node_id from resolved config
    tone_profile_source_node_id = resolved_config.get("tone_profile_source_node_id")

    async def _agent_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        # --- Publish: node started ---
        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": node_type,
                "role": role,
                "round": current_round,
            },
        )

        # --- Build system prompt ---
        system_prompt = _resolve_system_prompt(resolved_config, state)

        # --- Inject tone profile if configured ---
        tone_profile_name = None
        if tone_profile_source_node_id:
            tone_profiles = state.get("tone_profiles", {})
            profile_data = tone_profiles.get(tone_profile_source_node_id)
            if profile_data:
                try:
                    from backend.blueprints.models import ToneProfile
                    from backend.services.tone_prompt_injector import inject_tone_profile

                    profile = ToneProfile.model_validate(profile_data)
                    system_prompt = inject_tone_profile(system_prompt, profile)
                    tone_profile_name = profile.name
                    logger.info(
                        "Injected tone profile '%s' into agent %s (node %s)",
                        profile.name,
                        role,
                        node_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to inject tone profile for agent %s (node %s): %s",
                        role,
                        node_id,
                        exc,
                    )

        # --- Build user prompt ---
        context = state.get("context", "")
        current_draft = state.get("current_draft", "")
        language = state.get("language", "de")

        user_prompt = f"Case: {context}"

        # Inject RAG context (document content)
        rag_context = state.get("rag_context", "")
        if rag_context:
            user_prompt += f"\n\n--- DOCUMENT CONTEXT ---\n{rag_context}"

        if current_draft:
            user_prompt += f"\n\nCurrent draft:\n{current_draft}"

        # Inject pending interjections (from both state queue and interjection service)
        interjection_queue = list(state.get("interjection_queue", []))
        try:
            service_injs = await interjection_service.consume(session_id, node_id)
            interjection_queue.extend(service_injs)
        except Exception:
            logger.debug("Failed to consume interjection service for %s", session_id, exc_info=True)

        if interjection_queue:
            inj_text = "\n\n--- ADDITIONAL CONTEXT (User) ---\n"
            inj_text += "\n".join(f"- {inj['content']}" for inj in interjection_queue)
            user_prompt += inj_text

        if language == "en":
            user_prompt += "\n\nPlease respond in English."
        else:
            user_prompt += "\n\nBitte antworte auf Deutsch."

        # Required mode: auto-search before LLM call
        search_mode = state.get("search_mode", "off")
        if search_mode == "required":
            user_prompt = await _perform_required_search(state, role, language, user_prompt, session_id)

        # --- LLM call ---
        content = ""
        tokens_used = 0
        duration_ms = 0
        status = "completed"

        # Publish LLM call started event for live progress feedback
        await publish_async(
            session_id,
            "llm.call_started",
            {
                "node_id": node_id,
                "node_type": node_type,
                "role": role,
                "round": current_round,
                "llm_profile_id": llm_profile_id,
            },
        )

        try:
            llm_service = LLMService(
                profile_id=llm_profile_id,
                profile_service=_get_profile_service(),
            )
            gen_result = await llm_service.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            content = gen_result.content

            # Optional mode: check for [SEARCH: ...] markers after LLM response
            if state.get("search_mode") == "optional":
                content = await _perform_optional_search(content, role, language, session_id, state)
                tokens_used = len(content.split())

            tokens_used = gen_result.tokens_out if gen_result.tokens_out > 0 else len(content.split())
            duration_ms = gen_result.duration_ms

            logger.info(
                "Agent %s (node %s, round %d): LLM response (%d tokens, %dms)",
                role,
                node_id,
                current_round,
                tokens_used,
                duration_ms,
            )

        except Exception as exc:
            logger.error(
                "Agent %s (node %s, round %d): LLM call FAILED: %s",
                role,
                node_id,
                current_round,
                exc,
                exc_info=True,
            )
            content = f"[{role}] Round {current_round}: LLM call failed ({exc})"
            tokens_used = len(content.split())
            status = "failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": node_type,
            "role": role,
            "content": content,
            "tokens_used": tokens_used,
            "duration_ms": elapsed_ms,
            "status": status,
        }

        # --- Publish: node completed ---
        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": node_type,
                "role": role,
                "round": current_round,
                "content": content,
                "tokens_used": tokens_used,
                "duration_ms": elapsed_ms,
                "status": status,
            },
        )

        # --- Audit log ---
        try:
            al = get_audit_logger()
            audit_metadata = {}
            if tone_profile_name:
                audit_metadata["tone_profile_name"] = tone_profile_name

            if status == "failed":
                al.log_node_failed(
                    session_id=session_id,
                    workflow_id=state.get("workflow_id", ""),
                    workflow_version=state.get("workflow_version", 1),
                    node_id=node_id,
                    actor=role,
                    error=content,
                )
            else:
                al.log_node_execution(
                    session_id=session_id,
                    workflow_id=state.get("workflow_id", ""),
                    workflow_version=state.get("workflow_version", 1),
                    node_id=node_id,
                    actor=role,
                    input_data={
                        "system_prompt": system_prompt,
                        "user_prompt": user_prompt,
                        **audit_metadata,
                    },
                    output_data={"content": content, "tokens_used": tokens_used},
                    llm_profile_id=llm_profile_id,
                    latency_ms=duration_ms,
                    prompt_tokens=0,
                    completion_tokens=tokens_used,
                )
        except Exception:
            logger.debug("Audit logging failed for agent_node %s", node_id, exc_info=True)

        # Include round number in node_output for render engine / PDF generation
        output["round"] = current_round

        return {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "current_draft": state.get("current_draft", "") + "\n" + content,
        }

    return _agent_node


def moderator_node_factory(
    node_id: str,
    resolved_config: dict,
    threshold: float = 0.7,
) -> Callable[[WorkflowState], dict]:
    """Create a moderator node that also evaluates consensus.

    Same as ``agent_node_factory`` but additionally computes a consensus
    score, increments ``current_round``, and publishes SSE events.
    """
    base_fn = agent_node_factory(node_id, "wf-moderator", resolved_config)

    async def _moderator_node(state: WorkflowState) -> dict:
        result = await base_fn(state)

        # Simple consensus heuristic: based on draft length stability
        # In a real implementation, this would use LLM-based evaluation
        current_draft = result.get("current_draft", state.get("current_draft", ""))
        draft_length = len(current_draft)
        num_outputs = len(state.get("node_outputs", [])) + len(result.get("node_outputs", []))
        consensus = min(1.0, (num_outputs * 0.15) + (draft_length / 10000))

        current_round = state.get("current_round", 1)
        max_rounds = state.get("max_rounds", 10)
        next_round = current_round + 1

        session_id = state.get("session_id", "")
        await publish_async(
            session_id,
            "consensus.reached",
            {
                "score": round(consensus, 2),
                "threshold": threshold,
                "round": current_round,
            },
        )

        # Publish round update for UI
        total_tokens = sum(no.get("tokens_used", 0) for no in state.get("node_outputs", []) + result.get("node_outputs", []))
        await publish_async(
            session_id,
            "round_update",
            {
                "type": "round_update",
                "round": current_round,
                "consensus": round(consensus, 2),
                "threshold": threshold,
                "agent_count": num_outputs,
                "total_tokens": total_tokens,
            },
        )

        result["final_consensus"] = round(consensus, 2)
        # Increment current_round so the feedback router can cap at max_rounds
        result["current_round"] = next_round

        logger.info(
            "Moderator (node %s, round %d): consensus=%.2f, next_round=%d, max_rounds=%d",
            node_id,
            current_round,
            consensus,
            next_round,
            max_rounds,
        )

        return result

    return _moderator_node


# ---------------------------------------------------------------------------
# Gate node factory
# ---------------------------------------------------------------------------


def gate_node_factory(
    node_id: str,
    condition_expr: str = "",
) -> Callable[[WorkflowState], dict]:
    """Create a gate node that evaluates a condition.

    The gate node itself doesn't route — routing is handled by
    ``workflow_routers.route_conditional()``.  This function just
    publishes SSE events and records the gate evaluation.

    Args:
        node_id: The workflow node ID.
        condition_expr: The condition expression (for logging).
    """

    async def _gate_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-gate",
                "round": current_round,
            },
        )

        # Evaluate condition for logging
        condition_result = False
        try:
            if condition_expr:
                condition_result = bool(
                    eval(condition_expr, {"__builtins__": {}}, dict(state))  # noqa: S307
                )
        except Exception as exc:
            logger.warning("Gate condition '%s' raised: %s", condition_expr, exc)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-gate",
            "role": "gate",
            "content": f"Gate evaluated: {condition_expr} → {condition_result}",
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "completed",
        }

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-gate",
                "role": "gate",
                "content": output["content"],
                "tokens_used": 0,
                "duration_ms": 0,
            },
        )

        # --- Audit log ---
        try:
            get_audit_logger().log_node_execution(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=node_id,
                actor="gate",
                input_data={"condition": condition_expr},
                output_data={"result": condition_result},
            )
        except Exception:
            logger.debug("Audit logging failed for gate_node %s", node_id, exc_info=True)

        return {"node_outputs": [output]}

    return _gate_node


# ---------------------------------------------------------------------------
# Tone profile node
# ---------------------------------------------------------------------------


def tone_profile_node_factory(
    node_id: str,
    node_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create a tone profile node function.

    Loads the ToneProfile (from catalog or inline) and writes it into
    ``state["tone_profiles"][node_id]``.  No LLM call, no output.

    Args:
        node_id: The workflow node ID.
        node_config: The node config dict with keys ``tone_profile_id``
            or ``inline_profile``.
    """
    from backend.blueprints.models import ToneProfile
    from backend.blueprints.repository import BlueprintRepository

    tone_profile_id = node_config.get("tone_profile_id")
    inline_profile_data = node_config.get("inline_profile")

    async def _tone_profile_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-tone-profile",
                "role": "tone-profile",
            },
        )

        profile: ToneProfile | None = None

        if tone_profile_id:
            # Load from catalog
            try:
                repo = BlueprintRepository()
                profile = repo.get_tone_profile(tone_profile_id)
                if profile is None:
                    logger.warning("ToneProfile '%s' not found in catalog", tone_profile_id)
            except Exception as exc:
                logger.error("Failed to load ToneProfile '%s': %s", tone_profile_id, exc)

        elif inline_profile_data:
            # Use inline profile
            try:
                if isinstance(inline_profile_data, dict):
                    profile = ToneProfile.model_validate(inline_profile_data)
                else:
                    profile = inline_profile_data
            except Exception as exc:
                logger.error("Failed to parse inline ToneProfile: %s", exc)

        # Update tone_profiles in state
        tone_profiles = dict(state.get("tone_profiles", {}))
        if profile is not None:
            tone_profiles[node_id] = profile.model_dump()

        output = {
            "node_id": node_id,
            "node_type": "wf-tone-profile",
            "role": "tone-profile",
            "content": f"Tone profile loaded: {profile.name if profile else 'none'}",
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "completed" if profile else "failed",
        }

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-tone-profile",
                "role": "tone-profile",
                "content": output["content"],
                "tokens_used": 0,
                "duration_ms": 0,
            },
        )

        # --- Audit log ---
        try:
            get_audit_logger().log_node_execution(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=node_id,
                actor="tone-profile",
                input_data={"tone_profile_id": tone_profile_id},
                output_data={"profile_name": profile.name if profile else None},
            )
        except Exception:
            logger.debug("Audit logging failed for tone_profile_node %s", node_id, exc_info=True)

        return {
            "tone_profiles": tone_profiles,
            "node_outputs": [output],
        }

    return _tone_profile_node


# ---------------------------------------------------------------------------
# Interjection node
# ---------------------------------------------------------------------------


async def interjection_node(state: WorkflowState) -> dict:
    """Interjection node — consumes queued user input or pauses.

    If there are pending interjections in the queue, consumes them and
    appends to the state.  If the queue is empty, sets ``is_paused=True``
    to signal the execution engine to pause and wait for user input.
    """
    session_id = state.get("session_id", "")
    node_id = state.get("current_node_id", "wf-user-injection")

    await publish_async(
        session_id,
        "node.start",
        {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "round": state.get("current_round", 1),
        },
    )

    queue = state.get("interjection_queue", [])

    if queue:
        # Consume all pending interjections
        consumed_ids = [item.get("id", "") for item in queue]
        combined_content = "\n".join(item.get("content", "") for item in queue)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "role": "user-injection",
            "content": combined_content,
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "completed",
        }

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-user-injection",
                "role": "user-injection",
                "content": combined_content[:500],
                "tokens_used": 0,
                "duration_ms": 0,
            },
        )

        # --- Audit log ---
        try:
            get_audit_logger().log_node_execution(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=node_id,
                actor="user",
                input_data={"interjection_count": len(queue)},
                output_data={"consumed_ids": consumed_ids, "content": combined_content},
            )
        except Exception:
            logger.debug("Audit logging failed for interjection_node", exc_info=True)

        return {
            "interjection_queue": [],  # Clear the queue
            "consumed_interjections": consumed_ids,
            "node_outputs": [output],
            "current_draft": state.get("current_draft", "") + "\n" + combined_content,
        }
    else:
        # No interjections pending — pause execution
        logger.info("Interjection node %s: no pending input, pausing", node_id)

        await publish_async(
            session_id,
            "workflow.paused",
            {
                "session_id": session_id,
                "current_node_id": node_id,
            },
        )

        output_pause: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-user-injection",
            "role": "user-injection",
            "content": "[Paused — waiting for user input]",
            "tokens_used": 0,
            "duration_ms": 0,
            "status": "pending",
        }

        # --- Audit log ---
        try:
            get_audit_logger().log_workflow_event(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                event_type="workflow_paused",
                actor="system",
                metadata={"node_id": node_id, "reason": "no_pending_interjections"},
            )
        except Exception:
            logger.debug("Audit logging failed for interjection_node pause", exc_info=True)

        return {
            "is_paused": True,
            "node_outputs": [output_pause],
        }


# ---------------------------------------------------------------------------
# Helpers
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
    prompt_template_id = resolved_config.get("prompt_template_id")
    role_type_name = resolved_config.get("role_type_name", "")
    role_type_icon = resolved_config.get("role_type_icon", "👤")
    argumentation_pattern = resolved_config.get("argumentation_pattern")
    mode = resolved_config.get("mode")
    language = state.get("language", "de")

    # --- Layer 1+2: Use PromptService assemble_prompt ---
    if argumentation_pattern or prompt_template_id:
        try:
            prompt_service = _get_prompt_service()
            # Determine workflow variant from prompt_template_id if set
            workflow_variant = "default"
            assembled = prompt_service.assemble_prompt(
                role_type_id=role,
                argumentation_pattern=argumentation_pattern,
                workflow_variant=workflow_variant,
                language=language,
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
        except Exception as exc:
            logger.warning("Failed to assemble prompt for role '%s' (pattern=%s): %s", role, argumentation_pattern, exc)

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
