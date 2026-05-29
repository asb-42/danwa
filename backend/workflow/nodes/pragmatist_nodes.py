"""Pragmatist node for Transactional Drafting workflow.

The Pragmatist evaluates BuildResponses against real-world constraints
(feasibility, process risk, cost/time) and produces a structured
PragmatistOutput with reality_score and blocking concerns.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.models.transactional import PragmatistOutput
from backend.services.llm_service import LLMService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.node_functions import _get_profile_service, _resolve_system_prompt
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)

_MAX_JSON_RETRIES = 3


def pragmatist_node_factory(
    node_id: str,
    resolved_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create a Pragmatist node function.

    Args:
        node_id: The workflow node ID.
        resolved_config: Dict with keys ``llm_profile_id``, ``role``, etc.

    Returns:
        An async callable that takes ``WorkflowState`` and returns a partial
        state update dict.
    """
    llm_profile_id = resolved_config.get("llm_profile_id", "")
    role = resolved_config.get("role", "pragmatist")

    async def _pragmatist_node(state: WorkflowState) -> dict:
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        await publish_async(session_id, "node.start", {
            "node_id": node_id, "node_type": "wf-pragmatist",
            "role": role, "round": current_round,
        })

        # --- Read inputs ---
        build_responses = state.get("build_responses", [])
        if not build_responses:
            logger.warning("Pragmatist %s: no build_responses to evaluate", node_id)
            return {"node_outputs": [{
                "node_id": node_id, "node_type": "wf-pragmatist", "role": role,
                "content": "No build responses to evaluate.", "tokens_used": 0,
                "duration_ms": 0, "status": "completed",
            }]}

        system_prompt = _resolve_system_prompt(resolved_config, state)
        user_prompt = f"""Build responses to evaluate:\n{json.dumps(build_responses, indent=2, default=str)}"""

        language = state.get("language", "de")
        user_prompt += "Please respond in English." if language == "en" else "Bitte antworte auf Deutsch."

        content = ""
        tokens_used = 0
        duration_ms = 0
        pragmatist_output = None
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
                    pragmatist_output = PragmatistOutput.model_validate(parsed)
                    content = raw
                    break
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "Pragmatist JSON parse attempt %d/%d failed: %s",
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
            logger.error("Pragmatist %s LLM call failed: %s", node_id, exc)
            content = f"[Pragmatist] LLM call failed ({exc})"
            status = "failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        output: WorkflowNodeOutput = {
            "node_id": node_id, "node_type": "wf-pragmatist", "role": role,
            "content": content, "tokens_used": tokens_used,
            "duration_ms": elapsed_ms, "status": status, "round": current_round,
        }

        await publish_async(session_id, "node.complete", {
            "node_id": node_id, "node_type": "wf-pragmatist", "role": role,
            "round": current_round, "content": content,
            "tokens_used": tokens_used, "duration_ms": elapsed_ms, "status": status,
        })

        reality_score = pragmatist_output.reality_score if pragmatist_output else 0.0
        blocking = pragmatist_output.blocking_concerns if pragmatist_output else []

        # Audit
        try:
            al = get_audit_logger()
            if status == "failed":
                al.log_node_failed(session_id, state.get("workflow_id", ""),
                                   state.get("workflow_version", 1), node_id, role, content)
            else:
                al.log_node_execution(session_id, state.get("workflow_id", ""),
                                      state.get("workflow_version", 1), node_id, role,
                                      {"build_responses": build_responses},
                                      {"content": content, "reality_score": reality_score},
                                      llm_profile_id, duration_ms, 0, tokens_used)
                al.log_workflow_event(
                    session_id, state.get("workflow_id", ""),
                    "pragmatist_evaluation",
                    {"reality_score": reality_score, "blocking_concerns": blocking},
                )
        except Exception:
            logger.debug("Audit logging failed for pragmatist %s", node_id, exc_info=True)

        return {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "pragmatist_output": pragmatist_output.model_dump() if pragmatist_output else None,
        }

    return _pragmatist_node
