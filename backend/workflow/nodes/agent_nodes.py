"""Agent node factory for LangGraph workflow execution.

Creates agent execution nodes that resolve their ``AgentBlueprint`` at
runtime and call the LLM via ``LLMService``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.services.llm_service import LLMService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.interjection import interjection_service
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)


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
    from backend.workflow.node_functions import (
        _get_profile_service,
        _perform_optional_search,
        _perform_required_search,
        _resolve_system_prompt,
    )

    role = resolved_config.get("role", node_type.replace("wf-", ""))
    llm_profile_id = resolved_config.get("llm_profile_id", "")
    resolved_config.get("blueprint_name", role)
    model_params = resolved_config.get("model_params", {}) or {}

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

        # Use node config template as user prompt (with context substitution)
        node_config = resolved_config.get("node_config", {})
        task_template = node_config.get("template", "")
        if task_template:
            task_prompt = task_template.replace("{{context}}", context)
            user_prompt = f"{task_prompt}\n\nCase: {context}"
        else:
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
            # DIAGNOSTIC: Log interjection consumption result
            logger.info(
                "DIAG agent %s (node %s): service_injs=%d, state_queue=%d, total=%d",
                role,
                node_id,
                len(service_injs),
                len(state.get("interjection_queue", [])),
                len(interjection_queue),
            )
        except Exception:
            logger.error("DIAG Failed to consume interjection service for session=%s node=%s", session_id, node_id, exc_info=True)

        if interjection_queue:
            inj_text = "\n\n--- ADDITIONAL CONTEXT (User) ---\n"
            inj_text += "\n".join(f"- {inj['content']}" for inj in interjection_queue)
            user_prompt += inj_text
            logger.info(
                "DIAG agent %s (node %s, round %d): injected %d interjections into prompt",
                role,
                node_id,
                current_round,
                len(interjection_queue),
            )

            # Mark HITL interactions as consumed so the UI reflects the status change
            for inj in interjection_queue:
                meta = inj.get("metadata", {})
                if meta.get("debate_id") and meta.get("interaction_id"):
                    try:
                        from backend.workflow.hitl.api import consume_inject

                        consume_inject(meta["debate_id"], meta["interaction_id"])
                    except Exception:
                        logger.debug(
                            "Failed to mark HITL interaction %s as consumed",
                            meta.get("interaction_id"),
                            exc_info=True,
                        )

            # Publish SSE event so the frontend shows interjection consumption feedback
            await publish_async(
                session_id,
                "interjection.consumed",
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "role": role,
                    "round": current_round,
                    "interjection_count": len(interjection_queue),
                    "contents": [inj["content"][:200] for inj in interjection_queue],
                },
            )

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
                temperature=model_params.get("temperature"),
                extra_kwargs=model_params,
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

        # Keep current_draft bounded — only retain the latest round's content
        # to prevent unbounded context growth across feedback loops
        existing_draft = state.get("current_draft", "")
        # Append this agent's output, but cap total length to ~8000 chars (last ~2 rounds)
        new_draft = existing_draft + f"\n\n[{role.upper()} Round {current_round}]\n{content}"
        if len(new_draft) > 8000:
            new_draft = new_draft[-8000:]

        return {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "current_draft": new_draft,
        }

    return _agent_node
