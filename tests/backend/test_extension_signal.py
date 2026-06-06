"""Tests for Sprint 38 (part 1/3) — extension-decision WaitEvent.

Verifies the new ``set_extension_signal`` / ``wait_for_extension_signal``
methods on the workflow state backend.  These replace the
``asyncio.sleep(2)`` polling loop in ``moderator_nodes.py`` with an
event-driven wake-up so the moderator unblocks within milliseconds
of the HITL API saving the user's extension decision.
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
        result = asyncio.run(
            state.wait_for_extension_signal(sid, timeout=0.5)
        )
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
                await state.wait_for_extension_signal(
                    sid, timeout=min(2.0, max(0.1, remaining))
                )

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
                await state.wait_for_extension_signal(
                    sid, timeout=min(0.1, max(0.05, deadline - loop.time()))
                )
            return False  # timeout fallback

        result = await wait_for_decision()
        assert result is False
