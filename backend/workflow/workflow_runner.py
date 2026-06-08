"""Workflow runner — background execution of compiled workflow graphs.

Handles the lifecycle of a workflow execution: invoke the LangGraph graph,
manage pause/resume/cancel, save state snapshots, and publish SSE events.

Key features for the Unified Feedback System:

- **Request ID injection** — a unique ``request_id`` (UUID v4) is
  generated at the start of every ``run_workflow_background`` call and
  injected into ``initial_state`` so all downstream nodes can include it
  in their published SSE events for end-to-end log correlation.
- **WorkflowCancelledError** — a custom exception used instead of
  ``asyncio.CancelledError`` so that LangGraph's internal cancellation
  handling does not swallow the signal.  Caught alongside
  ``CancelledError`` in the main execution loop to set the session
  status to ``"cancelled"``.
- **Extension signal on cancel** — ``cancel_session()`` fires the
  extension signal via the state backend so any node blocked in
  ``wait_for_extension_signal()`` (e.g. a moderator waiting for an
  extension decision) unblocks immediately.

Sprint 37 (part 3/3) — pause/resume/cancel/status now delegate to the
unified :func:`backend.state.workflow_state.get_workflow_state` backend.
The module-level ``_pause_events`` / ``_cancelled_sessions`` /
``_session_status`` dicts that used to live here are gone; the state
backend owns them.  Audit logging for pause/resume is the only
workflow-specific side effect kept in this module.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Any

from backend.api.events import publish_async
from backend.models.artifact import (
    DebateArtifact,
    Injection,
    Turn,
)
from backend.services.artifact_store import ArtifactStore
from backend.state.workflow_state import get_workflow_state
from backend.workflow.audit_logger import get_audit_logger
from backend.workflow.immutability import lock_session
from backend.workflow.interjection import interjection_service
from backend.workflow.state_snapshot import StateSnapshotStore
from backend.workflow.workflow_compiler import CompiledWorkflow
from backend.workflow.workflow_state import WorkflowTemplate

logger = logging.getLogger(__name__)


class WorkflowCancelledError(Exception):
    """Raised by workflow nodes when the session is cancelled.

    Unlike ``asyncio.CancelledError``, this exception is **not** caught
    or suppressed by LangGraph's graph executor, which intercepts
    ``CancelledError`` for its own internal task-cancellation logic.
    Using a custom exception guarantees that the workflow runner's
    ``except WorkflowCancelledError`` block always fires, ensuring the
    session status is set to ``"cancelled"`` even when LangGraph would
    otherwise swallow the error.

    Agent nodes check ``is_cancelled(session_id)`` at the start of
    execution and raise this exception to abort cleanly.

    See Also:
        :func:`cancel_session` — marks a session as cancelled and
        fires the extension signal to unblock waiting nodes.
    """


# Module-level task tracking for asyncio cancellation.
# All other state (cancel, pause, status) lives in get_workflow_state().
_running_tasks: dict[str, asyncio.Task] = {}  # session_id -> asyncio.Task


def is_cancelled(session_id: str) -> bool:
    """Check if a session has been cancelled."""
    return get_workflow_state().is_cancelled(session_id)


def cancel_session(session_id: str) -> None:
    """Mark a session as cancelled and cancel the running asyncio task.

    Performs three actions:

    1. Sets the session status to ``"cancelled"`` via the state backend.
    2. Fires the extension signal so any node blocked in
       ``wait_for_extension_signal()`` (e.g. the moderator waiting for
       an extension decision) unblocks immediately instead of polling
       with a 2-second timeout.
    3. Cancels the ``asyncio.Task`` running the workflow graph, which
       propagates ``CancelledError`` into the graph executor.

    Args:
        session_id: The workflow session ID to cancel.
    """
    get_workflow_state().cancel(session_id)
    # Fire extension signal to unblock any waiting moderator node
    try:
        get_workflow_state().set_extension_signal(session_id)
    except Exception:
        logger.debug("Failed to fire extension signal on cancel for %s", session_id, exc_info=True)
    task = _running_tasks.get(session_id)
    if task and not task.done():
        task.cancel()


def get_session_status(session_id: str) -> str:
    """Get the current status of a session."""
    return get_workflow_state().get_status(session_id)


def set_session_status(session_id: str, status: str) -> None:
    """Set the status of a session."""
    get_workflow_state().set_status(session_id, status)


def get_pause_event(session_id: str):
    """Get or create the legacy ``asyncio.Event`` for a session.

    Kept for backward compat with code that calls ``event.wait()``
    directly (e.g.  ``run_workflow_background`` historically used
    it).  New code should use ``wait_for_pause`` /
    ``wait_for_resume`` on the state backend instead.
    """
    return get_workflow_state().get_pause_event(session_id)


def pause_session(session_id: str) -> None:
    """Pause a running session.

    Delegates to :meth:`WorkflowStateBackend.pause` and writes an
    audit-log entry.  The wake-up signal is published on the
    per-session pause channel so any ``wait_for_pause`` coroutine
    on this or another process unblocks immediately.
    """
    get_workflow_state().pause(session_id)
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id="",
            workflow_version=1,
            event_type="workflow_paused",
            actor="user",
        )
    except Exception:
        logger.debug("Audit logging failed for pause_session", exc_info=True)


def resume_session(session_id: str) -> None:
    """Resume a paused session.

    Delegates to :meth:`WorkflowStateBackend.resume` and writes
    an audit-log entry.  The wake-up signal is published on the
    per-session resume channel.
    """
    get_workflow_state().resume(session_id)
    try:
        get_audit_logger().log_workflow_event(
            session_id=session_id,
            workflow_id="",
            workflow_version=1,
            event_type="workflow_resumed",
            actor="user",
        )
    except Exception:
        logger.debug("Audit logging failed for resume_session", exc_info=True)


async def run_workflow_background(
    session_id: str,
    workflow_id: str,
    project_id: str,
    initial_state: dict[str, Any],
    compiled_workflow: CompiledWorkflow,
    snapshot_store: StateSnapshotStore,
) -> None:
    """Run a compiled workflow graph as a background task.

    This is the main execution loop for workflow-based debates.

    Args:
        session_id: Unique session identifier for this execution.
        workflow_id: The workflow definition ID.
        project_id: The project ID.
        initial_state: The initial WorkflowState dict.
        compiled_workflow: The compiled LangGraph graph and metadata.
        snapshot_store: Store for persisting state snapshots.
    """
    set_session_status(session_id, "running")

    # T-4: Generate a unique request_id for log/SSE correlation.
    # Inject into initial_state so all downstream nodes can include
    # it in their published events.
    request_id = str(uuid.uuid4())
    initial_state["request_id"] = request_id

    logger.info(
        "Workflow %s starting for session %s (request_id=%s)",
        workflow_id,
        session_id,
        request_id,
    )

    # Publish enriched workflow.started event
    await publish_async(
        session_id,
        "workflow.started",
        {
            "type": "workflow.started",
            "session_id": session_id,
            "workflow_id": workflow_id,
            "request_id": request_id,
            "node_sequence": compiled_workflow.node_sequence,
        },
    )

    start_time = time.monotonic()

    try:
        graph = compiled_workflow.graph

        # Calculate a hard recursion limit as a safety cap against infinite loops.
        # Each round uses ~len(node_sequence) node calls; add generous buffer.
        num_nodes = len(compiled_workflow.node_sequence) or 4
        max_rounds = initial_state.get("max_rounds", 10)
        recursion_limit = max(num_nodes * (max_rounds + 1) * 2 + 20, 100)
        logger.info(
            "Workflow %s: recursion_limit=%d (nodes=%d, max_rounds=%d)",
            workflow_id,
            recursion_limit,
            num_nodes,
            max_rounds,
        )

        # Invoke the compiled graph with a hard recursion limit.
        # Wrap in a tracked task so cancel_session() can interrupt it.
        graph_task = asyncio.current_task()
        if graph_task:
            _running_tasks[session_id] = graph_task
        try:
            final_state = await graph.ainvoke(
                initial_state,
                config={"recursion_limit": recursion_limit},
            )
        finally:
            _running_tasks.pop(session_id, None)

        # Save final snapshot
        snapshot_store.save(
            session_id=session_id,
            workflow_id=workflow_id,
            node_id="__final__",
            node_type="final",
            round_number=final_state.get("current_round", 0),
            state_dict=_serialize_state(final_state),
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # --- Build and save DebateArtifact for Output Composer ---
        try:
            artifact = _build_artifact_from_state(
                session_id=session_id,
                workflow_id=workflow_id,
                state=final_state,
                duration_ms=duration_ms,
            )
            ArtifactStore().save(artifact)
        except Exception:
            logger.warning(
                "Failed to build/save DebateArtifact for session %s",
                session_id,
                exc_info=True,
            )

        # Publish workflow.complete event with request_id for correlation
        await publish_async(
            session_id,
            "workflow.complete",
            {
                "type": "workflow.complete",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "request_id": request_id,
                "output": final_state.get("output", ""),
                "final_consensus": final_state.get("final_consensus", 0.0),
                "duration_ms": duration_ms,
                "node_outputs": final_state.get("node_outputs", []),
            },
        )

        set_session_status(session_id, "completed")

        debate_id = initial_state.get("debate_id")
        if debate_id:
            try:
                from backend.api.deps import get_debate_store_for_case
                from backend.persistence.debate_store import DebateStatus

                debate_store = get_debate_store_for_case(project_id)
                debate = debate_store.get(debate_id)
                if debate:
                    debate["status"] = DebateStatus.COMPLETED
                    debate["current_round"] = final_state.get("current_round", 0)
                    debate["result"] = {
                        "final_consensus": final_state.get("final_consensus", 0.0),
                        "consensus": final_state.get("final_consensus", 0.0),
                        "output": final_state.get("output", ""),
                    }
                    debate_store.put(debate_id, debate)
            except Exception:
                logger.warning("Failed to update debate record %s", debate_id, exc_info=True)

        # --- Auto-lock session and snapshots ---
        try:
            lock_session(session_id)
        except Exception:
            logger.warning("Failed to lock session %s", session_id, exc_info=True)

        # --- Audit log ---
        try:
            get_audit_logger().log_workflow_event(
                session_id=session_id,
                workflow_id=workflow_id,
                workflow_version=initial_state.get("workflow_version", 1),
                event_type="workflow_completed",
                actor="system",
                metadata={"duration_ms": duration_ms},
            )
        except Exception:
            logger.debug("Audit logging failed for workflow_completed", exc_info=True)

        logger.info(
            "Workflow %s completed for session %s in %dms",
            workflow_id,
            session_id,
            duration_ms,
        )

    except (asyncio.CancelledError, WorkflowCancelledError):
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.info("Workflow %s cancelled for session %s after %dms", workflow_id, session_id, duration_ms)

        await publish_async(
            session_id,
            "workflow.cancelled",
            {
                "type": "workflow.cancelled",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "request_id": request_id,
                "duration_ms": duration_ms,
            },
        )

        set_session_status(session_id, "cancelled")

        debate_id = initial_state.get("debate_id")
        if debate_id:
            try:
                from backend.api.deps import get_debate_store_for_case
                from backend.persistence.debate_store import DebateStatus

                debate_store = get_debate_store_for_case(project_id)
                debate = debate_store.get(debate_id)
                if debate:
                    debate["status"] = DebateStatus.CANCELLED
                    debate_store.put(debate_id, debate)
            except Exception:
                logger.warning("Failed to update debate record %s", debate_id, exc_info=True)

    except Exception as exc:
        duration_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "Workflow %s failed for session %s: %s",
            workflow_id,
            session_id,
            exc,
            exc_info=True,
        )

        # Publish node.error event
        await publish_async(
            session_id,
            "node.error",
            {
                "type": "node.error",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "error": str(exc),
                "duration_ms": duration_ms,
            },
        )

        set_session_status(session_id, "failed")

        debate_id = initial_state.get("debate_id")
        if debate_id:
            try:
                from backend.api.deps import get_debate_store_for_case
                from backend.persistence.debate_store import DebateStatus

                debate_store = get_debate_store_for_case(project_id)
                debate = debate_store.get(debate_id)
                if debate:
                    debate["status"] = DebateStatus.FAILED
                    debate["error"] = str(exc)
                    debate_store.put(debate_id, debate)
            except Exception:
                logger.warning("Failed to update debate record %s", debate_id, exc_info=True)

        # --- Auto-lock session and snapshots ---
        try:
            lock_session(session_id)
        except Exception:
            logger.warning("Failed to lock session %s", session_id, exc_info=True)

        # --- Audit log ---
        try:
            get_audit_logger().log_workflow_event(
                session_id=session_id,
                workflow_id=workflow_id,
                workflow_version=initial_state.get("workflow_version", 1),
                event_type="workflow_failed",
                actor="system",
                metadata={"error": str(exc), "duration_ms": duration_ms},
            )
        except Exception:
            logger.debug("Audit logging failed for workflow_failed", exc_info=True)

    finally:
        # Cleanup shared state.  The state backend drops cancel /
        # status / pause / wait-event entries for the session so
        # the next run starts clean.
        get_workflow_state().cleanup(session_id)
        _running_tasks.pop(session_id, None)
        await interjection_service.clear(session_id)


_MAX_SERIALIZE_DEPTH: int = 20


def _serialize_state(state: dict[str, Any]) -> dict[str, Any]:
    """Serialize WorkflowState for snapshot storage.

    Recursively converts non-JSON-serializable values to strings.
    Nested dicts and lists are preserved (not stringified) so that
    snapshots stored in SQLite retain their structure and can be
    queried or reconstructed for replay/debugging.

    A depth guard (H-02) prevents ``RecursionError`` on self-referential
    or excessively nested structures — at the limit, values fall back
    to ``str()``.
    """

    def _serialize_value(v: Any, depth: int = 0) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if depth >= _MAX_SERIALIZE_DEPTH:
            return str(v)
        if isinstance(v, dict):
            return {k: _serialize_value(val, depth + 1) for k, val in v.items()}
        if isinstance(v, list):
            return [_serialize_value(item, depth + 1) for item in v]
        if hasattr(v, "model_dump"):
            return _serialize_value(v.model_dump(mode="json"), depth + 1)
        if hasattr(v, "value"):
            return v.value
        return str(v)

    return {k: _serialize_value(v) for k, v in state.items()}


def normalize_transcript_for_display(state: dict) -> list[dict]:
    """Build transcript entries directly from transactional drafting state keys.

    Reads ``zero_draft``, ``critic_items``, and ``build_responses`` from
    the workflow state and returns a list of plain dicts compatible with
    the ``Turn`` Pydantic model.  Designed for the ``transactional_drafting``
    template where results live in top-level state keys rather than in
    the standard ``node_outputs`` list.
    """
    import uuid as _uuid

    transcript: list[dict] = []

    # Zero-Draft (Strategist)
    zd = state.get("zero_draft")
    if zd:
        content = zd if isinstance(zd, str) else str(zd)
        if len(content) > 50000:
            content = content[:25000] + "\n[… content truncated …]\n" + content[-25000:]
        transcript.append(
            {
                "id": str(_uuid.uuid4()),
                "round": 0,
                "node_id": "strategist",
                "agent_name": "Strategist",
                "role_type": "strategist",
                "content": f"**Zero-Draft erstellt:**\n\n{content}",
            }
        )

    # Critic Items
    critic_items = state.get("critic_items", [])
    if isinstance(critic_items, list):
        for i, item in enumerate(critic_items):
            data = item if isinstance(item, dict) else item.model_dump() if hasattr(item, "model_dump") else {}
            sev = data.get("severity", "mittel")
            flaw = data.get("flaw", data.get("issue", ""))
            principle = data.get("principle", "")
            target = data.get("target", "")
            transcript.append(
                {
                    "id": str(_uuid.uuid4()),
                    "round": 1,
                    "node_id": f"critic_{i}",
                    "agent_name": "Critic",
                    "role_type": "critic",
                    "content": (f"**Kritik {i + 1}** ({sev}): {flaw}\n\n*Prinzip:* {principle}\n*Betrifft:* {target}"),
                }
            )

    # Build Responses (Builder) — with provenance metadata
    build_responses_raw = state.get("build_responses", [])
    pragmatist_output = state.get("pragmatist_output", {})
    evaluations_by_resp = {}
    if pragmatist_output:
        for ev in pragmatist_output.get("evaluations", []):
            evaluations_by_resp[ev.get("response_to", "")] = ev

    if isinstance(build_responses_raw, list):
        for i, resp in enumerate(build_responses_raw):
            data = resp if isinstance(resp, dict) else resp.model_dump() if hasattr(resp, "model_dump") else {}
            rto = data.get("response_to", "?")
            opt_a = data.get("option_a", "")
            opt_b = data.get("option_b", "")
            rec = data.get("recommendation", "?")
            rationale = data.get("rationale", "")
            prov = data.get("provenance") or {}
            ev = evaluations_by_resp.get(rto, {})

            # Build provenance marginalia line
            marginalia = []
            if prov.get("draft_version"):
                marginalia.append(f"Iteration {prov['draft_version']}")
            if prov.get("critic_item_id"):
                marginalia.append(f"Critic: {prov['critic_item_id']}")
            if prov.get("revision_type"):
                opt_letter = "A" if prov["revision_type"] == "conservative" else "B" if prov["revision_type"] == "radical" else "C"
                marginalia.append(f"Builder: Option {opt_letter}")
            if ev:
                marginalia.append(f"Pragmatist: {ev.get('verdict', '?')} ({ev.get('feasibility', '?')})")

            parts = [
                f"**Lösung für {rto}**",
            ]
            if opt_a:
                parts.append(f"\n**A (Konservativ):** {opt_a}")
            if opt_b:
                parts.append(f"\n**B (Radikal):** {opt_b}")
            parts.append(f"\n**Empfohlen:** {rec}")
            if rationale:
                parts.append(f"\n*Begründung:* {rationale}")
            if marginalia:
                parts.append(f"\n\n---\n*{' | '.join(marginalia)}*")
            transcript.append(
                {
                    "id": str(_uuid.uuid4()),
                    "round": 2,
                    "node_id": f"builder_{i}",
                    "agent_name": "Builder",
                    "role_type": "builder",
                    "content": "".join(parts),
                    "metadata": {
                        "provenance": {
                            "draft_version": prov.get("draft_version"),
                            "critic_item_id": prov.get("critic_item_id"),
                            "original_text": prov.get("original_text", ""),
                            "revision_type": prov.get("revision_type"),
                            "pragmatist_verdict": ev.get("verdict"),
                            "pragmatist_score": ev.get("feasibility"),
                        },
                    },
                }
            )

    return transcript


def normalize_transcript_content(content: str, role: str) -> str:
    """Convert structured JSON output (critic, builder, pragmatist) into
    readable Markdown for the frontend transcript view."""
    import json as _json

    if not content or not content.strip():
        return content

    raw = content.strip()
    if raw.startswith("```json"):
        raw = raw.removeprefix("```json").strip()
    if raw.endswith("```"):
        raw = raw.removesuffix("```").strip()
    if raw.startswith("```"):
        raw = raw.removeprefix("```").strip()

    try:
        parsed = _json.loads(raw)
    except (_json.JSONDecodeError, ValueError):
        return content

    lines: list[str] = []

    if role == "critic" and isinstance(parsed, list):
        for item in parsed:
            cid = item.get("critic_id", "?")
            sev = item.get("severity", "?").upper()
            target = item.get("target", "")
            flaw = item.get("flaw", "")
            principle = item.get("principle", "")
            quote = item.get("context_quote")
            lines.append(f"**{cid} [{sev}]**  ")
            if target:
                lines.append(f"**Target:** {target}  ")
            if flaw:
                lines.append(f"**Flaw:** {flaw}  ")
            if principle:
                lines.append(f"**Principle:** {principle}  ")
            if quote:
                lines.append(f"> {quote}")
            lines.append("")
        return "\n".join(lines)

    if role == "builder" and isinstance(parsed, dict):
        responses = parsed.get("build_responses", [])
        for resp in responses:
            rto = resp.get("response_to", "?")
            opt_a = resp.get("option_a", "")
            opt_b = resp.get("option_b", "")
            opt_c = resp.get("option_c")
            rec = resp.get("recommendation", "?")
            risk = resp.get("risk_assessment", "?")
            rationale = resp.get("rationale", "")
            lines.append(f"**Response to {rto}**  ")
            if opt_a:
                lines.append(f"**Option A:** {opt_a}  ")
            if opt_b:
                lines.append(f"**Option B:** {opt_b}  ")
            if opt_c:
                lines.append(f"**Option C:** {opt_c}  ")
            lines.append(f"**Recommendation:** {rec} / Risk: {risk}  ")
            if rationale:
                lines.append(f"_{rationale}_")
            lines.append("")
        if lines:
            return "\n".join(lines)

    if role == "pragmatist" and isinstance(parsed, dict):
        evals = parsed.get("evaluations", [])
        concerns = parsed.get("blocking_concerns", [])
        rscore = parsed.get("reality_score")
        for ev in evals:
            rto = ev.get("response_to", "?")
            feas = ev.get("feasibility", "?")
            prisk = ev.get("process_risk", "?")
            cost = ev.get("cost_time_estimate", "?")
            verdict = ev.get("verdict", "?")
            note = ev.get("revision_note")
            lines.append(f"**Evaluation of {rto}**  ")
            lines.append(f"Feasibility: {feas} / Risk: {prisk} / Cost: {cost}  ")
            lines.append(f"**Verdict:** {verdict}  ")
            if note:
                lines.append(f"*{note}*")
            lines.append("")
        if rscore is not None:
            lines.append(f"**Reality Score:** {rscore}  ")
        if concerns:
            lines.append("**Blocking Concerns:**")
            for c in concerns:
                lines.append(f"- {c}")
        if lines:
            return "\n".join(lines)

    return content


def _build_artifact_from_state(
    *,
    session_id: str,
    workflow_id: str,
    state: dict[str, Any],
    duration_ms: int = 0,
) -> DebateArtifact:
    """Build a ``DebateArtifact`` from the final workflow state.

    Extracts transcript turns, interjections, user queries, and
    metadata from the LangGraph state dict.  This is the bridge
    between the workflow execution layer and the Output Composer.
    """

    # Transactional Drafting: build transcript from state keys directly
    if state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING:
        entries = normalize_transcript_for_display(state)
        turns = [Turn(**entry) for entry in entries]
        # Skip the standard node_outputs loop below — turns already built
        # Build remaining fields (interjections, metadata, etc.)
        return _build_artifact_common(
            session_id=session_id,
            workflow_id=workflow_id,
            state=state,
            duration_ms=duration_ms,
            turns=turns,
        )

    # Build turns from node_outputs
    node_configs = state.get("node_configs", {})
    config_by_node: dict[str, dict] = {}
    for nid, cfg in node_configs.items():
        if isinstance(cfg, str):
            try:
                import ast

                cfg = ast.literal_eval(cfg)
            except (ValueError, SyntaxError):
                cfg = {}
        config_by_node[nid] = cfg if isinstance(cfg, dict) else {}

    _system_roles = {"complete", "input", "initialize"}

    # Sort node_outputs by node_sequence to restore logical phase order.
    # With fan-out, parallel agents complete in arbitrary LLM-response
    # order — sorting by the compile-time sequence restores the intended
    # phase flow (all Phase 1 agents → gate → Phase 2 agents → …).
    node_sequence = state.get("node_sequence", [])
    seq_order = {nid: i for i, nid in enumerate(node_sequence)}

    def _output_sort_key(output: dict) -> tuple[int, int]:
        nid = output.get("node_id", "")
        return (output.get("round", 0), seq_order.get(nid, 9999))

    sorted_outputs = sorted(
        state.get("node_outputs", []),
        key=_output_sort_key,
    )

    turns: list[Turn] = []
    for output in sorted_outputs:
        role = output.get("role", "")
        if role in _system_roles:
            continue
        node_id = output.get("node_id", "")
        config = config_by_node.get(node_id, {})
        llm_model = config.get("llm_model", "")
        llm_profile_id = config.get("llm_profile_id", "")
        llm_profile_name = config.get("llm_profile_name", "")
        role_type_name = config.get("role_type_name", role.title() if role else "")

        # Build descriptive agent name: "Critic (owl-alpha)"
        agent_name = role_type_name or role.title() if role else ""
        if llm_model:
            agent_name = f"{agent_name} ({llm_model})"
        elif llm_profile_name:
            agent_name = f"{agent_name} ({llm_profile_name})"
        elif llm_profile_id:
            agent_name = f"{agent_name} ({llm_profile_id})"

        raw_content = output.get("content", "")
        turns.append(
            Turn(
                node_id=node_id,
                round=output.get("round", 0),
                agent_name=agent_name,
                role_type=role,
                llm_profile_id=llm_profile_id,
                llm_profile_name=llm_profile_name,
                content=normalize_transcript_content(raw_content, role),
                latency_ms=output.get("duration_ms", 0),
                token_usage={"total": output.get("tokens_used", 0)},
            )
        )

    return _build_artifact_common(
        session_id=session_id,
        workflow_id=workflow_id,
        state=state,
        duration_ms=duration_ms,
        turns=turns,
    )


def _build_verdict_map(
    build_responses: list[dict],
    evaluations: list[dict],
) -> list[dict]:
    """Build a merged CriticItem → BuildResponse → PragmatistEvaluation map.

    Each entry links a critic item to its build response options and the
    pragmatist verdict for each option.  Used by the report template to
    render the "Konstruktionsprotokoll" table.
    """
    verdict_map: list[dict] = []
    eval_by_resp = {e.get("response_to", ""): e for e in evaluations}

    for br in build_responses:
        critic_id = br.get("response_to", "")
        provenance = br.get("provenance", {}) or {}
        ev = eval_by_resp.get(critic_id, {})

        verdict_map.append(
            {
                "critic_item_id": critic_id,
                "option_a": br.get("option_a", ""),
                "option_b": br.get("option_b", ""),
                "option_c": br.get("option_c", ""),
                "rationale": br.get("rationale", ""),
                "implementable": br.get("implementable", False),
                "verdict": ev.get("verdict", provenance.get("pragmatist_verdict", "pending")),
                "feasibility": ev.get("feasibility", provenance.get("pragmatist_score")),
                "revision_type": provenance.get("revision_type", ""),
                "draft_version": provenance.get("draft_version", 0),
            }
        )

    return verdict_map


def _build_artifact_common(
    *,
    session_id: str,
    workflow_id: str,
    state: dict[str, Any],
    duration_ms: int,
    turns: list[Turn],
) -> DebateArtifact:
    """Build the shared fields of a DebateArtifact (interjections, metadata,
    consensus) and return the completed artifact.  Used by both the standard
    node_outputs path and the transactional-drafting fast path."""
    from datetime import UTC, datetime

    # Build interjections from consumed_interjections
    interjections: list[Injection] = []
    for ij in state.get("consumed_interjections", []):
        if isinstance(ij, dict):
            interjections.append(
                Injection(
                    id=ij.get("interjection_id", ""),
                    source=ij.get("source", "user"),
                    target_node_id=ij.get("target_node_id", ""),
                    content=ij.get("content", ""),
                )
            )

    # Build tone profile snapshot
    tone_snapshot = state.get("tone_profiles", {})

    # Metadata
    now = datetime.now(UTC)
    metadata: dict[str, Any] = {
        "token_usage": {
            "total": sum(t.token_usage.get("total", 0) for t in turns),
        },
        "timestamps": {
            "end": now.isoformat(),
        },
        "duration_ms": duration_ms,
        "workflow_template": state.get("workflow_template", "debate"),
    }

    # Include transactional drafting data in metadata for report generation
    if state.get("workflow_template") == WorkflowTemplate.TRANSACTIONAL_DRAFTING:
        pragmatist_out = state.get("pragmatist_output")
        metadata["transactional"] = {
            "critic_items": state.get("critic_items", []),
            "build_responses": state.get("build_responses", []),
            "pragmatist_evaluations": (pragmatist_out.get("evaluations", []) if isinstance(pragmatist_out, dict) else []),
            "pragmatist_verdicts": _build_verdict_map(
                state.get("build_responses", []),
                pragmatist_out.get("evaluations", []) if isinstance(pragmatist_out, dict) else [],
            ),
        }

    # Transactional Drafting scores
    pragmatist_output = state.get("pragmatist_output")
    pragmatist_reality = None
    if isinstance(pragmatist_output, dict):
        pragmatist_reality = pragmatist_output.get("reality_score")

    critic_items = state.get("critic_items", [])
    build_responses = state.get("build_responses", [])

    return DebateArtifact(
        session_id=session_id,
        workflow_id=workflow_id,
        workflow_version=state.get("workflow_version", 1),
        workflow_name=state.get("workflow_name", ""),
        title=state.get("title", ""),
        topic=state.get("context", ""),
        tone_profile_snapshot=tone_snapshot,
        transcript=turns,
        interjections=interjections,
        consensus_result={
            "score": state.get("final_consensus", 0.0),
        },
        final_assessment=state.get("final_assessment"),
        usability_score=state.get("usability_score"),
        remaining_blockers=state.get("remaining_blockers", []),
        constructivity_score=state.get("constructivity_score"),
        draft_versions=state.get("draft_version", 0),
        critic_item_count=len(critic_items) if isinstance(critic_items, list) else 0,
        build_response_count=len(build_responses) if isinstance(build_responses, list) else 0,
        pragmatist_reality_score=pragmatist_reality,
        metadata=metadata,
    )
