"""Agent node factory for LangGraph workflow execution.

Creates agent execution nodes that resolve their ``AgentBlueprint`` at
runtime and call the LLM via ``LLMService``.

Each agent node publishes enriched feedback events for the Unified
Feedback System:

- ``llm.call_started`` — emitted before the LLM call with the resolved
  model name, provider, and ``request_id`` for frontend correlation.
- ``llm.error`` — emitted on LLM failure with a classified error
  (rate_limit, timeout, content_filter, network, unknown) and a
  user-friendly message so the frontend ``ErrorPanel`` can display
  actionable guidance.

Error classification is handled by :func:`_classify_llm_error` and
human-readable messages by :func:`_user_friendly_error_message`.
"""

from __future__ import annotations

import json as _json
import logging
import re
import time
from collections.abc import Callable

from backend.api.events import publish_async
from backend.services.llm_service import LLMService
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.domains import get_decision_matrix
from backend.workflow.interjection import interjection_service
from backend.workflow.nodes._draft_helpers import truncate_running_draft
from backend.workflow.workflow_state import WorkflowNodeOutput, WorkflowState, WorkflowTemplate

logger = logging.getLogger(__name__)


# Sprint 35 (L2 fix): promote the ``_max_draft_len`` magic number
# (formerly a function-local 50000 in the non-transactional concat
# branch) to a module-level constant so its purpose is discoverable
# from the module top and so future tuning lives in one place.
#
# Sprint 39 (H2 fix): the constants and the head+tail truncation
# logic are now in ``backend.workflow.nodes._draft_helpers`` so the
# interjection node and the legacy ``run_agent_node`` use the same
# bounds.  The single-source-of-truth constants live there; this
# file imports the helper directly and no longer holds local copies.


def _classify_llm_error(exc: Exception) -> str:
    """Classify an LLM exception into a user-friendly error category.

    Inspects the exception type and message content to determine the
    most likely cause of failure. Used by agent nodes to populate the
    ``error_class`` field of ``llm.error`` SSE events.

    Args:
        exc: The exception raised during an LLM call.

    Returns:
        One of ``'rate_limit'``, ``'timeout'``, ``'content_filter'``,
        ``'network'``, or ``'unknown'``.
    """
    exc_str = str(exc).lower()
    exc_type = type(exc).__name__.lower()

    # Rate limit (HTTP 429)
    if "429" in exc_str or "rate limit" in exc_str or "ratelimit" in exc_str:
        return "rate_limit"

    # Timeout
    if "timeout" in exc_str or "timeout" in exc_type or "timed out" in exc_str:
        return "timeout"
    if isinstance(exc, TimeoutError):
        return "timeout"

    # Content filter
    if "content_filter" in exc_str or "content_policy" in exc_str or "safety" in exc_str:
        return "content_filter"

    # Network
    if "connect" in exc_str or "connection" in exc_str or "network" in exc_str:
        return "network"
    if isinstance(exc, (ConnectionError, OSError)):
        return "network"

    return "unknown"


def _user_friendly_error_message(error_class: str) -> str:
    """Return a user-facing message string for a classified LLM error.

    Maps each error class to a concise, actionable message displayed in
    the frontend ``ErrorPanel``. Falls back to a generic message for
    unrecognised classes.

    Args:
        error_class: One of ``'rate_limit'``, ``'timeout'``,
            ``'content_filter'``, ``'network'``, or ``'unknown'``.

    Returns:
        A short, user-friendly error message string.
    """
    messages = {
        "rate_limit": "Model is busy — switching to backup model…",
        "timeout": "LLM response took too long — retrying…",
        "content_filter": "Response was filtered — adjusting and retrying…",
        "network": "Connection issue — retrying…",
        "unknown": "Something went wrong — please try again",
    }
    return messages.get(error_class, messages["unknown"])


