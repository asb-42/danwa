"""HITL-aware LangGraph node implementations.

These nodes wrap the existing debate workflow nodes with HITL capabilities:
- Pause checking before each agent
- Inject consumption (merging user context into agent prompts)
- Agent query detection after agent output
- Interrupt creation when agents need clarification

The HITL nodes are designed to be inserted into the existing graph without
modifying the original node functions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from backend.api.events import publish_async
from backend.workflow.hitl.agent_query import analyze_for_query
from backend.workflow.hitl.api import (
    consume_inject,
    get_active_interrupt,
    get_pending_injects,
    is_paused,
    register_agent_query,
)
from backend.workflow.state import DebateState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HITL check node — runs before each agent
# ---------------------------------------------------------------------------


async def hitl_check_node(state: DebateState) -> dict:
    """Pre-agent HITL check: handle pause state and pending injects.

    This node runs before each agent and:
    1. Checks if the debate is paused (waits if so)
    2. Consumes pending user injections
    3. Updates the interaction log in state

    Returns state updates (no blocking — pause is handled via polling).
    """
    session_id = state.get("session_id", "")
    debate_id = state.get("session_id", "")  # session_id == debate_id
    hitl_enabled = state.get("hitl_enabled", False)

    if not hitl_enabled:
        return {}

    # --- Check pause state ---
    if is_paused(debate_id):
        await publish_async(
            session_id,
            "hitl_paused",
            {
                "type": "hitl_paused",
                "message": "Workflow paused, waiting for resume...",
                "round": state.get("current_round", 0),
                "agent_index": state.get("current_agent_index", 0),
            },
        )

        # Poll until resumed (with timeout)
        max_wait = 600  # 10 minutes max pause
        waited = 0
        poll_interval = 2  # seconds

        while is_paused(debate_id) and waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

        if is_paused(debate_id):
            logger.warning("Debate %s pause timeout after %ds", debate_id, max_wait)
            await publish_async(
                session_id,
                "hitl_pause_timeout",
                {"type": "hitl_pause_timeout", "waited_seconds": waited},
            )
        else:
            await publish_async(
                session_id,
                "hitl_resumed",
                {"type": "hitl_resumed", "message": "Workflow resumed"},
            )

    # --- Consume pending injects ---
    pending = get_pending_injects(debate_id)
    if pending:
        interactions = []
        for inject in pending:
            interactions.append(
                {
                    "interaction_id": inject["interaction_id"],
                    "type": "inject",
                    "direction": "user_to_agent",
                    "source": "user",
                    "target": inject.get("target", "all_future"),
                    "content": inject["content"],
                    "round": state.get("current_round", 0),
                    "agent_index": state.get("current_agent_index", 0),
                    "timestamp": datetime.now(UTC).isoformat(),
                    "status": "consumed",
                    "metadata": inject.get("metadata", {}),
                }
            )
            consume_inject(debate_id, inject["interaction_id"])

        logger.info(
            "Consumed %d pending injects for debate %s",
            len(pending),
            debate_id,
        )

        # Publish SSE event so the frontend knows injects were consumed
        await publish_async(
            session_id,
            "hitl_inject_consumed",
            {
                "type": "hitl_inject_consumed",
                "count": len(pending),
                "interaction_ids": [i["interaction_id"] for i in pending],
                "round": state.get("current_round", 0),
                "agent_index": state.get("current_agent_index", 0),
            },
        )

        return {"interactions": interactions}

    return {}


# ---------------------------------------------------------------------------
# HITL agent query check — runs after each agent
# ---------------------------------------------------------------------------


async def hitl_agent_query_node(state: DebateState) -> dict:
    """Post-agent HITL check: analyze agent output for query potential.

    If the agent's output indicates a need for clarification, this node:
    1. Creates an interrupt (agent query to user)
    2. Publishes SSE event for the frontend
    3. Waits for the user's response
    4. Returns the response as additional context

    If no query is needed, returns empty dict (workflow continues).
    """
    hitl_enabled = state.get("hitl_enabled", False)
    hitl_mode = state.get("hitl_mode", "off")

    if not hitl_enabled or hitl_mode not in ("full", "query_only"):
        return {}

    debate_id = state.get("session_id", "")
    session_id = state.get("session_id", "")
    current_round = state.get("current_round", 0)
    max_interrupts = state.get("max_interrupts_per_round", 3)
    round_interrupt_count = state.get("round_interrupt_count", 0)
    auto_query_threshold = state.get("auto_query_threshold", 0.4)

    # Check interrupt limit
    if round_interrupt_count >= max_interrupts:
        logger.debug(
            "HITL: Max interrupts per round reached (%d/%d) for debate %s",
            round_interrupt_count,
            max_interrupts,
            debate_id,
        )
        return {}

    # Get the latest agent output
    agent_outputs = state.get("agent_outputs", [])
    if not agent_outputs:
        return {}

    latest_output = agent_outputs[-1]
    agent_role = latest_output.get("role", "unknown")
    agent_content = latest_output.get("content", "")
    agent_index = state.get("current_agent_index", 1) - 1  # Already incremented

    # Get previous outputs for loop detection
    previous_outputs = [ao["content"] for ao in agent_outputs[:-1] if ao.get("role") == agent_role]

    # Analyze for query potential
    analysis = analyze_for_query(
        agent_output=agent_content,
        agent_role=agent_role,
        current_round=current_round,
        max_rounds=state.get("max_rounds", 3),
        auto_query_threshold=auto_query_threshold,
        previous_outputs=previous_outputs,
    )

    if not analysis.should_query:
        return {}

    # --- Create interrupt ---
    # Build context snippet from current draft
    current_draft = state.get("current_draft", "")
    context_snippet = current_draft[-500:] if len(current_draft) > 500 else current_draft

    interrupt_id = register_agent_query(
        debate_id,
        {
            "agent_role": agent_role,
            "agent_index": agent_index,
            "round": current_round,
            "question": analysis.suggested_question,
            "context": context_snippet,
        },
    )

    # Publish SSE event
    await publish_async(
        session_id,
        "hitl_query",
        {
            "type": "hitl_query",
            "interrupt_id": interrupt_id,
            "agent_role": agent_role,
            "question": analysis.suggested_question,
            "context": context_snippet,
            "confidence": analysis.confidence,
            "reason": analysis.reason,
            "round": current_round,
        },
    )

    # --- Wait for user response ---
    timeout = state.get("interrupt_timeout_seconds", 300)
    waited = 0
    poll_interval = 2  # seconds

    logger.info(
        "HITL: Agent %s waiting for user response (interrupt=%s, timeout=%ds)",
        agent_role,
        interrupt_id,
        timeout,
    )

    while waited < timeout:
        await asyncio.sleep(poll_interval)
        waited += poll_interval

        # Check if interrupt was resolved
        interrupt = get_active_interrupt(debate_id)
        if interrupt is None:
            # Interrupt was resolved (user responded)
            break

        # Check if interrupt timed out or was cancelled
        if interrupt.get("status") in ("timeout", "cancelled"):
            break

    # Check if we got a response
    # The interrupt is removed from _active_interrupts when resolved
    # We need to check the interaction log for the response
    from backend.workflow.hitl.api import _interaction_log

    response_content = None
    for interaction in _interaction_log.get(debate_id, []):
        if interaction.get("type") == "response" and interaction.get("metadata", {}).get("interrupt_id") == interrupt_id:
            response_content = interaction["content"]
            break

    if response_content:
        # Inject the user's response as additional context
        interaction_record = {
            "interaction_id": str(uuid.uuid4()),
            "type": "response",
            "direction": "user_to_agent",
            "source": "user",
            "target": agent_role,
            "content": response_content,
            "round": current_round,
            "agent_index": agent_index,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "consumed",
            "metadata": {"interrupt_id": interrupt_id},
        }

        logger.info(
            "HITL: User response received for agent %s (round %d), length=%d",
            agent_role,
            current_round,
            len(response_content),
        )

        return {
            "interactions": [interaction_record],
            "round_interrupt_count": round_interrupt_count + 1,
        }
    else:
        # Timeout or no response
        logger.info(
            "HITL: Agent %s query timed out after %ds (interrupt=%s)",
            agent_role,
            timeout,
            interrupt_id,
        )

        await publish_async(
            session_id,
            "hitl_timeout",
            {
                "type": "hitl_timeout",
                "interrupt_id": interrupt_id,
                "agent_role": agent_role,
                "waited_seconds": waited,
            },
        )

        return {
            "round_interrupt_count": round_interrupt_count + 1,
        }


# ---------------------------------------------------------------------------
# HITL inject context builder
# ---------------------------------------------------------------------------


def build_inject_context(state: DebateState, agent_role: str) -> str:
    """Build context string from consumed injects for a specific agent.

    This is called by run_agent_node to merge user injections into the
    agent's prompt.  It reads from ``state["interactions"]`` which is
    populated by ``hitl_check_node`` *before* the agent runs.

    Note: ``hitl_check_node`` already consumes pending injects (sets
    status to "consumed") and stores them in the state's ``interactions``
    accumulator.  We must NOT call ``get_pending_injects()`` here because
    those injects are no longer pending at this point.

    Args:
        state: Current debate state.
        agent_role: The agent about to run.

    Returns:
        Formatted context string to append to the agent's prompt.
    """
    current_round = state.get("current_round", 0)

    # Read from state["interactions"] — populated by hitl_check_node
    interactions = state.get("interactions", [])
    inject_interactions = [i for i in interactions if i.get("type") == "inject" and i.get("status") == "consumed"]

    if not inject_interactions:
        return ""

    # Filter injects relevant to this agent
    relevant = []
    for inject in inject_interactions:
        target = inject.get("target", "all_future")
        metadata = inject.get("metadata", {})
        target_agent = metadata.get("target_agent")
        target_round = metadata.get("target_round")

        # Check agent targeting
        if target_agent and target_agent != agent_role and target != "all_future":
            continue

        # Check round targeting
        if target_round is not None and target_round != current_round:
            continue

        relevant.append(inject)

    if not relevant:
        return ""

    # Build context block
    context = "\n\n--- USER CONTEXT INJECTION ---\n"
    for inject in relevant:
        priority = inject.get("metadata", {}).get("priority", "normal")
        prefix = f"[{priority.upper()}] " if priority != "normal" else ""
        context += f"{prefix}{inject['content']}\n"
    context += "--- END USER CONTEXT ---\n"

    return context


# ---------------------------------------------------------------------------
# HITL round reset
# ---------------------------------------------------------------------------


async def extension_request_node(state: DebateState) -> dict:
    """Extension request node: moderator decides on extra rounds.

    After check_consensus, if consensus is NOT reached AND extra rounds
    are enabled, this node creates a query to the user asking whether
    they want to continue debating.

    Waits for the user's response and evaluates it to set
    ``extension_granted`` in the state so the routing decision can
    decide whether to continue or finish the debate.

    Returns state update with extension_granted decision.
    """
    enable_extra = state.get("enable_extra_rounds", False)
    consensus = state.get("final_consensus", 0.0)
    threshold = state.get("threshold", 0.8)
    current_round = state.get("current_round", 0)
    max_rounds = state.get("max_rounds", 3)
    session_id = state.get("session_id", "")
    # NOTE: session_id == debate_id in this codebase
    debate_id = session_id
    language = state.get("language", "de")
    round_int_count = state.get("round_interrupt_count", 0)

    # Only trigger if extra rounds enabled, consensus not reached, and
    # we're within the extended round budget (max + 2)
    if not enable_extra or consensus >= threshold or current_round > max_rounds + 2:
        return {}

    # Create an interrupt asking for extension decision
    from backend.workflow.hitl.api import register_agent_query

    question_de = (
        f"Die Debatte hat nach {current_round} Runden noch keinen Konsens "
        f"(aktuell: {consensus:.1%}, Schwellenwert: {threshold:.0%}). "
        f"Sollen weitere Runden debattiert werden?"
    )
    question_en = (
        f"The debate has not reached consensus after {current_round} rounds "
        f"(current: {consensus:.1%}, threshold: {threshold:.0%}). "
        f"Should additional rounds be debated?"
    )

    interrupt_id = register_agent_query(
        debate_id,
        {
            "agent_role": "moderator",
            "agent_index": -1,
            "round": current_round,
            "question": question_en if language == "en" else question_de,
            "context": f"Debate extension request. Consensus={consensus:.3f}, threshold={threshold}, round {current_round}/{max_rounds}.",
        },
    )

    # Publish SSE event for the extension request
    await publish_async(
        session_id,
        "extension_request",
        {
            "type": "extension_request",
            "debate_id": debate_id,
            "current_consensus": consensus,
            "threshold": threshold,
            "current_round": current_round,
            "max_rounds": max_rounds,
            "interrupt_id": interrupt_id,
        },
    )

    # --- Wait for user response ---
    #
    # Sprint 38 (2/3) — replaced the 2-second ``asyncio.sleep``
    # polling with ``wait_for_extension_signal``.  The
    # ``post_extension_decision`` HITL endpoint (which resolves
    # the interrupt and writes ``extension_granted`` to the
    # debate) fires this signal — so the node unblocks within
    # milliseconds of the user responding.  The 2-second timeout
    # remains as a safety net so the loop can re-check the
    # interrupt status even if the signal mechanism is bypassed
    # (e.g. the response arrived through a code path that
    # doesn't fire the signal).
    timeout = state.get("interrupt_timeout_seconds", 300)
    waited = 0
    poll_interval = 2  # seconds

    logger.info(
        "HITL: Extension request waiting for user response (interrupt=%s, timeout=%ds)",
        interrupt_id,
        timeout,
    )

    from backend.state.workflow_state import get_workflow_state

    state_backend = get_workflow_state()

    while waited < timeout:
        # Wait for the extension signal (or 2 s cap).  The signal
        # is fired by ``post_extension_decision`` after the
        # interrupt is resolved, so a real user response wakes
        # us immediately.  If the signal mechanism is bypassed,
        # the 2 s cap still lets us re-check the interrupt
        # status periodically.
        await state_backend.wait_for_extension_signal(
            session_id,
            timeout=min(poll_interval, max(0.1, timeout - waited)),
        )
        waited += poll_interval

        # Check if interrupt was resolved
        interrupt = get_active_interrupt(debate_id)
        if interrupt is None:
            # Interrupt was resolved (user responded)
            break

        # Check if interrupt timed out or was cancelled
        if interrupt.get("status") in ("timeout", "cancelled"):
            break

    # --- Evaluate user response ---
    # Check the interaction log for a matching response
    from backend.workflow.hitl.api import _interaction_log

    response_content = None
    for interaction in _interaction_log.get(debate_id, []):
        if interaction.get("type") == "response" and interaction.get("metadata", {}).get("interrupt_id") == interrupt_id:
            response_content = interaction["content"]
            break

    if response_content:
        # Determine whether the user granted or denied the extension
        response_lower = response_content.lower().strip()
        # Common "denied" patterns across English and German
        denied_keywords = [
            "denied",
            "verweigert",
            "no ",
            "nein",
            "not ",
            "don't",
            "dont",
            "kein",
            "keine",
            "nö",
            "nope",
            "negative",
            "do not",
            "do not wish",
            "would not like",
            "möchte nicht",
            "möchten nicht",
            "sollen nicht",
        ]
        extension_granted = not any(kw in response_lower for kw in denied_keywords)

        interaction_record = {
            "interaction_id": str(uuid.uuid4()),
            "type": "response",
            "direction": "user_to_agent",
            "source": "user",
            "target": "moderator",
            "content": response_content,
            "round": current_round,
            "agent_index": -1,
            "timestamp": datetime.now(UTC).isoformat(),
            "status": "consumed",
            "metadata": {"interrupt_id": interrupt_id},
        }

        logger.info(
            "HITL: Extension %s for debate %s (response=%s)",
            "granted" if extension_granted else "denied",
            debate_id,
            response_content[:50],
        )

        return {
            "interactions": [interaction_record],
            "extension_granted": extension_granted,
            "round_interrupt_count": round_int_count + 1,
        }
    else:
        # Timeout or no response — deny extension
        logger.info(
            "HITL: Extension request timed out after %ds (interrupt=%s)",
            timeout,
            interrupt_id,
        )

        await publish_async(
            session_id,
            "hitl_timeout",
            {
                "type": "hitl_timeout",
                "interrupt_id": interrupt_id,
                "context": "extension_request",
                "waited_seconds": waited,
            },
        )

        return {
            "extension_granted": False,
            "round_interrupt_count": round_int_count + 1,
        }


def reset_round_interrupt_count(state: DebateState) -> dict:
    """Reset the interrupt counter at the start of a new round.

    Called by check_consensus_node when advancing to the next round.
    """
    return {"round_interrupt_count": 0}
