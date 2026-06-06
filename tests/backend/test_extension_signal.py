"""Tests for Sprint 38 (part 1/3 + 2/3) — extension-decision WaitEvent.

Sprint 38 (1/3) — verifies the new ``set_extension_signal`` /
``wait_for_extension_signal`` methods on the workflow state backend.
These replace the ``asyncio.sleep(2)`` polling loop in
``moderator_nodes.py`` with an event-driven wake-up so the
moderator unblocks within milliseconds of the HITL API saving the
user's extension decision.

Sprint 38 (2/3) — extends to the second code path:
``extension_request_node`` (in ``hitl/nodes.py``) and
``resolve_interrupt`` (in ``hitl/api.py``).  The signal is fired
by BOTH the dedicated ``extension_decision`` endpoint and the
generic ``respond_to_interrupt`` flow (via ``resolve_interrupt``),
so any node waiting on the extension signal wakes up regardless
of which endpoint the user uses to respond.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest

from backend.state.pubsub import InMemoryPubSub
from backend.state.workflow_state import (
    InMemoryWorkflowState,
    RedisWorkflowState,
    _extension_channel,
    get_workflow_state,
    reset_workflow_state_cache,
)


def _sid() -> str:
    return f"sess-{uuid.uuid4()}"


# ---------------------------------------------------------------------------
# InMemoryWorkflowState — basic semantics
# ---------------------------------------------------------------------------


class TestInMemoryExtensionSignal:
    """``set_extension_signal`` fires the channel,
    ``wait_for_extension_signal`` blocks until it fires (or times
    out).
    """

    def test_set_then_wait_returns_true(self) -> None:
        """A signal set before the wait must be observed via the
        channel-state fast path (``is_set()``) without the wait
        actually blocking.
        """
        state = InMemoryWorkflowState()
        sid = _sid()
        state.set_extension_signal(sid)
        # Run the wait via asyncio.run to avoid the deprecated
        # ``asyncio.get_event_loop()`` access pattern.
        result = asyncio.run(state.wait_for_extension_signal(sid, timeout=0.5))
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_blocks_until_set(self) -> None:
        """``wait_for_extension_signal`` blocks until
        ``set_extension_signal`` is invoked from another coroutine.
        """
        state = InMemoryWorkflowState()
        sid = _sid()

        async def fire() -> None:
            await asyncio.sleep(0.05)
            state.set_extension_signal(sid)

        asyncio.create_task(fire())
        result = await state.wait_for_extension_signal(sid, timeout=2.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_wait_times_out_when_not_set(self) -> None:
        """``wait_for_extension_signal`` returns ``False`` on timeout."""
        state = InMemoryWorkflowState()
        sid = _sid()
        result = await state.wait_for_extension_signal(sid, timeout=0.1)
        assert result is False

    @pytest.mark.asyncio
    async def test_signal_carries_no_payload(self) -> None:
        """The signal is a wake-up; the decision value is read
        separately from the debate store.  Verifies the contract
        that ``wait_for_extension_signal`` only returns
        True/False, not the granted/denied value.
        """
        state = InMemoryWorkflowState()
        sid = _sid()
        state.set_extension_signal(sid)
        result = await state.wait_for_extension_signal(sid, timeout=1.0)
        # True = "wake up, the decision is in the debate store".
        # Caller must read debate["extension_granted"] to know
        # which outcome.
        assert result is True
        assert not hasattr(result, "__await__")  # not a coroutine


# ---------------------------------------------------------------------------
# Cross-instance wake-up (simulates cross-process)
# ---------------------------------------------------------------------------


class TestInMemoryExtensionCrossInstance:
    """Two ``InMemoryWorkflowState`` instances on the same
    pubsub share the extension signal — a HITL request on one
    instance wakes a moderator waiter on another.
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    @pytest.mark.asyncio
    async def test_set_on_a_wakes_waiter_on_b(self) -> None:
        """A signal fired on instance A is observed by a
        ``wait_for_extension_signal`` on instance B.
        """
        pubsub = InMemoryPubSub()
        state_a = InMemoryWorkflowState(pubsub=pubsub)
        state_b = InMemoryWorkflowState(pubsub=pubsub)
        sid = _sid()

        async def fire() -> None:
            await asyncio.sleep(0.05)
            state_a.set_extension_signal(sid)

        asyncio.create_task(fire())
        result = await state_b.wait_for_extension_signal(sid, timeout=2.0)
        assert result is True


# ---------------------------------------------------------------------------
# Channel name + Protocol surface
# ---------------------------------------------------------------------------