def _estimate_tokens(content: str) -> int:
    """Best-effort token estimate for a piece of LLM-generated text.

    Used as a fallback when the LLM response object reports
    ``tokens_out == 0`` (some providers omit the count for streaming
    or non-billing contexts).  The historical estimate
    ``len(content.split())`` counted whitespace-separated tokens, not
    LLM tokens, and underestimated the real cost by ~3-4x for
    English / German prose.

    The rule of thumb ``1 token ≈ 4 characters`` is an industry
    standard used by tiktoken, OpenAI cookbook, and Anthropic docs;
    we apply it to the raw character count and round up to at least
    1 for any non-empty content so the audit log never records
    ``tokens_used=0`` for a successful LLM call.
    """
    if not content:
        return 0
    return max(1, len(content) // 4)


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
    # Sprint 35 (L1 fix): removed dead blueprint_name lookup — the result
    # was discarded.  The docstring above still describes the key for
    # callers, and the name is never read in this module.
    model_params = resolved_config.get("model_params", {}) or {}

    # Extract tone_profile_source_node_id from resolved config
    tone_profile_source_node_id = resolved_config.get("tone_profile_source_node_id")

    async def _agent_node(state: WorkflowState) -> dict:
        """Agent node the instance."""
        session_id = state.get("session_id", "")
        current_round = state.get("current_round", 1)

        # Check for cancellation before starting work.
        # 4.2: Use WorkflowCancelledError instead of asyncio.CancelledError
        # to avoid ambiguity with LangGraph's internal cancellation handling.
        from backend.workflow.workflow_runner import WorkflowCancelledError, is_cancelled

        if is_cancelled(session_id):
            raise WorkflowCancelledError(f"Workflow session {session_id} was cancelled")

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

        # --- Inject CriticItem JSON schema + decision matrix for wf-critic ---
        # IMPORTANT: Decision matrix only applies to Transactional Drafting,
        # not standard debate workflows (Akzeptanzkriterium).
        if node_type == "wf-critic" and state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING:
            from backend.models.transactional import CriticItem

            schema = CriticItem.model_json_schema()
            agent_tags = resolved_config.get("agent_tags") or []
            decision_matrix = get_decision_matrix(agent_tags)
            system_prompt = system_prompt + "\n\n" + decision_matrix + "\n\n"
            system_prompt += (
                "## Rules\n"
                "- Maximum 10 CriticItems per round. Prioritize blocking and critical severity.\n"
                "- You MUST NEVER say 'Das sollte überprüft werden' or 'Man sollte prüfen, ob…'. "
                "Instead: 'Die Klausel verstößt gegen X, weil Y.'\n"
                "- Every item MUST have a concrete target, principle, and flaw.\n\n"
            )
            system_prompt += "## Output Format\nRespond with a JSON array. Every object must match this schema:\n" + _json.dumps(
                {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": schema["properties"],
                        "required": schema.get("required", []),
                    },
                },
                indent=2,
                ensure_ascii=False,
            )

        # --- Inject tone profile if configured ---
        tone_profile_name: str | None = None
        # Sprint 34 (M4 fix): track tone profile injection failures
        # explicitly so the user (or the audit log) can see when a
        # configured profile failed to apply.  Previously the
        # ``except Exception`` swallowed the error and the workflow
        # silently continued without a tone profile.
        tone_profile_error: str | None = None
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
                    tone_profile_error = f"{type(exc).__name__}: {exc}"
                    logger.warning(
                        "Failed to inject tone profile for agent %s (node %s): %s",
                        role,
                        node_id,
                        exc,
                    )
            else:
                # Source node is configured but produced no profile —
                # the upstream tone-profile node may have failed or not
                # run yet.  Surface this so callers can see that the
                # profile was *expected* but *missing*.
                tone_profile_error = f"tone_profile_source_node_id '{tone_profile_source_node_id}' produced no profile_data in state['tone_profiles']"
                logger.warning(
                    "Tone profile source '%s' produced no data for agent %s (node %s)",
                    tone_profile_source_node_id,
                    role,
                    node_id,
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
            logger.debug(
                "agent %s (node %s): service_injs=%d, state_queue=%d, total=%d",
                role,
                node_id,
                len(service_injs),
                len(state.get("interjection_queue", [])),
                len(interjection_queue),
            )
        except Exception:
            logger.warning("Failed to consume interjection service for session=%s node=%s", session_id, node_id, exc_info=True)

        if interjection_queue:
            inj_text = "\n\n--- ADDITIONAL CONTEXT (User) ---\n"
            inj_text += "\n".join(f"- {inj['content']}" for inj in interjection_queue)
            user_prompt += inj_text
            logger.debug(
                "agent %s (node %s, round %d): injected %d interjections into prompt",
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

        # T-1: Peek at the LLM profile to include model and provider
        # in the llm.call_started event.  If resolution fails, we
        # still publish the event with empty values — the actual
        # LLMService creation happens inside the try block below.
        llm_model = ""
        llm_provider = ""
        try:
            _peek_svc = LLMService(
                profile_id=llm_profile_id,
                profile_service=_get_profile_service(),
            )
            llm_model = getattr(_peek_svc.profile, "model", "") if _peek_svc.profile else ""
            llm_provider = str(getattr(_peek_svc.profile, "provider", "")) if _peek_svc.profile else ""
        except Exception:
            pass

        # Publish enriched LLM call started event for live progress feedback
        await publish_async(
            session_id,
            "llm.call_started",
            {
                "node_id": node_id,
                "node_type": node_type,
                "role": role,
                "round": current_round,
                "llm_profile_id": llm_profile_id,
                "model": llm_model,
                "provider": llm_provider,
                "request_id": state.get("request_id", ""),
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
                tokens_used = _estimate_tokens(content)

            tokens_used = gen_result.tokens_out if gen_result.tokens_out > 0 else _estimate_tokens(content)
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

            # T-2: Publish structured llm.error event for frontend feedback
            error_class = _classify_llm_error(exc)
            await publish_async(
                session_id,
                "llm.error",
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "role": role,
                    "round": current_round,
                    "error_class": error_class,
                    "message": _user_friendly_error_message(error_class),
                    "raw_error": str(exc)[:500],
                    "request_id": state.get("request_id", ""),
                },
            )

            content = f"[{role}] Round {current_round}: LLM call failed ({exc})"
            tokens_used = _estimate_tokens(content)
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
            if tone_profile_error:
                audit_metadata["tone_profile_error"] = tone_profile_error

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

        # Keep current_draft bounded to prevent unbounded context growth
        # across feedback loops.  Uses head+tail preservation so the start
        # of the debate isn't lost.
        #
        # For transactional drafting this concatenation is harmful: the
        # Strategist's ``zero_draft`` is the artifact being refined, but
        # appending every critic / angel's-advocate / pragmatist message
        # turns ``current_draft`` into a garbage dump.  The Builder reads
        # ``latest_draft`` for the iterative state and ``zero_draft`` for
        # the first iteration — neither benefits from this concatenation.
        is_transactional = state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING
        state_update: dict = {
            "node_outputs": [output],
            "messages": [{"role": role, "content": content, "round": current_round}],
        }
        # Meta-agent roles (orchestrator) produce flow-control JSON, not
        # debate content.  Appending their output to current_draft pollutes
        # the context for subsequent debate agents, causing them to discuss
        # meta-evaluation (e.g. "the moderator score rose from 0.72 to 0.79")
        # instead of the actual debate topic.
        _meta_agent_roles = {"orchestrator"}
        if not is_transactional and role not in _meta_agent_roles:
            existing_draft = state.get("current_draft", "")
            new_draft = existing_draft + f"\n\n[{role.upper()} Round {current_round}]\n{content}"
            # Sprint 39 (H2 fix): tail-only truncation via the
            # shared helper.  Previous head+tail logic dropped
            # the early debate history that subsequent agents
            # need for context continuity.  The shared helper is
            # also used by ``system_nodes.interjection_node`` and
            # ``legacy_nodes.run_agent_node`` so the bound is
            # applied consistently across all three accumulators.
            state_update["current_draft"] = truncate_running_draft(new_draft)

        # --- Transactional Drafting: populate domain-specific state keys ---
        if node_type == "wf-critic":
            items = _parse_critic_output(content, node_id)
            if items:
                for item in items:
                    if "round" not in item:
                        item["round"] = current_round
                state_update["critic_items"] = items
        elif node_type == "wf-strategist":
            state_update["zero_draft"] = content

        return state_update

    return _agent_node


_SEVERITY_MAP = {
    "blocking": "blocking",
    "critical": "critical",
    "warning": "warning",
    "cosmetic": "cosmetic",
    "hoch": "critical",
    "mittel": "warning",
    "niedrig": "cosmetic",
    "high": "critical",
    "medium": "warning",
    "low": "cosmetic",
    "kritisch": "critical",
    "schwer": "critical",
    "gering": "cosmetic",
}


def _normalize_severity(val: str | None) -> str:
    """Normalize severity the instance."""
    if not val:
        return "warning"
    return _SEVERITY_MAP.get(val.lower().strip(), "warning")


def _map_to_critic_item(item: dict, idx: int) -> dict:
    """Map to critic item the instance."""
    severity = _normalize_severity(item.get("severity"))

    raw_id = item.get("critic_id") or item.get("id") or item.get("criticId") or str(idx + 1)
    if isinstance(raw_id, (int, float)):
        critic_id = f"c-critic_1-{int(raw_id):03d}"
    elif isinstance(raw_id, str) and re.match(r"^c-\w+-\d{3}$", raw_id):
        critic_id = raw_id
    else:
        critic_id = f"c-critic_1-{idx + 1:03d}"

    target = (
        item.get("target")
        or item.get("section")
        or item.get("location")
        or item.get("bereich")
        or item.get("abschnitt")
        or item.get("paragraph")
        or ""
    )
    flaw = (
        item.get("flaw") or item.get("criticism") or item.get("description") or item.get("kritik") or item.get("problem") or item.get("mangel") or ""
    )
    principle = (
        item.get("principle")
        or item.get("norm")
        or item.get("rule")
        or item.get("principle_violated")
        or item.get("suggestion")
        or item.get("empfehlung")
        or item.get("category")
        or ""
    )
    context_quote = item.get("context_quote") or item.get("quote") or item.get("zitat") or item.get("context") or item.get("evidence") or None

    mapped = {
        "critic_id": critic_id,
        "severity": severity,
        "target": str(target)[:500] if target else "",
        "flaw": str(flaw)[:500] if flaw else "",
        "principle": str(principle)[:500] if principle else "",
    }
    if context_quote:
        mapped["context_quote"] = str(context_quote)[:500]

    return mapped


def _parse_critic_output(content: str, node_id: str) -> list[dict] | None:
    """Parse LLM output for wf-critic into a list of CriticItem dicts.
    Handles markdown code fences, field aliases, and severity translation.
    """
    raw = content.strip()

    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if m:
        raw = m.group(1).strip()

    try:
        parsed = _json.loads(raw)
    except Exception:
        try:
            from json_repair import repair_json

            repaired = repair_json(raw)
            parsed = _json.loads(repaired)
            logger.info("_parse_critic_output[%s]: json-repair fixed %d chars → %d chars", node_id, len(raw), len(repaired))
        except Exception:
            logger.warning("_parse_critic_output[%s]: JSON decode failed on: %s…", node_id, raw[:200])
            return None

    if not isinstance(parsed, list):
        parsed = [parsed]

    from backend.models.transactional import CriticItem

    items: list[dict] = []
    for idx, c in enumerate(parsed):
        if not isinstance(c, dict):
            continue
        try:
            items.append(CriticItem.model_validate(c).model_dump())
            continue
        except Exception:
            pass
        mapped = _map_to_critic_item(c, idx)
        try:
            items.append(CriticItem.model_validate(mapped).model_dump())
        except Exception:
            logger.warning("_parse_critic_output[%s]: skipping item %d: %s…", node_id, idx, str(c)[:120])

    if not items:
        logger.warning("_parse_critic_output[%s]: zero items extracted from content", node_id)
        return None

    logger.info("_parse_critic_output[%s]: extracted %d critic items", node_id, len(items))
    return items
