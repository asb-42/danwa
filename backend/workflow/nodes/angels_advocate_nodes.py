"""Angel's Advocate node for Transactional Drafting workflow.

The Angel's Advocate identifies elements in the current draft that must be
preserved, even if everything else is discarded.  This provides a stability
anchor for the Builder, preventing total overwrites and ensuring institutional
knowledge survives iterative revision.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.models.transactional import AngelsAdvocateOutput
from backend.services.llm_service import LLMService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.node_functions import _get_profile_service
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
    """Extract CriticItems from state or node_outputs."""
    items = state.get("critic_items", [])
    if items:
        return items

    for no in reversed(state.get("node_outputs", [])):
        if no.get("node_type") == "wf-critic":
            raw = no.get("content", "")
            if not raw:
                continue
            # Strip markdown fences
            m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw.strip())
            if m:
                raw = m.group(1).strip()
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                continue
    return []


def angels_advocate_node_factory(
    node_id: str,
    resolved_config: dict,
) -> Callable[[WorkflowState], dict]:
    """Create an Angel's Advocate node function.

    The Angel's Advocate reads the current draft and the Critic's items,
    then identifies elements that must be preserved regardless of how much
    the Builder revises.  This output is injected into the Builder's prompt
    as a constraint.

    Args:
        node_id: The workflow node ID.
        resolved_config: Dict with keys ``llm_profile_id``, ``role``, etc.

    Returns:
        An async callable that takes ``WorkflowState`` and returns a partial
        state update dict.
    """
    llm_profile_id = resolved_config.get("llm_profile_id", "")
    role = resolved_config.get("role", "angels-advocate")

    async def _angels_advocate_node(state: WorkflowState) -> dict:
        """Angels advocate node the instance."""
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-angels-advocate",
                "role": role,
                "round": current_round,
            },
        )

        # --- Read inputs ---
        zero_draft = _extract_zero_draft(state)
        critic_items = _extract_critic_items(state)

        if not zero_draft and not critic_items:
            logger.warning("Angel's Advocate %s: no draft or critique to analyze", node_id)
            return {
                "node_outputs": [
                    {
                        "node_id": node_id,
                        "node_type": "wf-angels-advocate",
                        "role": role,
                        "content": "No draft or critique available to analyze.",
                        "tokens_used": 0,
                        "duration_ms": 0,
                        "status": "completed",
                    }
                ],
                "preserved_elements": [],
            }

        # --- Build prompt ---
        schema = AngelsAdvocateOutput.model_json_schema()
        dump = {
            "type": "object",
            "properties": schema["properties"],
            "required": schema.get("required", []),
        }
        if "$defs" in schema:
            dump["$defs"] = schema["$defs"]

        system_prompt = (
            "Du bist der Angel's Advocate. Deine Aufgabe ist es, die Stärken und "
            "erhaltenswerten Elemente des aktuellen Entwurfs zu identifizieren.\n"
            "\n"
            "KONTEXT:\n"
            "Der Critic hat Schwachstellen identifiziert. Der Builder wird diese "
            "beheben. Bevor das passiert, musst DU sicherstellen, dass dabei keine "
            "wertvollen Elemente verloren gehen.\n"
            "\n"
            "ABSOLUTE REGELN:\n"
            "1. Du MUSST mindestens 3 Elemente finden, die beibehalten werden müssen.\n"
            "2. Für jedes Element: Gib den genauen Text und die Position im Dokument an.\n"
            "3. Begründe, warum jedes Element kritisch ist (rechtlich, strategisch, logisch).\n"
            "4. Wenn der Entwurf so schwach ist, dass kaum etwas erhalten werden kann, "
            "dann identifiziere die wenigen Rohdiamanten und warne eindringlich.\n"
            "\n"
            "FORMAT: Valides JSON. Kein Markdown außerhalb des JSON.\n"
            "\n"
            "## Output Format\n"
            "Respond with a JSON object matching this schema:\n" + json.dumps(dump, indent=2, ensure_ascii=False)
        )

        user_prompt = f"Original draft:\n{zero_draft}\n\n"
        if critic_items:
            user_prompt += f"Critique items (the Builder will try to fix these):\n{json.dumps(critic_items, indent=2, default=str)}\n\n"
        user_prompt += "Identify the elements that MUST be preserved, even if the Builder rewrites everything else."

        language = state.get("language", "de")
        user_prompt += " Please respond in English." if language == "en" else " Bitte antworte auf Deutsch."

        # --- LLM call with JSON retry ---
        content = ""
        tokens_used = 0
        angels_output = None
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
                    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", clean)
                    if m:
                        clean = m.group(1).strip()
                    parsed = json.loads(clean)
                    if isinstance(parsed, list):
                        parsed = {"preserved_elements": parsed, "overall_stability_score": 0.5}
                    angels_output = AngelsAdvocateOutput.model_validate(parsed)
                    content = raw
                    break
                except Exception as e:
                    try:
                        from json_repair import repair_json

                        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
                        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", clean)
                        if m:
                            clean = m.group(1).strip()
                        repaired = repair_json(clean)
                        parsed = json.loads(repaired)
                        if isinstance(parsed, list):
                            parsed = {"preserved_elements": parsed, "overall_stability_score": 0.5}
                        angels_output = AngelsAdvocateOutput.model_validate(parsed)
                        content = raw
                        logger.info(
                            "Angel's Advocate %s: json-repair fixed JSON on attempt %d",
                            node_id,
                            attempt + 1,
                        )
                        break
                    except Exception:
                        pass
                    logger.warning(
                        "Angel's Advocate JSON parse attempt %d/%d failed: %s",
                        attempt + 1,
                        _MAX_JSON_RETRIES,
                        e,
                    )
                    if attempt < _MAX_JSON_RETRIES - 1:
                        user_prompt += "\n\nYour previous response was not valid JSON. You MUST respond with valid JSON matching the required schema."
                    else:
                        content = raw
                        status = "failed"
        except Exception as exc:
            logger.error("Angel's Advocate %s LLM call failed: %s", node_id, exc)
            content = f"[Angel's Advocate] LLM call failed ({exc})"
            status = "failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # --- Extract preserved elements for downstream (Builder) ---
        preserved = []
        stability_score = 0.0
        if angels_output:
            preserved = [el.model_dump() for el in angels_output.preserved_elements]
            stability_score = angels_output.overall_stability_score

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-angels-advocate",
            "role": role,
            "content": content,
            "tokens_used": tokens_used,
            "duration_ms": elapsed_ms,
            "status": status,
            "round": current_round,
        }

        await publish_async(
            session_id,
            "node.complete",
            {
                "node_id": node_id,
                "node_type": "wf-angels-advocate",
                "role": role,
                "round": current_round,
                "content": content,
                "tokens_used": tokens_used,
                "duration_ms": elapsed_ms,
                "status": status,
            },
        )

        # Audit
        try:
            al = get_audit_logger()
            wf_id = state.get("workflow_id", "")
            wf_ver = state.get("workflow_version", 1)
            if status == "failed":
                al.log_node_failed(
                    session_id=session_id,
                    workflow_id=wf_id,
                    workflow_version=wf_ver,
                    node_id=node_id,
                    actor=role,
                    error=content,
                )
            else:
                al.log_node_execution(
                    session_id=session_id,
                    workflow_id=wf_id,
                    workflow_version=wf_ver,
                    node_id=node_id,
                    actor=role,
                    input_data={"zero_draft": zero_draft[:500], "critic_items_count": len(critic_items)},
                    output_data={"content": content, "stability_score": stability_score, "preserved_count": len(preserved)},
                    llm_profile_id=llm_profile_id,
                    latency_ms=duration_ms,
                    prompt_tokens=0,
                    completion_tokens=tokens_used,
                )
        except Exception:
            logger.debug("Audit logging failed for angels-advocate %s", node_id, exc_info=True)

        return {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "preserved_elements": preserved,
            "stability_score": stability_score,
        }

    return _angels_advocate_node
