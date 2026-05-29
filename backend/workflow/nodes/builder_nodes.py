"""Builder node for Transactional Drafting workflow.

The Builder receives CriticItems and the original zero-draft, then generates
structured BuildResponses via LLM. Supports feedback loops with Pragmatist
blocking concerns injected into subsequent iterations.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.models.transactional import BuilderOutput, CriticItem
from backend.services.llm_service import LLMService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.node_functions import _get_profile_service, _resolve_system_prompt
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)

_MAX_JSON_RETRIES = 3


def _extract_zero_draft(state: WorkflowState) -> str:
    """Extract zero draft from state, falling back to parsing from node_outputs."""
    zd = state.get("zero_draft")
    if zd:
        return zd
    for no in reversed(state.get("node_outputs", [])):
        if no.get("node_type") == "wf-strategist":
            return no.get("content", "")
    return state.get("context", "")


def _extract_critic_items(state: WorkflowState) -> list[dict]:
    """Extract CriticItems from state, falling back to parsing from node_outputs.

    If ``critic_items`` accumulator is populated, returns it directly.
    Otherwise scans ``node_outputs`` for the most recent ``wf-critic`` entry
    and attempts to parse its content as a JSON array of ``CriticItem`` objects.
    """
    items = state.get("critic_items", [])
    if items:
        return items

    for no in reversed(state.get("node_outputs", [])):
        if no.get("node_type") == "wf-critic":
            raw = no.get("content", "")
            if not raw:
                continue
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [CriticItem.model_validate(c).model_dump() for c in parsed]
            except (json.JSONDecodeError, ValueError):
                continue
    return []


def builder_node_factory(
    node_id: str,
    resolved_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create a Builder node function.

    Args:
        node_id: The workflow node ID.
        resolved_config: Dict with keys ``llm_profile_id``, ``role``, etc.

    Returns:
        An async callable that takes ``WorkflowState`` and returns a partial
        state update dict.
    """
    llm_profile_id = resolved_config.get("llm_profile_id", "")
    role = resolved_config.get("role", "builder")

    async def _builder_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        await publish_async(session_id, "node.start", {
            "node_id": node_id, "node_type": "wf-builder",
            "role": role, "round": current_round,
        })

        # --- Read inputs ---
        critic_items = _extract_critic_items(state)
        zero_draft = _extract_zero_draft(state)
        pragmatist_output = state.get("pragmatist_output")
        draft_version = state.get("draft_version", 1)

        if not critic_items:
            logger.warning("Builder %s: no critic_items to respond to", node_id)
            return {"node_outputs": [{
                "node_id": node_id, "node_type": "wf-builder", "role": role,
                "content": "No critique to address.", "tokens_used": 0,
                "duration_ms": 0, "status": "completed",
            }]}

        # --- Build prompt ---
        system_prompt = _resolve_system_prompt(resolved_config, state)

        user_prompt = f"""Original draft:\n{zero_draft}\n\nCritique items:\n{json.dumps(critic_items, indent=2, default=str)}"""

        if pragmatist_output:
            concerns = pragmatist_output.get("blocking_concerns", [])
            if concerns:
                user_prompt += "\n\nThe Pragmatist raised these concerns from the previous iteration:\n"
                user_prompt += "\n".join(f"- {c}" for c in concerns)

        user_prompt += f"\n\nThis is iteration {draft_version}. "

        language = state.get("language", "de")
        user_prompt += "Please respond in English." if language == "en" else "Bitte antworte auf Deutsch."

        # --- LLM call with JSON retry ---
        content = ""
        tokens_used = 0
        builder_output = None
        status = "completed"

        try:
            llm_service = LLMService(
                profile_id=llm_profile_id,
                profile_service=_get_profile_service(),
            )

            for attempt in range(_MAX_JSON_RETRIES):
                gen_result = await llm_service.generate(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                )
                raw = gen_result.content
                tokens_used = gen_result.tokens_out if gen_result.tokens_out > 0 else len(raw.split())
                duration_ms = gen_result.duration_ms

                try:
                    parsed = json.loads(raw)
                    builder_output = BuilderOutput.model_validate(parsed)
                    content = raw
                    break
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Builder JSON parse attempt %d/%d failed: %s",
                        attempt + 1, _MAX_JSON_RETRIES, e,
                    )
                    if attempt < _MAX_JSON_RETRIES - 1:
                        user_prompt += (
                            "\n\nYour previous response was not valid JSON. "
                            "You MUST respond with valid JSON matching the required schema."
                        )
                    else:
                        content = raw
                        status = "failed"
        except Exception as exc:
            logger.error("Builder %s LLM call failed: %s", node_id, exc)
            content = f"[Builder] LLM call failed ({exc})"
            status = "failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # --- Compute constructivity score ---
        n_critic = len(critic_items)
        if builder_output:
            n_build = len(builder_output.build_responses)
            constructivity = round(n_build / n_critic, 4) if n_critic > 0 else 1.0
            builder_output.constructivity_score = constructivity
        else:
            constructivity = 0.0

        output: WorkflowNodeOutput = {
            "node_id": node_id, "node_type": "wf-builder", "role": role,
            "content": content, "tokens_used": tokens_used,
            "duration_ms": elapsed_ms, "status": status, "round": current_round,
        }

        await publish_async(session_id, "node.complete", {
            "node_id": node_id, "node_type": "wf-builder", "role": role,
            "round": current_round, "content": content,
            "tokens_used": tokens_used, "duration_ms": elapsed_ms, "status": status,
        })

        # Audit
        try:
            al = get_audit_logger()
            if status == "failed":
                al.log_node_failed(session_id, state.get("workflow_id", ""),
                                   state.get("workflow_version", 1), node_id, role, content)
            else:
                al.log_node_execution(session_id, state.get("workflow_id", ""),
                                      state.get("workflow_version", 1), node_id, role,
                                      {"critic_items": critic_items, "zero_draft": zero_draft},
                                      {"content": content, "constructivity_score": constructivity},
                                      llm_profile_id, duration_ms, 0, tokens_used)
                al.log_workflow_event(
                    session_id, state.get("workflow_id", ""),
                    "builder_iteration",
                    {"draft_version": draft_version, "constructivity_score": constructivity},
                )
        except Exception:
            logger.debug("Audit logging failed for builder %s", node_id, exc_info=True)

        state_update: dict = {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "build_responses": [b.model_dump() for b in builder_output.build_responses] if builder_output else [],
            "constructivity_score": constructivity,
            "current_draft": content,
        }
        if builder_output and builder_output.global_revision:
            state_update["current_draft"] = builder_output.global_revision

        return state_update

    return _builder_node
