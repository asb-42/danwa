"""HITL API router — endpoints for bidirectional human-in-the-loop interactions.

Endpoints:
    POST /debate/{id}/inject     — User injects context into running debate
    POST /debate/{id}/respond    — User responds to an agent query
    POST /debate/{id}/pause      — Pause or resume a running debate
    GET  /debate/{id}/hitl/status — Current HITL state for a debate
    GET  /debate/{id}/interactions — Interaction history (paginated)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_debate_store_for_case, get_project_id
from backend.api.events import publish_async
from backend.state.workflow_state import get_workflow_state
from backend.workflow.hitl.contracts import (
    ExtensionDecision,
    ExtensionDecisionModel,
    ExtensionRequest,
    ExtensionResponse,
    HITLMode,
    HITLStatusResponse,
    InjectRequest,
    InjectResponse,
    InteractionDirection,
    InteractionListResponse,
    InteractionResponse,
    InteractionStatus,
    InteractionType,
    InterruptInfo,
    InterruptStatus,
    PauseRequest,
    PauseResponse,
    RespondRequest,
    RespondResponse,
)
from backend.workflow.hitl.security import scan_for_injection

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory HITL state (per debate)
# In production, this would be backed by Redis or a database.
# ---------------------------------------------------------------------------

# Maximum number of interaction log entries kept per debate before
# the oldest entries are evicted.  Prevents unbounded memory growth
# in long-running deployments.
_MAX_LOG_PER_DEBATE: int = 1000

# debate_id → list of interactions
_interaction_log: dict[str, list[dict]] = {}

# debate_id → interrupt context (if active)
_active_interrupts: dict[str, dict] = {}

# debate_id → HITL configuration
_hitl_config: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Helper functions (used by workflow nodes)
# ---------------------------------------------------------------------------


def get_hitl_config(debate_id: str) -> dict:
    """Get HITL configuration for a debate."""
    return _hitl_config.get(
        debate_id,
        {
            "hitl_enabled": True,
            "hitl_mode": "full",
            "auto_query_threshold": 0.4,
            "max_interrupts_per_round": 3,
            "interrupt_timeout_seconds": 300,
        },
    )


def set_hitl_config(debate_id: str, config: dict) -> None:
    """Set HITL configuration for a debate."""
    _hitl_config[debate_id] = config


def is_paused(debate_id: str) -> bool:
    """Check if a debate is currently paused.

    Sprint 38 part 3/3: delegates to the workflow state backend
    so the HITL pause survives process restarts when Redis is
    configured, and so ``workflow_state`` is the single source
    of truth for all pause-related state.  The HITL pause is
    distinct from the session-level ``workflow_runner`` pause
    (different concern, different storage key).
    """
    return get_workflow_state().get_hitl_pause(debate_id) is not None


def get_active_interrupt(debate_id: str) -> dict | None:
    """Get the active interrupt for a debate (if any)."""
    return _active_interrupts.get(debate_id)


def get_pending_injects(debate_id: str) -> list[dict]:
    """Get pending inject interactions for a debate (not yet consumed)."""
    return [i for i in _interaction_log.get(debate_id, []) if i["type"] == "inject" and i["status"] == "pending"]


def consume_inject(debate_id: str, interaction_id: str) -> None:
    """Mark an inject interaction as consumed."""
    for interaction in _interaction_log.get(debate_id, []):
        if interaction["interaction_id"] == interaction_id:
            interaction["status"] = "consumed"
            break


def consume_all_pending_injects(debate_id: str) -> None:
    """Mark all pending inject interactions as consumed."""
    for interaction in _interaction_log.get(debate_id, []):
        if interaction["type"] == "inject" and interaction["status"] == "pending":
            interaction["status"] = "consumed"


def register_agent_query(debate_id: str, query_context: dict) -> str:
    """Register an agent query (creates an interrupt).

    Called by workflow nodes when an agent needs clarification.
    If an interrupt is already active for this debate, the previous
    one is resolved automatically with a placeholder response so the
    user's attention is not silently stolen.

    Args:
        debate_id: The debate ID.
        query_context: Dict with agent_role, agent_index, round, question, context.

    Returns:
        The interrupt_id.
    """
    # If an interrupt is already active, auto-resolve it so the agent
    # is not left hanging indefinitely (S-02 fix).
    existing = _active_interrupts.get(debate_id)
    if existing and existing.get("status") == "waiting":
        logger.warning(
            "Auto-resolving previous interrupt %s for debate %s before registering new query from %s",
            existing["interrupt_id"],
            debate_id,
            query_context.get("agent_role", "unknown"),
        )
        resolve_interrupt(
            debate_id,
            "[Auto-resolved: a new agent query arrived before the user responded]",
        )

    interrupt_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()
    config = get_hitl_config(debate_id)

    interrupt = {
        "interrupt_id": interrupt_id,
        "debate_id": debate_id,
        "agent_role": query_context["agent_role"],
        "agent_index": query_context.get("agent_index", 0),
        "round": query_context.get("round", 0),
        "question": query_context["question"],
        "context": query_context.get("context", ""),
        "created_at": now,
        "timeout_seconds": config.get("interrupt_timeout_seconds", 300),
        "status": "waiting",
        "response": None,
        "responded_at": None,
    }

    _active_interrupts[debate_id] = interrupt

    # Log the interaction
    _log_interaction(
        debate_id,
        {
            "interaction_id": str(uuid.uuid4()),
            "type": "query",
            "direction": "agent_to_user",
            "source": query_context["agent_role"],
            "target": "user",
            "content": query_context["question"],
            "round": query_context.get("round", 0),
            "agent_index": query_context.get("agent_index", 0),
            "timestamp": now,
            "status": "pending",
            "metadata": {
                "interrupt_id": interrupt_id,
                "context": query_context.get("context", "")[:200],
            },
        },
    )

    logger.info(
        "Agent query registered: interrupt=%s, agent=%s, round=%d",
        interrupt_id,
        query_context["agent_role"],
        query_context.get("round", 0),
    )

    return interrupt_id


def resolve_interrupt(debate_id: str, response: str) -> dict | None:
    """Resolve an active interrupt with the user's response.

    Args:
        debate_id: The debate ID.
        response: The user's response text.

    Returns:
        The resolved interrupt context, or None if no active interrupt.

    Sprint 38 (2/3) — also fires the per-session
    ``set_extension_signal`` so any node waiting on the
    extension decision (e.g.  ``extension_request_node``)
    wakes up immediately when the user responds to an
    extension interrupt via ``respond_to_interrupt``.  This
    is the second code path for extension decisions
    alongside ``extension_decision``; both fire the same
    signal.  Best-effort: failure is logged but does not
    affect the response.
    """
    interrupt = _active_interrupts.get(debate_id)
    if not interrupt:
        return None

    now = datetime.now(UTC).isoformat()
    interrupt["status"] = "answered"
    interrupt["response"] = response
    interrupt["responded_at"] = now

    # Log the response interaction
    _log_interaction(
        debate_id,
        {
            "interaction_id": str(uuid.uuid4()),
            "type": "response",
            "direction": "user_to_agent",
            "source": "user",
            "target": interrupt["agent_role"],
            "content": response,
            "round": interrupt["round"],
            "agent_index": interrupt["agent_index"],
            "timestamp": now,
            "status": "delivered",
            "metadata": {"interrupt_id": interrupt["interrupt_id"]},
        },
    )

    # Remove from active interrupts
    resolved = _active_interrupts.pop(debate_id)

    # Sprint 38 (2/3) — fire the per-session extension signal
    # so any waiter (``extension_request_node``) on this
    # session unblocks immediately.  ``session_id ==
    # debate_id`` in this codebase, so we use debate_id as
    # the signal key.  Best-effort — the waiter has a 2 s
    # fallback timeout in case this fails.
    try:
        from backend.state.workflow_state import get_workflow_state

        get_workflow_state().set_extension_signal(debate_id)
    except Exception:
        logger.debug(
            "Failed to fire extension signal on resolve_interrupt for %s",
            debate_id,
            exc_info=True,
        )

    logger.info(
        "Interrupt resolved: interrupt=%s, response_length=%d",
        resolved["interrupt_id"],
        len(response),
    )

    return resolved


def cleanup_hitl_state(debate_id: str) -> None:
    """Clean up all HITL state for a completed debate.

    Removes active interrupts, pause state, config, and the interaction
    log for this debate.  Previously the interaction log was kept "for
    history", but without a cap or TTL this caused unbounded memory
    growth in long-running deployments (C-02).
    """
    _active_interrupts.pop(debate_id, None)
    get_workflow_state().clear_hitl_pause(debate_id)
    _hitl_config.pop(debate_id, None)
    _interaction_log.pop(debate_id, None)


def _log_interaction(debate_id: str, interaction: dict) -> None:
    """Append an interaction to the log, capping at ``_MAX_LOG_PER_DEBATE``.

    When the cap is reached the oldest entries are evicted so the
    list never grows beyond the limit.
    """
    if debate_id not in _interaction_log:
        _interaction_log[debate_id] = []
    log = _interaction_log[debate_id]
    log.append(interaction)
    # Evict oldest entries when the cap is exceeded.
    if len(log) > _MAX_LOG_PER_DEBATE:
        del log[: len(log) - _MAX_LOG_PER_DEBATE]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{debate_id}/inject",
    response_model=InjectResponse,
    status_code=201,
)
async def inject_context(
    debate_id: str,
    body: InjectRequest,
    project_id: str = Depends(get_project_id),
) -> InjectResponse:
    """Inject user context into a running debate.

    The injected content will be available to agents in subsequent turns.
    Non-blocking — the debate continues while the injection is queued.
    """
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Debate is not running (current status: {status_val})",
        )

    # Security scan
    scan_result = scan_for_injection(body.content)
    if scan_result.should_block:
        logger.warning(
            "Injection blocked for debate %s: risk=%s, detections=%s",
            debate_id,
            scan_result.risk_level,
            [d["category"] for d in scan_result.detections],
        )
        raise HTTPException(
            status_code=422,
            detail="Content blocked: potential prompt injection detected",
        )

    # Create interaction record
    interaction_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    _log_interaction(
        debate_id,
        {
            "interaction_id": interaction_id,
            "type": "inject",
            "direction": "user_to_agent",
            "source": "user",
            "target": body.target_agent or "all_future",
            "content": body.content,
            "round": body.target_round or 0,
            "agent_index": -1,
            "timestamp": now,
            "status": "pending",
            "metadata": {
                "target_agent": body.target_agent,
                "target_round": body.target_round,
                "priority": body.priority,
                "security_scan": scan_result.to_dict() if scan_result.detections else None,
            },
        },
    )

    # Emit SSE event
    session_id = debate.get("session_id", debate_id)
    await publish_async(
        session_id,
        "hitl_inject",
        {
            "type": "hitl_inject",
            "interaction_id": interaction_id,
            "content": body.content,
            "target_agent": body.target_agent,
            "priority": body.priority,
        },
    )

    # Bridge to workflow interjection_service so agent nodes can consume this injection
    try:
        from backend.workflow.interjection import interjection_service

        await interjection_service.submit(
            session_id=session_id,
            content=body.content,
            source="hitl",
            metadata={
                "interaction_id": interaction_id,
                "debate_id": debate_id,
                "target_agent": body.target_agent,
                "priority": body.priority,
            },
        )
        logger.info(
            "HITL inject bridged to workflow interjection_service: interaction=%s, session=%s, target=%s",
            interaction_id,
            session_id,
            body.target_agent or "all_future",
        )
    except Exception:
        logger.error(
            "Failed to bridge HITL inject %s to workflow interjection_service for session %s",
            interaction_id,
            session_id,
            exc_info=True,
        )

    return InjectResponse(
        interaction_id=interaction_id,
        status="pending",
        target_resolved=body.target_agent or "all_future",
        message="Context injection queued",
    )


@router.post(
    "/{debate_id}/respond",
    response_model=RespondResponse,
)
async def respond_to_query(
    debate_id: str,
    body: RespondRequest,
    project_id: str = Depends(get_project_id),
) -> RespondResponse:
    """Respond to an agent's clarification query.

    Resolves the active interrupt and allows the debate workflow to resume.
    """
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    # Security scan on response
    scan_result = scan_for_injection(body.response)
    if scan_result.should_block:
        logger.warning(
            "Response blocked for debate %s: risk=%s",
            debate_id,
            scan_result.risk_level,
        )
        raise HTTPException(
            status_code=422,
            detail="Response blocked: potential prompt injection detected",
        )

    # Verify the interrupt exists and matches
    interrupt = _active_interrupts.get(debate_id)
    if not interrupt:
        raise HTTPException(
            status_code=409,
            detail="No active interrupt for this debate",
        )
    if interrupt["interrupt_id"] != body.interrupt_id:
        raise HTTPException(
            status_code=404,
            detail=f"Interrupt {body.interrupt_id} not found or already resolved",
        )

    # Resolve the interrupt
    resolved = resolve_interrupt(debate_id, body.response)
    if not resolved:
        raise HTTPException(status_code=500, detail="Failed to resolve interrupt")

    # Emit SSE event
    session_id = debate.get("session_id", debate_id)
    await publish_async(
        session_id,
        "hitl_response",
        {
            "type": "hitl_response",
            "interrupt_id": body.interrupt_id,
            "response": body.response,
            "agent_role": resolved["agent_role"],
        },
    )

    logger.info(
        "Query response delivered: interrupt=%s, debate=%s",
        body.interrupt_id,
        debate_id,
    )

    return RespondResponse(
        interaction_id=str(uuid.uuid4()),
        interrupt_id=body.interrupt_id,
        status="delivered",
        message="Response delivered to agent",
    )


@router.post(
    "/{debate_id}/pause",
    response_model=PauseResponse,
)
async def pause_debate(
    debate_id: str,
    body: PauseRequest,
    project_id: str = Depends(get_project_id),
) -> PauseResponse:
    """Pause or resume a running debate.

    When paused, the workflow will check the pause state at each node
    boundary and wait until resumed.
    """
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Debate is not running (current status: {status_val})",
        )

    now = datetime.now(UTC).isoformat()

    if body.action == "pause":
        get_workflow_state().set_hitl_pause(debate_id, paused_at=now, reason=body.reason)
        message = body.reason or "Debate paused by user"

        # Emit SSE event
        session_id = debate.get("session_id", debate_id)
        await publish_async(
            session_id,
            "hitl_pause",
            {"type": "hitl_pause", "paused": True, "reason": body.reason},
        )

        logger.info("Debate %s paused: %s", debate_id, body.reason or "no reason")
        return PauseResponse(debate_id=debate_id, paused=True, action=body.action, message=message)

    else:  # resume
        get_workflow_state().clear_hitl_pause(debate_id)
        message = "Debate resumed"

        # Emit SSE event
        session_id = debate.get("session_id", debate_id)
        await publish_async(
            session_id,
            "hitl_pause",
            {"type": "hitl_pause", "paused": False, "reason": ""},
        )

        logger.info("Debate %s resumed", debate_id)
        return PauseResponse(debate_id=debate_id, paused=False, action=body.action, message=message)


# ---------------------------------------------------------------------------
# Extension / Extra Rounds endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{debate_id}/extension-request",
    response_model=dict,
)
async def request_extension(
    debate_id: str,
    body: ExtensionRequest,
    project_id: str = Depends(get_project_id),
):
    """Submit an extension request for additional debate rounds.

    Called by the workflow when consensus is not reached and extra rounds
    are enabled. Creates an interrupt that the moderator can respond to.
    """
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    # Verify extension is enabled for this debate
    if not debate.get("enable_extra_rounds", False):
        raise HTTPException(
            status_code=409,
            detail="Extra rounds not enabled for this debate",
        )

    # Check current max rounds to enforce hard cap (max + 2)
    current_max = body.max_rounds
    hard_cap = current_max + 2
    current_round = body.current_round

    if current_round > hard_cap:
        raise HTTPException(
            status_code=409,
            detail=f"Hard round cap ({hard_cap}) exceeded",
        )

    # Store extension request in debate state
    debate["extension_request"] = {
        "current_consensus": body.current_consensus,
        "threshold": body.threshold,
        "current_round": body.current_round,
        "max_rounds": body.max_rounds,
        "requested_at": datetime.now(UTC).isoformat(),
    }
    store.put(debate_id, debate)

    logger.info(
        "Extension requested for debate %s: round %d, consensus=%.3f, threshold=%.3f",
        debate_id,
        body.current_round,
        body.current_consensus,
        body.threshold,
    )

    # Emit SSE event
    session_id = debate.get("session_id", debate_id)
    await publish_async(
        session_id,
        "extension_request",
        {
            "type": "extension_request",
            "debate_id": debate_id,
            "current_consensus": body.current_consensus,
            "threshold": body.threshold,
            "current_round": body.current_round,
            "max_rounds": body.max_rounds,
        },
    )

    return {"status": "pending", "debate_id": debate_id}


@router.post(
    "/{debate_id}/extension-decision",
    response_model=ExtensionResponse,
)
async def extension_decision(
    debate_id: str,
    body: ExtensionDecisionModel,
    project_id: str = Depends(get_project_id),
):
    """Respond to an extension request — grant or deny extra rounds.

    Called by the moderator (or user) to decide whether additional rounds
    should be debated.
    """
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    status = debate.get("status")
    status_val = status.value if hasattr(status, "value") else status
    if status_val != "running":
        raise HTTPException(
            status_code=409,
            detail=f"Debate is not running (current status: {status_val})",
        )

    if not debate.get("enable_extra_rounds", False):
        raise HTTPException(
            status_code=409,
            detail="Extra rounds not enabled for this debate",
        )

    # Validate decision
    decision = body.decision
    if decision not in (ExtensionDecision.GRANTED, ExtensionDecision.DENIED):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid decision: {decision}",
        )

    # Determine new max rounds
    current_max = debate.get("max_rounds", 3)
    current_round = debate.get("current_round", 0)

    if decision == ExtensionDecision.GRANTED:
        new_max = min(current_max + 2, current_round + 2)
        debate["extension_granted"] = True
        message = f"Extension granted. {new_max} total rounds allowed."
    else:
        new_max = current_max
        debate["extension_granted"] = False
        message = "Extension denied. Debate will conclude at current round."

    store.put(debate_id, debate)

    # Emit SSE event and wake the moderator's WaitEvent so it
    # reads the fresh decision immediately.  Sprint 38 (1/3) —
    # ``set_extension_signal`` replaces the 2-second polling
    # latency the moderator had to wait before seeing the
    # decision.  The signal is cross-process via the configured
    # pub/sub backend, so a moderator running on a different
    # worker also unblocks promptly.
    session_id = debate.get("session_id", debate_id)
    await publish_async(
        session_id,
        "extension_decision",
        {
            "type": "extension_decision",
            "debate_id": debate_id,
            "decision": decision.value,
            "new_max_rounds": new_max,
        },
    )
    try:
        from backend.state.workflow_state import get_workflow_state

        get_workflow_state().set_extension_signal(session_id)
    except Exception:
        # The signal is best-effort: if it fails, the moderator
        # still wakes up via the bounded 2 s wait timeout in its
        # loop.  Logged but not raised so the API response
        # remains unaffected.
        logger.warning(
            "Failed to fire extension signal for session %s",
            session_id,
            exc_info=True,
        )

    logger.info(
        "Extension decision for debate %s: %s (new_max=%d)",
        debate_id,
        decision.value,
        new_max,
    )

    return ExtensionResponse(
        decision=decision,
        debate_id=debate_id,
        new_max_rounds=new_max,
        message=message,
    )


@router.get(
    "/{debate_id}/hitl/status",
    response_model=HITLStatusResponse,
)
async def get_hitl_status(
    debate_id: str,
    project_id: str = Depends(get_project_id),
) -> HITLStatusResponse:
    """Get the current HITL status for a debate."""
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    config = get_hitl_config(debate_id)
    interactions = _interaction_log.get(debate_id, [])
    interrupt = _active_interrupts.get(debate_id)

    # Count interactions by type
    by_type: dict[str, int] = {}
    for i in interactions:
        t = i.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    # Build interrupt info
    interrupt_info = None
    if interrupt:
        created = datetime.fromisoformat(interrupt["created_at"])
        elapsed = (datetime.now(UTC) - created).total_seconds()
        interrupt_info = InterruptInfo(
            interrupt_id=interrupt["interrupt_id"],
            agent_role=interrupt["agent_role"],
            question=interrupt["question"],
            context=interrupt.get("context", ""),
            round=interrupt["round"],
            created_at=interrupt["created_at"],
            timeout_seconds=interrupt["timeout_seconds"],
            status=InterruptStatus(interrupt["status"]),
            elapsed_seconds=elapsed,
        )

    # Count interrupts in current round
    current_round = debate.get("current_round", 0)
    round_count = sum(1 for i in interactions if i.get("type") == "query" and i.get("round") == current_round)

    return HITLStatusResponse(
        debate_id=debate_id,
        hitl_enabled=config.get("hitl_enabled", True),
        hitl_mode=HITLMode(config.get("hitl_mode", "full")),
        is_paused=is_paused(debate_id),
        active_interrupt=interrupt_info,
        total_interactions=len(interactions),
        interactions_by_type=by_type,
        round_interrupt_count=round_count,
        max_interrupts_per_round=config.get("max_interrupts_per_round", 3),
    )


@router.get(
    "/{debate_id}/interactions",
    response_model=InteractionListResponse,
)
async def list_interactions(
    debate_id: str,
    offset: int = 0,
    limit: int = 50,
    interaction_type: str | None = None,
    project_id: str = Depends(get_project_id),
) -> InteractionListResponse:
    """Get interaction history for a debate (paginated)."""
    store = get_debate_store_for_case(project_id)
    debate = store.get(debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="Debate not found")

    interactions = _interaction_log.get(debate_id, [])

    # Filter by type if specified
    if interaction_type:
        interactions = [i for i in interactions if i.get("type") == interaction_type]

    total = len(interactions)
    page = interactions[offset : offset + limit]

    items = [
        InteractionResponse(
            interaction_id=i["interaction_id"],
            type=InteractionType(i["type"]),
            direction=InteractionDirection(i["direction"]),
            source=i["source"],
            target=i["target"],
            content=i["content"],
            round=i["round"],
            agent_index=i["agent_index"],
            timestamp=i["timestamp"],
            status=InteractionStatus(i["status"]),
            metadata=i.get("metadata", {}),
        )
        for i in page
    ]

    return InteractionListResponse(
        interactions=items,
        total=total,
        offset=offset,
        limit=limit,
    )
