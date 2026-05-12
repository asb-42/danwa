"""LangGraph node for A2A agent participation in debates (Phase 8).

Refactored to use A2AAdapter with fallback support and structured error handling.
Publishes node.error SSE events on failure and logs to audit trail.
"""

from __future__ import annotations

import logging

from backend.a2a.adapter import A2AAdapter
from backend.a2a.config import get_a2a_config
from backend.a2a.exceptions import A2AError
from backend.api.events import publish_async
from backend.core.config import settings

logger = logging.getLogger(__name__)


async def run_a2a_agent_node(state: dict) -> dict:
    """Run an external A2A agent as a debate participant.

    Uses A2AAdapter for transparent integration with the same interface
    as LLMService. Supports fallback to local LLM profile on A2A failure.
    Logs errors to audit trail (Phase 7).
    """
    # Check for per-debate A2A config first, then global config
    a2a_config = state.get("a2a_config")
    if not a2a_config:
        a2a_config = get_a2a_config()

    if not a2a_config or not a2a_config.get("enabled"):
        return {"current_agent_index": state["current_agent_index"] + 1}

    # Determine agent URL and role
    agent_url = a2a_config.get("agent_url", "")
    if not agent_url:
        external_agents = a2a_config.get("external_agents", [])
        if external_agents:
            agent = external_agents[0]
            agent_url = agent.get("url", "")
        else:
            return {"current_agent_index": state["current_agent_index"] + 1}

    role = a2a_config.get("role", "a2a_agent")
    session_id = state.get("session_id", "")
    round_num = state.get("current_round", 1)
    fallback_id = a2a_config.get("fallback_llm_profile_id")

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
        adapter = A2AAdapter(
            a2a_endpoint=agent_url,
            timeout=a2a_config.get("timeout", 120),
            allow_private_ips=settings.a2a_allow_private_ips,
        )

        # Build messages from state
        messages = []
        context = state.get("context", "")
        if context:
            messages.append(
                {
                    "role": "user",
                    "content": f"## Context\n{context}",
                }
            )

        previous_outputs = state.get("agent_outputs", [])
        if previous_outputs:
            prev_text = "\n\n".join(f"### {o.get('role', 'Agent')}\n{o.get('content', '')}" for o in previous_outputs)
            messages.append(
                {
                    "role": "user",
                    "content": f"## Previous Contributions\n{prev_text}",
                }
            )

        result = await adapter.invoke(
            messages=messages,
            config={
                "context": context,
                "role": role,
                "round_num": round_num,
                "previous_outputs": previous_outputs,
            },
        )

        content = result.content
        tokens_used = result.tokens_out

    except A2AError as exc:
        logger.error("A2A agent failed: %s", exc)

        # Try fallback
        if fallback_id:
            try:
                from backend.services.llm_service import LLMService

                fallback_service = LLMService(profile_id=fallback_id)
                fallback_result = await fallback_service.generate(
                    prompt=f"[A2A Fallback] Context: {context}\nRole: {role}",
                )
                content = fallback_result.content
                tokens_used = fallback_result.tokens_out
                logger.info("A2A fallback to %s succeeded", fallback_id)
            except Exception as fallback_exc:
                logger.error("A2A fallback also failed: %s", fallback_exc)
                await publish_async(
                    session_id,
                    "node.error",
                    {
                        "type": "node.error",
                        "session_id": session_id,
                        "role": role,
                        "error": f"A2A failed: {exc}. Fallback also failed: {fallback_exc}",
                        "round": round_num,
                    },
                )
                content = f"[{role}] A2A agent and fallback both failed"
                tokens_used = 0
        else:
            await publish_async(
                session_id,
                "node.error",
                {
                    "type": "node.error",
                    "session_id": session_id,
                    "role": role,
                    "error": str(exc),
                    "round": round_num,
                },
            )
            content = f"[{role}] A2A agent failed: {exc}"
            tokens_used = 0

        # Audit log the error
        try:
            from backend.workflow.audit_logger import get_audit_logger

            get_audit_logger().log_node_failed(
                session_id=session_id,
                workflow_id=state.get("workflow_id", ""),
                workflow_version=state.get("workflow_version", 1),
                node_id=f"a2a_{role}",
                actor=role,
                error=str(exc),
            )
        except Exception:
            logger.debug("Audit logging failed for A2A error", exc_info=True)

    # Publish: A2A agent completed
    await publish_async(
        session_id,
        "agent_output",
        {
            "round": round_num,
            "role": role,
            "content": content,
            "tokens_used": tokens_used,
            "tokens_in": 0,
            "tokens_out": tokens_used,
            "duration_ms": 0,
            "model": f"a2a:{agent_url}",
        },
    )

    return {
        "agent_outputs": [{"role": role, "content": content, "tokens_used": tokens_used}],
        "current_agent_index": state["current_agent_index"] + 1,
    }
