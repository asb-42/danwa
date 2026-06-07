"""Pragmatist node for Transactional Drafting workflow.

The Pragmatist evaluates BuildResponses against real-world constraints
(feasibility, process risk, cost/time) and produces a structured
PragmatistOutput with reality_score and blocking concerns.
"""

from __future__ import annotations

import json
import logging
import re
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
        """Pragmatist node the instance."""
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-pragmatist",
                "role": role,
                "round": current_round,
            },
        )

        # --- Read inputs ---
        build_responses = state.get("build_responses", [])
        if not build_responses:
            logger.warning("Pragmatist %s: no build_responses to evaluate", node_id)
            # Return a default pragmatist_output so the moderator can still
            # make a decision (rather than leaving consensus_result unset).
            default_output = PragmatistOutput(
                evaluations=[],
                reality_score=0.0,
                blocking_concerns=["No build responses were produced by the Builder."],
            )
            return {
                "node_outputs": [
                    {
                        "node_id": node_id,
                        "node_type": "wf-pragmatist",
                        "role": role,
                        "content": "No build responses to evaluate.",
                        "tokens_used": 0,
                        "duration_ms": 0,
                        "status": "completed",
                    }
                ],
                "pragmatist_output": default_output.model_dump(),
                "build_responses": [],
            }

        system_prompt = _resolve_system_prompt(resolved_config, state)

        # Inject PragmatistOutput JSON schema + verdict threshold rules
        schema = PragmatistOutput.model_json_schema()
        dump = {
            "type": "object",
            "properties": schema["properties"],
            "required": schema.get("required", []),
        }
        if "$defs" in schema:
            dump["$defs"] = schema["$defs"]
        system_prompt += (
            "\n\n## Verdict Rules\n"
            "You MUST classify each option using these thresholds:\n"
            "- **accept**: feasibility >= 0.7 — the option works in practice.\n"
            "- **revise**: feasibility 0.4–0.7 — the option has potential but needs changes. "
            "You MUST provide a `revision_note` telling the Builder exactly what to change.\n"
            "- **reject**: feasibility < 0.4 — the option will fail. "
            "You MUST provide a `revision_note` explaining why.\n"
            "\n"
            "## Output Format\n"
            "Respond with a JSON object matching this schema:\n" + json.dumps(dump, indent=2, ensure_ascii=False)
        )

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
                    clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw)
                    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", clean)
                    if m:
                        clean = m.group(1).strip()
                    parsed = json.loads(clean)
                    if isinstance(parsed, list):
                        parsed = {"evaluations": parsed, "reality_score": 0.0, "blocking_concerns": []}
                    pragmatist_output = PragmatistOutput.model_validate(parsed)
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
                            parsed = {"evaluations": parsed, "reality_score": 0.0, "blocking_concerns": []}
                        pragmatist_output = PragmatistOutput.model_validate(parsed)
                        content = raw
                        logger.info("Pragmatist %s: json-repair fixed JSON on attempt %d", node_id, attempt + 1)
                        break
                    except Exception:
                        pass
                    logger.warning(
                        "Pragmatist JSON parse attempt %d/%d failed: %s",
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
            logger.error("Pragmatist %s LLM call failed: %s", node_id, exc)
            content = f"[Pragmatist] LLM call failed ({exc})"
            status = "failed"

        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-pragmatist",
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
                "node_type": "wf-pragmatist",
                "role": role,
                "round": current_round,
                "content": content,
                "tokens_used": tokens_used,
                "duration_ms": elapsed_ms,
                "status": status,
            },
        )

        reality_score = pragmatist_output.reality_score if pragmatist_output else 0.0
        blocking = pragmatist_output.blocking_concerns if pragmatist_output else []

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
                    input_data={"build_responses": build_responses},
                    output_data={"content": content, "reality_score": reality_score},
                    llm_profile_id=llm_profile_id,
                    latency_ms=duration_ms,
                    prompt_tokens=0,
                    completion_tokens=tokens_used,
                )
                # Transactional Drafting: pragmatist_evaluation event
                verdicts_summary = []
                if pragmatist_output and pragmatist_output.evaluations:
                    for ev in pragmatist_output.evaluations:
                        verdicts_summary.append(
                            {
                                "response_to": ev.response_to,
                                "verdict": ev.verdict,
                                "feasibility": ev.feasibility,
                            }
                        )
                al.log_workflow_event(
                    session_id=session_id,
                    workflow_id=wf_id,
                    workflow_version=wf_ver,
                    event_type="pragmatist_evaluation",
                    metadata={
                        "reality_score": reality_score,
                        "blocking_concerns": blocking,
                        "verdicts": verdicts_summary,
                        "draft_version": state.get("draft_version", 0),
                    },
                )
        except Exception:
            logger.debug("Audit logging failed for pragmatist %s", node_id, exc_info=True)

        # --- Merge pragmatist verdict/score into build_responses provenance ---
        updated_build_responses = list(build_responses)
        if pragmatist_output and pragmatist_output.evaluations:
            eval_by_resp = {e.response_to: e for e in pragmatist_output.evaluations}
            for br_dict in updated_build_responses:
                evalu = eval_by_resp.get(br_dict.get("response_to", ""))
                if evalu and "provenance" in br_dict and br_dict["provenance"]:
                    br_dict["provenance"]["pragmatist_verdict"] = evalu.verdict
                    br_dict["provenance"]["pragmatist_score"] = evalu.feasibility

        # --- Save provenance to DB ---
        try:
            _save_provenance_batch(session_id, state.get("workflow_id", ""), updated_build_responses)
        except Exception:
            logger.debug("Failed to save provenance for session %s", session_id, exc_info=True)

        return {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
            "pragmatist_output": pragmatist_output.model_dump() if pragmatist_output else None,
            "build_responses": updated_build_responses,
        }

    return _pragmatist_node


def _save_provenance_batch(
    session_id: str,
    workflow_id: str,
    build_responses: list[dict],
) -> None:
    """Persist provenance entries to the build_response_provenance SQLite table.

    Delegates to :meth:`MiscRepository.save_provenance_batch` so the
    database path is configurable (default ``data/blueprints.db``) and
    the schema lives in one place — migration v32.
    """
    from backend.blueprints.repository import BlueprintRepository

    try:
        repo = BlueprintRepository()
        repo.save_provenance_batch(session_id, workflow_id, build_responses)
    except Exception as exc:
        logger.warning("Failed to save provenance for session %s: %s", session_id, exc)
