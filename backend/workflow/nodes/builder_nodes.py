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
from backend.models.transactional import CriticItem, Provenance
from backend.services.llm_service import LLMService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.node_functions import _get_profile_service
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState

logger = logging.getLogger(__name__)

_MAX_JSON_RETRIES = 3


def _extract_zero_draft(state: WorkflowState) -> str:
    """Extract the draft the Builder should improve.

    Resolution order:
      1. ``latest_draft`` — most recent Builder output (``global_revision`` or
         raw content).  This is the iterative state: the Builder is improving
         the previous revision, not the original zero draft.
      2. ``zero_draft`` — original Strategist output, used on the first
         iteration when no Builder has run yet.
      3. Most recent ``wf-strategist`` content from ``node_outputs``.
      4. ``state.context`` — ultimate fallback so the Builder always has
         something to work with.
    """
    latest = state.get("latest_draft")
    if latest:
        return latest
    zd = state.get("zero_draft")
    if zd:
        return zd
    for no in reversed(state.get("node_outputs", [])):
        if no.get("node_type") == "wf-strategist":
            return no.get("content", "")
    return state.get("context", "")


def _strip_markdown_json(text: str) -> str:
    """Strip markdown code-block fences (`` ```json … ``` ``) from a string."""
    s = text.strip()
    import re

    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", s)
    if m:
        return m.group(1).strip()
    if s.startswith("```"):
        s = s.removeprefix("```").removeprefix("json").removeprefix("JSON").strip()
        if s.endswith("```"):
            s = s.removesuffix("```").strip()
    return s


def _clean_llm_output(text: str) -> str:
    """Strip control characters (except newlines/tabs) from LLM output."""
    import re

    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)


