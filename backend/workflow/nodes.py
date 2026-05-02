"""Node functions for LangGraph debate workflow.

Sprint 3: Real LLM calls via litellm with profile-based configuration.
Falls back to dummy output if litellm is not available or LLM call fails.
"""

from __future__ import annotations

import logging
from typing import Optional

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

    # Profile configuration from state
    llm_profile_id = state.get("llm_profile_id", "openrouter-claude")
    prompt_variant = state.get("prompt_variant", "default")
    persona_ids = state.get("agent_persona_ids", {})

    # --- Resolve system prompt ---
    system_prompt = _resolve_system_prompt(role, prompt_variant, persona_ids, state)

    # --- Build user prompt ---
    user_prompt = _build_user_prompt(state, role)

    # --- LLM call with graceful fallback ---
    try:
        llm_service = LLMService(
            profile_id=llm_profile_id,
            profile_service=_get_profile_service(),
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
        logger.warning("LLM call failed for agent %s: %s — using dummy output", role, exc)
        content = (
            f"[{role}] Round {state['current_round']}: "
            f"Analysis of '{state['context'][:50]}...'"
        )
        tokens = len(content.split())

    output: AgentOutputState = {
        "role": role,
        "content": content,
        "tokens_used": tokens,
    }

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
) -> str:
    """Resolve the system prompt for an agent role.

    Priority: persona system_prompt → prompt service template → generic default.
    """
    # 1. Try persona-specific system prompt
    persona_id = persona_ids.get(role)
    if persona_id:
        persona = _get_profile_service().get_agent_persona(persona_id)
        if persona:
            return persona.system_prompt

    # 2. Try prompt service template
    try:
        return _get_prompt_service().render(
            variant=prompt_variant,
            role=role,
            variables={"context": state["context"]},
        )
    except FileNotFoundError:
        logger.warning("No prompt found for %s/%s, using generic default", prompt_variant, role)

    # 3. Generic fallback
    return f"You are a {role} agent analyzing a legal case. Provide your expert analysis."


def _build_user_prompt(state: DebateState, role: str) -> str:
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
    parts.append("Please provide your analysis based on the case and previous discussion.")

    return "\n\n".join(parts)


def check_consensus_node(state: DebateState) -> dict:
    """Evaluate consensus (linear progression toward threshold).

    TODO: Replace with LLM-based consensus evaluation in a future sprint.
    """
    current_round = state["current_round"]
    max_rounds = state["max_rounds"]
    threshold = state["threshold"]

    # Linear consensus progression
    consensus = min(threshold, current_round / max_rounds * threshold * 1.2)

    round_data: RoundDataState = {
        "round": current_round,
        "consensus": round(consensus, 3),
        "agent_outputs": [],  # already in state.agent_outputs via accumulator
    }

    return {
        "rounds": [round_data],
        "final_consensus": round(consensus, 3),
        "current_agent_index": 0,
        "current_round": current_round + 1,
    }


def complete_node(state: DebateState) -> dict:
    """Finalize the debate."""
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
