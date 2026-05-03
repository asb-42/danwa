"""Node functions for LangGraph debate workflow.

Sprint 3: Real LLM calls via litellm with profile-based configuration.
Falls back to dummy output if litellm is not available or LLM call fails.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.api.events import publish_async
from backend.services.llm_service import LLMService
from backend.services.profile_service import ProfileService
from backend.services.prompt_service import PromptService
from backend.workflow.state import (
    AgentOutputState,
    DebateState,
    RoundDataState,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level service singletons (lazy-initialized)
# ---------------------------------------------------------------------------

_profile_service: Optional[ProfileService] = None
_prompt_service: Optional[PromptService] = None


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

    # Profile configuration from state
    llm_profile_id = state.get("llm_profile_id", "openrouter-claude")
    prompt_variant = state.get("prompt_variant", "default")
    persona_ids = state.get("agent_persona_ids", {})
    language = state.get("language", "de")

    # --- Resolve system prompt ---
    system_prompt = _resolve_system_prompt(role, prompt_variant, persona_ids, state, language)

    # --- Build user prompt ---
    user_prompt = _build_user_prompt(state, role, language)

    # --- Publish: agent started ---
    await publish_async(session_id, "agent_started", {
        "round": state["current_round"],
        "role": role,
        "profile": llm_profile_id,
    })

    # --- LLM call with graceful fallback ---
    try:
        llm_service = LLMService(
            profile_id=llm_profile_id,
            profile_service=_get_profile_service(),
        )
        logger.info(
            "Agent %s (round %d): calling LLM profile '%s' (model=%s, api_base=%s)",
            role, state["current_round"], llm_profile_id,
            llm_service.profile.model if llm_service.profile else "N/A",
            llm_service.profile.api_base if llm_service.profile else "N/A",
        )
        content = await llm_service.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=agent.get("temperature", 0.7),
        )
        tokens = len(content.split())  # rough estimate
        logger.info(
            "Agent %s (round %d): LLM response (%d tokens)",
            role, state["current_round"], tokens,
        )
    except Exception as exc:
        logger.error(
            "LLM call FAILED for agent %s (round %d, profile=%s): %s",
            role, state["current_round"], llm_profile_id, exc,
            exc_info=True,
        )
        content = (
            f"[{role}] Round {state['current_round']}: "
            f"LLM call failed ({type(exc).__name__}: {exc}). "
            f"Profile: {llm_profile_id}"
        )
        tokens = len(content.split())

    output: AgentOutputState = {
        "role": role,
        "content": content,
        "tokens_used": tokens,
    }

    # --- Publish: agent completed ---
    await publish_async(session_id, "agent_output", {
        "round": state["current_round"],
        "role": role,
        "content": content,
        "tokens_used": tokens,
    })

    return {
        "agent_outputs": [output],
        "current_agent_index": idx + 1,
        "current_draft": state.get("current_draft", "") + "\n" + content,
    }


def _resolve_system_prompt(
    role: str,
    prompt_variant: str,
    persona_ids: dict[str, str],
    state: DebateState,
    language: str = "de",
) -> str:
    """Resolve the system prompt for an agent role.

    Priority: prompt service template (language-aware) → persona system_prompt → generic default.

    The prompt service is tried first because it supports language variants
    (e.g. ``strategist.md`` for German, ``strategist-en.md`` for English).
    Persona system prompts are used as fallback when no template exists.
    """
    # 1. Try prompt service template (language-aware) — highest priority
    try:
        rendered = _get_prompt_service().render(
            variant=prompt_variant,
            role=role,
            variables={"context": state["context"]},
            language=language,
        )
        logger.debug("Using prompt template for %s/%s (lang=%s)", prompt_variant, role, language)
        return rendered
    except FileNotFoundError:
        logger.debug("No prompt template for %s/%s (lang=%s), trying persona", prompt_variant, role, language)

    # 2. Try persona-specific system prompt (always in persona's language)
    persona_id = persona_ids.get(role)
    if persona_id:
        persona = _get_profile_service().get_agent_persona(persona_id)
        if persona:
            logger.debug("Using persona system_prompt for %s (persona=%s)", role, persona_id)
            return persona.system_prompt

    # 3. Generic fallback (language-aware)
    logger.warning("No prompt found for %s/%s (lang=%s), using generic default", prompt_variant, role, language)
    if language == "en":
        return f"You are a {role} agent analyzing a legal case. Provide your expert analysis."
    return f"Du bist ein {role}-Agent, der einen Rechtsfall analysiert. Gib deine Expertenanalyse ab."


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
    else:
        parts.append("Bitte gib deine Analyse basierend auf dem Fall und der bisherigen Diskussion.")

    return "\n\n".join(parts)


async def check_consensus_node(state: DebateState) -> dict:
    """Evaluate consensus (linear progression toward threshold).

    TODO: Replace with LLM-based consensus evaluation in a future sprint.
    """
    current_round = state["current_round"]
    max_rounds = state["max_rounds"]
    threshold = state["threshold"]
    session_id = state.get("session_id", "")

    # Linear consensus progression
    consensus = min(threshold, current_round / max_rounds * threshold * 1.2)

    # Include agent outputs from this round in the round data
    round_data: RoundDataState = {
        "round": current_round,
        "consensus": round(consensus, 3),
        "agent_outputs": list(state.get("agent_outputs", [])),
    }

    # --- Publish: round completed ---
    await publish_async(session_id, "round_update", {
        "round": current_round,
        "consensus": round(consensus, 3),
        "agent_count": len(state.get("agent_outputs", [])),
    })

    return {
        "rounds": [round_data],
        "final_consensus": round(consensus, 3),
        "current_agent_index": 0,
        "current_round": current_round + 1,
    }


async def complete_node(state: DebateState) -> dict:
    """Finalize the debate."""
    session_id = state.get("session_id", "")

    # --- Publish: debate completed ---
    await publish_async(session_id, "status_change", {
        "status": "completed",
        "final_consensus": state.get("final_consensus", 0.0),
        "total_rounds": state.get("current_round", 1) - 1,
    })

    return {
        "output": state.get("current_draft", "No output generated."),
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
    """
    if state["final_consensus"] >= state["threshold"]:
        return "complete"
    if state["current_round"] > state["max_rounds"]:
        return "complete"
    return "next_round"