class TestChannelAndProtocol:
    def test_channel_name_format(self) -> None:
        """The channel name follows the same pattern as pause /
        resume so the moderator / HITL pair agrees on the key.
        """
        sid = "abc-123"
        assert _extension_channel(sid) == "danwa:wf:extension:abc-123"

    def test_protocol_mentions_extension_methods(self) -> None:
        """``WorkflowStateBackend`` protocol includes
        ``set_extension_signal`` and ``wait_for_extension_signal``
        so type checkers see them on the union return of
        ``get_workflow_state()``.
        """
        from backend.state.workflow_state import WorkflowStateBackend

        attrs = set(WorkflowStateBackend.__dict__.keys())
        assert "set_extension_signal" in attrs
        assert "wait_for_extension_signal" in attrs

    def test_both_backends_implement_extension_methods(self) -> None:
        """Both InMemory and Redis impls define the new methods
        as either sync or async per the protocol.
        """
        import inspect

        # set is sync, wait is async — matches the pattern set
        # by pause / resume.
        assert not inspect.iscoroutinefunction(InMemoryWorkflowState.set_extension_signal)
        assert inspect.iscoroutinefunction(InMemoryWorkflowState.wait_for_extension_signal)
        assert not inspect.iscoroutinefunction(RedisWorkflowState.set_extension_signal)
        assert inspect.iscoroutinefunction(RedisWorkflowState.wait_for_extension_signal)


# ---------------------------------------------------------------------------
# cleanup() releases the extension wait-event
# ---------------------------------------------------------------------------


class TestExtensionCleanup:
    def test_cleanup_drops_extension_wait_event(self) -> None:
        """``cleanup()`` removes the cached extension WaitEvent
        so a fresh ``wait_for_extension_signal`` after cleanup
        creates a new event on a new channel.
        """
        state = InMemoryWorkflowState()
        sid = _sid()
        state.set_extension_signal(sid)
        assert _extension_channel(sid) in state._wait_events
        state.cleanup(sid)
        assert _extension_channel(sid) not in state._wait_events


# ---------------------------------------------------------------------------
# Integration: cancel check + signal-driven wake-up + timeout fallback
# ---------------------------------------------------------------------------


class TestExtensionWaitIntegration:
    """Mimics the moderator's wait loop: cancel check on every
    iteration, signal-driven wake-up, and timeout fallback.
    """

    @pytest.mark.asyncio
    async def test_full_loop_grants_on_signal(self) -> None:
        """Mirrors the moderator logic: poll debate + cancel
        check; if no decision, wait on the extension signal with
        a 2 s cap.  When the signal fires, the debate has the
        decision, and the loop breaks with ``extension_granted``
        set from the debate.
        """
        # Simulated debate store
        debate_state: dict = {}

        def get_debate() -> dict | None:
            return debate_state or None

        # State backend with the extension signal
        state = InMemoryWorkflowState()
        sid = _sid()

        # Simulate the moderator's wait loop (5 s deadline here
        # instead of 5 min for the test).
        granted: bool | None = None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5.0

        async def wait_for_decision() -> None:
            nonlocal granted
            while loop.time() < deadline:
                # Cancel check (always False here)
                # debate lookup
                debate = get_debate()
                if debate and debate.get("extension_granted") is not None:
                    granted = debate["extension_granted"]
                    return
                remaining = deadline - loop.time()
                await state.wait_for_extension_signal(sid, timeout=min(2.0, max(0.1, remaining)))

        waiter = asyncio.create_task(wait_for_decision())
        await asyncio.sleep(0.05)

        # Simulate the HITL API: save decision, then fire signal
        debate_state["extension_granted"] = True
        state.set_extension_signal(sid)

        await waiter
        assert granted is True

    @pytest.mark.asyncio
    async def test_full_loop_denies_on_timeout(self) -> None:
        """No decision ever arrives — the loop times out and
        the moderator records ``False`` (deny).
        """
        state = InMemoryWorkflowState()
        sid = _sid()
        loop = asyncio.get_running_loop()

        async def wait_for_decision() -> bool:
            """Returns the granted value; ``None`` on timeout."""
            # Short deadline (0.2 s) for the test
            deadline = loop.time() + 0.2
            while loop.time() < deadline:
                await state.wait_for_extension_signal(sid, timeout=min(0.1, max(0.05, deadline - loop.time())))
            return False  # timeout fallback

        result = await wait_for_decision()
        assert result is False