def _extract_critic_items(state: WorkflowState) -> list[dict]:
    """Extract CriticItems from state for the current iteration.

    The ``critic_items`` accumulator is populated by ``operator.add`` and
    therefore contains items from every previous round.  When the Builder
    runs in iteration N we want only the items raised in the current round,
    not the entire history (otherwise the Builder is asked to re-fix items
    it has already addressed, which corrupts the output).

    Resolution order:
      1.  If any item in the accumulator carries a ``round`` field equal to
          ``state.current_round``, return only those items.
      2.  If no item has a ``round`` field (e.g. state was constructed
          before this fix was applied), fall back to the full accumulator —
          preserves existing behaviour.
      3.  If the accumulator is empty, scan ``node_outputs`` for the most
          recent ``wf-critic`` entry and parse its content as a JSON array.
    """
    items = state.get("critic_items", [])
    if items:
        current_round = state.get("current_round", 1)
        current_round_items = [it for it in items if it.get("round") == current_round]
        if current_round_items:
            return current_round_items
        has_round_tag = any("round" in it for it in items)
        if not has_round_tag:
            return items

    for no in reversed(state.get("node_outputs", [])):
        if no.get("node_type") == "wf-critic":
            raw = no.get("content", "")
            if not raw:
                continue
            raw = _strip_markdown_json(raw)
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [CriticItem.model_validate(c).model_dump() for c in parsed]
            except Exception:
                try:
                    from json_repair import repair_json

                    repaired = repair_json(raw)
                    parsed = json.loads(repaired)
                    if isinstance(parsed, list):
                        return [CriticItem.model_validate(c).model_dump() for c in parsed]
                except Exception:
                    continue
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
        """Builder node the instance."""
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)
        start_time = time.monotonic()

        await publish_async(
            session_id,
            "node.start",
            {
                "node_id": node_id,
                "node_type": "wf-builder",
                "role": role,
                "round": current_round,
            },
        )

        # --- Read inputs ---
        critic_items = _extract_critic_items(state)
        zero_draft = _extract_zero_draft(state)
        pragmatist_output = state.get("pragmatist_output")
        draft_version = state.get("draft_version", 1)

        if not critic_items:
            logger.warning("Builder %s: no critic_items to respond to", node_id)
            return {
                "node_outputs": [
                    {
                        "node_id": node_id,
                        "node_type": "wf-builder",
                        "role": role,
                        "content": "No critique to address.",
                        "tokens_used": 0,
                        "duration_ms": 0,
                        "status": "completed",
                    }
                ]
            }

        # --- Build prompt (hardened against meta-discussion) ---
        from backend.models.transactional import BuilderOutput

        schema = BuilderOutput.model_json_schema()
        dump = {
            "type": "object",
            "properties": schema["properties"],
            "required": schema.get("required", []),
        }
        if "$defs" in schema:
            dump["$defs"] = schema["$defs"]

        system_prompt = (
            "Du bist der Builder. Du erhältst:\n"
            "Den ORIGINAL-ENTWURF (Zero-Draft) als vollständigen Text.\n"
            "Eine Liste von CriticItems mit konkreten Mängeln.\n"
            "\n"
            "ABSOLUTE REGELN:\n"
            "Du darfst NICHT über 'die Problematik' oder 'die Herausforderung' sprechen.\n"
            "Du darfst NICHT sagen 'man sollte erwägen' oder 'es wäre denkbar'.\n"
            "Du MUSST für jeden CriticItem einen konkreten, revidierten Text liefern, "
            "der direkt in den Vertrag/Klage/Strategie eingesetzt werden kann.\n"
            "Wenn es eine Klausel betrifft: Schreibe die neue Klausel in juristischem Deutsch.\n"
            "Wenn es eine Prozessstrategie betrifft: Schreibe den konkreten nächsten Schritt "
            "mit Termin und Zuständigkeit.\n"
            "Wenn du keine Lösung hast: Schreibe 'KEINE REPARATUR MÖGLICH' und begründe "
            "in einem Satz.\n"
            "\n"
            "FORMAT: Valides JSON. Kein Markdown außerhalb des JSON. "
            "Keine Einleitung. Keine Schlussfolgerung.\n"
            "\n"
            "## Output Format\n"
            "Respond with a JSON object matching this schema:\n" + json.dumps(dump, indent=2, ensure_ascii=False)
        )

        user_prompt = f"""Original draft:\n{zero_draft}\n\nCritique items:\n{json.dumps(critic_items, indent=2, default=str)}"""

        # Inject Angel's Advocate preserved elements as constraints
        preserved_elements = state.get("preserved_elements", [])
        if preserved_elements:
            user_prompt += "\n\nThe Angel's Advocate identified these elements that MUST be preserved:\n"
            for el in preserved_elements:
                loc = el.get("source_location", "")
                text = el.get("preserved_text", "")
                rationale = el.get("rationale", "")
                user_prompt += f'- [{loc}] "{text}" — Reason: {rationale}\n'
            user_prompt += "\nYou MUST keep these elements intact in your revisions.\n"

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
                    # Strip control characters and markdown fences
                    clean = _clean_llm_output(raw)
                    clean = _strip_markdown_json(clean)
                    parsed = json.loads(clean)
                    # Handle both array and object formats
                    if isinstance(parsed, list):
                        parsed = {"build_responses": parsed, "constructivity_score": 0.0}
                    builder_output = BuilderOutput.model_validate(parsed)
                    content = raw
                    break
                except Exception as e:
                    # Try json-repair fallback
                    try:
                        from json_repair import repair_json

                        clean = _clean_llm_output(raw)
                        clean = _strip_markdown_json(clean)
                        repaired = repair_json(clean)
                        parsed = json.loads(repaired)
                        if isinstance(parsed, list):
                            parsed = {"build_responses": parsed, "constructivity_score": 0.0}
                        builder_output = BuilderOutput.model_validate(parsed)
                        content = raw
                        logger.info("Builder %s: json-repair fixed JSON on attempt %d", node_id, attempt + 1)
                        break
                    except Exception:
                        pass
                    logger.warning(
                        "Builder JSON parse attempt %d/%d failed: %s",
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
            # --- Attach Provenance to each BuildResponse ---
            critic_by_id = {c.get("critic_id", ""): c for c in critic_items}
            revision_map = {"option_a": "conservative", "option_b": "radical", "option_c": "minimal"}
            for br in builder_output.build_responses:
                c = critic_by_id.get(br.response_to, {})
                original_text = c.get("context_quote") or c.get("flaw", "")
                revision_type = revision_map.get(br.recommendation, "conservative")
                br.provenance = Provenance(
                    draft_version=draft_version,
                    critic_item_id=br.response_to,
                    original_text=original_text,
                    revision_type=revision_type,
                )
        else:
            constructivity = 0.0

        output: WorkflowNodeOutput = {
            "node_id": node_id,
            "node_type": "wf-builder",
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
                "node_type": "wf-builder",
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
                    input_data={"critic_items": critic_items, "zero_draft": zero_draft},
                    output_data={"content": content, "constructivity_score": constructivity},
                    llm_profile_id=llm_profile_id,
                    latency_ms=duration_ms,
                    prompt_tokens=0,
                    completion_tokens=tokens_used,
                    constructivity_score=constructivity,
                    draft_version=draft_version,
                )
                # Transactional Drafting: builder_iteration event
                al.log_workflow_event(
                    session_id=session_id,
                    workflow_id=wf_id,
                    workflow_version=wf_ver,
                    event_type="builder_iteration",
                    metadata={
                        "draft_version": draft_version,
                        "constructivity_score": constructivity,
                        "build_response_count": len(builder_output.build_responses) if builder_output else 0,
                    },
                    draft_version=draft_version,
                    constructivity_score=constructivity,
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
            state_update["latest_draft"] = builder_output.global_revision
        else:
            state_update["latest_draft"] = content

        return state_update

    return _builder_node
