"""LangGraph node for A2A agent participation in debates.

This node is inserted into the agent pipeline when an A2A agent
is configured for the debate.  It calls the external agent via
the A2A protocol and returns the result as an agent output.
"""

from __future__ import annotations

import logging

from backend.a2a.client import A2AClient
from backend.a2a.config import get_a2a_config
from backend.api.events import publish_async

logger = logging.getLogger(__name__)


async def run_a2a_agent_node(state: dict) -> dict:
    """Run an external A2A agent as a debate participant.

    Reads A2A configuration from the debate state (``a2a_config``)
    or falls back to the global ``config/a2a.json``.
    """
    # Check for per-debate A2A config first, then global config
    a2a_config = state.get("a2a_config")
    if not a2a_config:
        a2a_config = get_a2a_config()

    if not a2a_config or not a2a_config.get("enabled"):
        # A2A not configured — skip
        return {"current_agent_index": state["current_agent_index"] + 1}

    # Determine agent URL and role
    agent_url = a2a_config.get("agent_url", "")
    if not agent_url:
        # Try to get from external_agents list
        external_agents = a2a_config.get("external_agents", [])
        if external_agents:
            agent = external_agents[0]
            agent_url = agent.get("url", "")
        else:
            return {"current_agent_index": state["current_agent_index"] + 1}

    role = a2a_config.get("role", "a2a_agent")
    session_id = state.get("session_id", "")
    round_num = state.get("current_round", 1)

    # Publish: A2A agent starting
    await publish_async(
        session_id,
        "agent_preparing",
        {
            "type": "agent_preparing",
            "round": round_num,
            "role": role,
            "agent_index": state["current_agent_index"],
            "agent_total": len(state.get("agent_profile", [])) + 1,
            "phase": "a2a_invocation",
        },
    )

    try:
        client = A2AClient(agent_url)

        # Discover agent capabilities
        card = await client.discover()
        logger.info(
            "A2A agent discovered: %s — %s",
            card.get("name", "unknown"),
            card.get("description", "")[:100],
        )

        # Invoke agent
        response = await client.invoke_agent(
            context=state.get("context", ""),
            role=role,
            round_num=round_num,
            previous_outputs=state.get("agent_outputs", []),
        )

        # Publish: A2A agent completed
        await publish_async(
            session_id,
            "agent_output",
            {
                "round": round_num,
                "role": role,
                "content": response,
                "tokens_used": len(response.split()),
                "tokens_in": 0,
                "tokens_out": len(response.split()),
                "duration_ms": 0,
                "model": f"a2a:{agent_url}",
            },
        )

        # Return as agent output
        return {
            "agent_outputs": [
                {
                    "role": role,
                    "content": response,
                    "tokens_used": len(response.split()),
                }
            ],
            "current_agent_index": state["current_agent_index"] + 1,
            "current_draft": state.get("current_draft", "") + "\n" + response,
        }

    except Exception as exc:
        logger.error("A2A agent invocation failed: %s", exc, exc_info=True)

        # Publish error event
        await publish_async(
            session_id,
            "agent_output",
            {
                "round": round_num,
                "role": role,
                "content": f"[A2A Error] {exc}",
                "tokens_used": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "duration_ms": 0,
                "model": f"a2a:{agent_url}",
            },
        )

        return {
            "agent_outputs": [
                {
                    "role": role,
                    "content": f"[A2A Agent Error] {exc}",
                    "tokens_used": 0,
                }
            ],
            "current_agent_index": state["current_agent_index"] + 1,
            "anomalies": [f"A2A agent {role} failed: {exc}"],
        }