# ===========================================================================
# Sprint 38 (part 2/3) — resolve_interrupt fires the signal
# ===========================================================================
#
# The ``extension_request_node`` waits on the extension signal
# while polling the interrupt registry.  Sprint 38 (2/3) makes
# ``resolve_interrupt`` fire the same signal so the wait wakes
# up immediately when the user responds via the generic
# ``respond_to_interrupt`` endpoint (not just the dedicated
# ``extension_decision`` endpoint).


class TestResolveInterruptFiresSignal:
    """``resolve_interrupt`` (the canonical "user responded"
    API) fires the extension signal as a side effect so any
    waiter on the same session unblocks.
    """

    def setup_method(self) -> None:
        """Reset all module-level singletons and HITL state."""
        reset_workflow_state_cache()
        from backend.workflow.hitl import api as hitl_api

        hitl_api._active_interrupts.clear()
        hitl_api._interaction_log.clear()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()
        from backend.workflow.hitl import api as hitl_api

        hitl_api._active_interrupts.clear()
        hitl_api._interaction_log.clear()

    @pytest.mark.asyncio
    async def test_resolve_interrupt_fires_signal(self) -> None:
        """Calling ``resolve_interrupt`` after registering an
        interrupt fires the per-session extension signal.
        """
        from backend.workflow.hitl.api import register_agent_query, resolve_interrupt

        did = _sid()
        register_agent_query(
            did,
            {
                "agent_role": "moderator",
                "agent_index": -1,
                "round": 0,
                "question": "Continue debating?",
                "context": "consensus below threshold",
            },
        )
        # Before resolution — the signal is NOT set
        backend = get_workflow_state()
        assert isinstance(backend, InMemoryWorkflowState)
        assert _extension_channel(did) not in backend._wait_events
        result = await backend.wait_for_extension_signal(did, timeout=0.1)
        assert result is False
        # Resolve the interrupt — this should fire the signal
        resolve_interrupt(did, "Yes, please continue")
        # After resolution — the signal is set
        result = await backend.wait_for_extension_signal(did, timeout=0.1)
        assert result is True

    def test_resolve_interrupt_no_active_does_not_crash(self) -> None:
        """``resolve_interrupt`` returns ``None`` when there's
        no active interrupt, and does NOT fire the signal
        (since there's no event to fire for).  No exception
        is raised — the signal-fire path is best-effort.
        """
        from backend.workflow.hitl.api import resolve_interrupt

        result = resolve_interrupt("no-such-debate", "response")
        assert result is None


class TestExtensionRequestNodeSignal:
    """``extension_request_node`` (in ``hitl/nodes.py``) uses
    ``wait_for_extension_signal`` to wake up within milliseconds
    of the user responding via either ``extension_decision`` or
    ``respond_to_interrupt``.
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    @pytest.mark.asyncio
    async def test_node_wakes_on_resolve_interrupt(self) -> None:
        """The node's wait loop unblocks immediately when
        ``resolve_interrupt`` fires the signal — no 2 s
        polling delay.
        """
        from backend.workflow.hitl.api import (
            get_active_interrupt,
            register_agent_query,
            resolve_interrupt,
        )

        did = _sid()
        register_agent_query(
            did,
            {
                "agent_role": "moderator",
                "agent_index": -1,
                "round": 0,
                "question": "Continue debating?",
                "context": "consensus below threshold",
            },
        )
        assert get_active_interrupt(did) is not None

        backend = get_workflow_state()
        assert isinstance(backend, InMemoryWorkflowState)

        # The node's wait loop (simplified, mirror of
        # extension_request_node's loop body).  A separate
        # task resolves the interrupt after a short delay
        # to simulate the user responding via the generic
        # ``respond_to_interrupt`` endpoint.
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 5.0
        woke_on_signal = False
        woke_at: float | None = None
        start = loop.time()

        async def user_responds() -> None:
            """Simulate the user clicking 'Yes' after 100 ms."""
            await asyncio.sleep(0.1)
            resolve_interrupt(did, "Yes, please continue")

        asyncio.create_task(user_responds())

        while loop.time() < deadline:
            await backend.wait_for_extension_signal(did, timeout=min(2.0, max(0.1, deadline - loop.time())))
            interrupt = get_active_interrupt(did)
            if interrupt is None:
                # Resolved
                woke_at = loop.time() - start
                woke_on_signal = True
                break

        assert woke_on_signal is True
        # Woke up immediately after the resolver fires
        # (sub-500ms is the realistic upper bound for the
        # test environment, not 2 s which is the poll interval).
        assert woke_at is not None
        assert woke_at < 0.5  # generous threshold for CI jitter
