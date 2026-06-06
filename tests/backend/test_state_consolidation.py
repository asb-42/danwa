"""Tests for Sprint 37 (part 3/3) — cancel/pause consolidation.

Verifies that ``workflow_runner`` and ``debate_oob`` cancel/pause
helpers delegate to the unified ``get_workflow_state()`` backend.
The state set via one module is visible to the other, and the
state backend owns the canonical truth.

Sprint 38 (part 3/3) — adds the HITL pause storage
(``get_hitl_pause`` / ``set_hitl_pause`` / ``clear_hitl_pause``)
on the same backend.  The previous process-local
``hitl/api.py:_paused_debates`` dict is gone.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from backend.services.debate import debate_oob
from backend.state.workflow_state import (
    InMemoryWorkflowState,
    get_workflow_state,
    reset_workflow_state_cache,
)
from backend.workflow import workflow_runner


def _id() -> str:
    return f"id-{uuid.uuid4()}"


# ---------------------------------------------------------------------------
# Singleton cache discipline (required for the delegation to work)
# ---------------------------------------------------------------------------


class TestSingletonCache:
    """``get_workflow_state()`` must return the same instance per
    process; otherwise the delegated cancel/pause state would be
    lost between calls and the cross-request coordination
    guarantee would silently break.
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    def test_get_workflow_state_is_singleton(self) -> None:
        a = get_workflow_state()
        b = get_workflow_state()
        assert a is b

    def test_state_set_via_runner_visible_via_backend(self) -> None:
        """The consolidation works: state set via the legacy
        module-level helper is visible to the unified backend.
        """
        sid = _id()
        # Direct backend call
        get_workflow_state().cancel(sid)
        # Legacy wrapper sees it
        assert workflow_runner.is_cancelled(sid) is True
        assert workflow_runner.get_session_status(sid) == "cancelled"


# ---------------------------------------------------------------------------
# workflow_runner delegation
# ---------------------------------------------------------------------------


class TestWorkflowRunnerDelegation:
    """``workflow_runner`` cancel/pause helpers delegate to
    ``get_workflow_state()`` instead of carrying their own dicts.
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    def test_is_cancelled_delegates_to_backend(self) -> None:
        sid = _id()
        get_workflow_state().cancel(sid)
        assert workflow_runner.is_cancelled(sid) is True
        get_workflow_state().clear_cancel(sid)
        assert workflow_runner.is_cancelled(sid) is False

    def test_cancel_session_delegates_to_backend(self) -> None:
        sid = _id()
        workflow_runner.cancel_session(sid)
        assert get_workflow_state().is_cancelled(sid) is True
        assert get_workflow_state().get_status(sid) == "cancelled"

    def test_get_and_set_session_status_delegate(self) -> None:
        sid = _id()
        workflow_runner.set_session_status(sid, "running")
        assert workflow_runner.get_session_status(sid) == "running"
        assert get_workflow_state().get_status(sid) == "running"

    def test_get_pause_event_delegates_to_backend(self) -> None:
        """The legacy ``asyncio.Event`` accessor still works; it
        returns the backend's per-session event.
        """
        sid = _id()
        ev = workflow_runner.get_pause_event(sid)
        # Default: not paused (event is set)
        assert ev.is_set() is True
        # Pause via the backend flips the event
        get_workflow_state().pause(sid)
        assert ev.is_set() is False
        # Resume flips it back
        get_workflow_state().resume(sid)
        assert ev.is_set() is True

    def test_pause_session_delegates_and_audits(self) -> None:
        """``pause_session`` updates the backend and writes an
        audit-log entry.  The audit log is the only workflow-
        specific side effect kept in ``workflow_runner`` after the
        Sprint 37 (3/3) consolidation.
        """
        sid = _id()
        with patch("backend.workflow.workflow_runner.get_audit_logger") as mock_audit_factory:
            mock_logger = mock_audit_factory.return_value
            workflow_runner.pause_session(sid)
        # Backend reflects the pause
        assert get_workflow_state().is_paused(sid) is True
        assert get_workflow_state().get_status(sid) == "paused"
        # Audit logger received the event
        mock_logger.log_workflow_event.assert_called_once()
        call = mock_logger.log_workflow_event.call_args
        assert call.kwargs["event_type"] == "workflow_paused"
        assert call.kwargs["actor"] == "user"
        assert call.kwargs["session_id"] == sid

    def test_resume_session_delegates_and_audits(self) -> None:
        sid = _id()
        workflow_runner.pause_session(sid)
        with patch("backend.workflow.workflow_runner.get_audit_logger") as mock_audit_factory:
            mock_logger = mock_audit_factory.return_value
            workflow_runner.resume_session(sid)
        assert get_workflow_state().is_paused(sid) is False
        assert get_workflow_state().get_status(sid) == "running"
        mock_logger.log_workflow_event.assert_called_once()
        call = mock_logger.log_workflow_event.call_args
        assert call.kwargs["event_type"] == "workflow_resumed"

    def test_pause_session_audit_failure_does_not_break_pause(self) -> None:
        """If the audit logger raises, the pause still applies.
        The legacy code swallowed audit failures with a debug
        log; the consolidated version preserves that.
        """
        sid = _id()
        with patch("backend.workflow.workflow_runner.get_audit_logger") as mock_audit_factory:
            mock_audit_factory.return_value.log_workflow_event.side_effect = RuntimeError("audit down")
            workflow_runner.pause_session(sid)  # must not raise
        assert get_workflow_state().is_paused(sid) is True

    def test_module_no_longer_carries_local_state_dicts(self) -> None:
        """Sprint 37 (3/3) removed the module-level
        ``_pause_events`` / ``_cancelled_sessions`` /
        ``_session_status`` dicts.  The state lives on the
        backend now.
        """
        for attr in ("_pause_events", "_cancelled_sessions", "_session_status"):
            assert not hasattr(workflow_runner, attr), f"workflow_runner.{attr} should be gone after consolidation"


# ---------------------------------------------------------------------------
# debate_oob delegation
# ---------------------------------------------------------------------------


class TestDebateOobCancellationDelegation:
    """``debate_oob`` cancellation helpers delegate to
    ``get_workflow_state()``.  The OOB queue itself is unchanged
    (still module-local — different concern, see
    ``debate_oob.py`` docstring).
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    def test_is_cancelled_delegates_to_backend(self) -> None:
        did = _id()
        assert debate_oob.is_cancelled(did) is False
        debate_oob.mark_cancelled(did)
        assert debate_oob.is_cancelled(did) is True
        assert get_workflow_state().is_cancelled(did) is True

    def test_mark_cancelled_delegates_to_backend(self) -> None:
        did = _id()
        debate_oob.mark_cancelled(did)
        assert get_workflow_state().is_cancelled(did) is True

    def test_clear_cancel_delegates_to_backend(self) -> None:
        did = _id()
        debate_oob.mark_cancelled(did)
        debate_oob.clear_cancel(did)
        assert debate_oob.is_cancelled(did) is False
        assert get_workflow_state().is_cancelled(did) is False

    def test_oob_queue_is_still_module_local(self) -> None:
        """The OOB input queue remains in ``debate_oob._oob_queues``;
        consolidating it is a follow-up.
        """
        did = _id()
        debate_oob.enqueue_oob(did, {"oob_id": "x", "status": "pending"})
        pending = debate_oob.get_oob_for_debate(did)
        assert len(pending) == 1
        assert pending[0]["oob_id"] == "x"
        # consume still works
        debate_oob.consume_oob(did, ["x"])
        assert debate_oob.get_oob_for_debate(did) == []
        debate_oob.clear_oob_queue(did)

    def test_module_no_longer_carries_cancelled_set(self) -> None:
        """Sprint 37 (3/3) removed the module-level
        ``_cancelled_debates`` set; cancellation lives on the
        backend now.  The OOB queue dict is kept (different
        concern).
        """
        assert not hasattr(debate_oob, "_cancelled_debates"), "debate_oob._cancelled_debates should be gone after consolidation"
        # The OOB queue dict is intentional
        assert hasattr(debate_oob, "_oob_queues")


# ---------------------------------------------------------------------------
# Cross-module consolidation: one backend, two legacy APIs
# ---------------------------------------------------------------------------


class TestCrossModuleConsolidation:
    """A cancel via ``debate_oob`` is visible to
    ``workflow_runner`` and vice versa.  This is the property the
    consolidation delivers: a single source of truth for cancel /
    pause state.
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    def test_debate_cancel_visible_to_workflow_runner(self) -> None:
        """``debate_oob.mark_cancelled(did)`` makes
        ``workflow_runner.is_cancelled(did)`` return True.
        They share the same backend.
        """
        did = _id()
        debate_oob.mark_cancelled(did)
        assert workflow_runner.is_cancelled(did) is True

    def test_workflow_runner_cancel_visible_to_debate_oob(self) -> None:
        """``workflow_runner.cancel_session(sid)`` makes
        ``debate_oob.is_cancelled(sid)`` return True.
        """
        sid = _id()
        workflow_runner.cancel_session(sid)
        assert debate_oob.is_cancelled(sid) is True

    def test_pause_visible_across_modules(self) -> None:
        """Pause/resume via the runner is visible as a status
        change on the backend, and the workflow-state pause
        signal fires the cross-process wake-up (covered in
        ``test_workflow_state_wait.py``).
        """
        sid = _id()
        workflow_runner.pause_session(sid)
        # The backend status reflects the pause
        assert get_workflow_state().get_status(sid) == "paused"
        # Cross-module is_cancelled still reports False (no cancel
        # happened, just a pause)
        assert debate_oob.is_cancelled(sid) is False


# ---------------------------------------------------------------------------
# Async pause/resume wake-up still works after the refactor
# ---------------------------------------------------------------------------


class TestPauseResumeWaitStillWorks:
    """``wait_for_pause`` / ``wait_for_resume`` keep working when
    invoked through the ``workflow_runner`` legacy API.
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    @pytest.mark.asyncio
    async def test_workflow_runner_pause_wakes_wait_for_pause(self) -> None:
        """A pause issued via the legacy ``workflow_runner`` API
        wakes a ``wait_for_pause`` coroutine subscribed to the
        same session.
        """
        sid = _id()
        backend = get_workflow_state()
        assert isinstance(backend, InMemoryWorkflowState)

        async def pauser() -> None:
            import asyncio

            await asyncio.sleep(0.05)
            workflow_runner.pause_session(sid)

        import asyncio

        asyncio.create_task(pauser())
        result = await backend.wait_for_pause(sid, timeout=2.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_workflow_runner_resume_wakes_wait_for_resume(self) -> None:
        sid = _id()
        backend = get_workflow_state()
        assert isinstance(backend, InMemoryWorkflowState)
        workflow_runner.pause_session(sid)

        async def resumer() -> None:
            import asyncio

            await asyncio.sleep(0.05)
            workflow_runner.resume_session(sid)

        import asyncio

        asyncio.create_task(resumer())
        result = await backend.wait_for_resume(sid, timeout=2.0)
        assert result is True


# ---------------------------------------------------------------------------
# Sprint 38 (3/3) — HITL pause storage on the workflow state backend
# ---------------------------------------------------------------------------


class TestHitlPauseStorage:
    """The HITL ``is_paused(debate_id)`` state (formerly
    ``hitl/api.py:_paused_debates``) is stored on the workflow
    state backend.  ``get_hitl_pause`` returns ``None`` when the
    debate is not paused and a ``{paused_at, reason}`` dict
    when it is; ``set_hitl_pause`` stores the record;
    ``clear_hitl_pause`` removes it (idempotently).
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    def test_get_hitl_pause_default_none(self) -> None:
        backend = get_workflow_state()
        assert backend.get_hitl_pause(_id()) is None

    def test_set_hitl_pause_then_get(self) -> None:
        backend = get_workflow_state()
        did = _id()
        backend.set_hitl_pause(did, paused_at="2024-01-01T00:00:00Z", reason="user request")
        record = backend.get_hitl_pause(did)
        assert record == {
            "paused_at": "2024-01-01T00:00:00Z",
            "reason": "user request",
        }

    def test_set_hitl_pause_reason_may_be_none(self) -> None:
        backend = get_workflow_state()
        did = _id()
        backend.set_hitl_pause(did, paused_at="now", reason=None)
        record = backend.get_hitl_pause(did)
        assert record is not None
        assert record["reason"] is None
        assert record["paused_at"] == "now"

    def test_set_hitl_pause_is_idempotent(self) -> None:
        """A second ``set`` overwrites the prior record (the
        newer timestamp wins, which is the correct semantic for
        repeated pause actions).
        """
        backend = get_workflow_state()
        did = _id()
        backend.set_hitl_pause(did, paused_at="2024-01-01T00:00:00Z", reason="first")
        backend.set_hitl_pause(did, paused_at="2024-01-01T00:01:00Z", reason="second")
        record = backend.get_hitl_pause(did)
        assert record == {
            "paused_at": "2024-01-01T00:01:00Z",
            "reason": "second",
        }

    def test_clear_hitl_pause_removes_record(self) -> None:
        backend = get_workflow_state()
        did = _id()
        backend.set_hitl_pause(did, paused_at="now", reason="x")
        assert backend.get_hitl_pause(did) is not None
        backend.clear_hitl_pause(did)
        assert backend.get_hitl_pause(did) is None

    def test_clear_hitl_pause_is_idempotent(self) -> None:
        """Clearing a non-existent record is a no-op (must not
        raise).  This matches the prior ``_paused_debates.pop(…, None)``
        behavior.
        """
        backend = get_workflow_state()
        backend.clear_hitl_pause(_id())  # should not raise

    def test_get_returns_copy(self) -> None:
        """The dict returned by ``get_hitl_pause`` is a copy,
        so mutating it does not affect the stored record.
        """
        backend = get_workflow_state()
        did = _id()
        backend.set_hitl_pause(did, paused_at="now", reason="orig")
        record = backend.get_hitl_pause(did)
        assert record is not None
        record["reason"] = "mutated"
        # Re-fetch: the stored record is untouched.
        record2 = backend.get_hitl_pause(did)
        assert record2 is not None
        assert record2["reason"] == "orig"

    def test_cross_instance_visibility(self) -> None:
        """Two ``InMemoryWorkflowState`` instances created from
        the same factory share the singleton (verified
        elsewhere), so state set on one is visible on the
        other — no test-only shim needed.
        """
        backend1 = get_workflow_state()
        backend2 = get_workflow_state()
        assert backend1 is backend2
        did = _id()
        backend1.set_hitl_pause(did, paused_at="now", reason="x")
        assert backend2.get_hitl_pause(did) is not None


class TestHitlPauseFromHitlApi:
    """End-to-end: the ``hitl.api.is_paused`` helper delegates
    to the workflow state backend (Sprint 38 3/3 contract).
    """

    def setup_method(self) -> None:
        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        reset_workflow_state_cache()

    def test_is_paused_via_state_backend(self) -> None:
        from backend.workflow.hitl.api import is_paused

        did = _id()
        assert is_paused(did) is False
        get_workflow_state().set_hitl_pause(did, paused_at="now", reason="user")
        assert is_paused(did) is True
        get_workflow_state().clear_hitl_pause(did)
        assert is_paused(did) is False

    def test_no_local_dict_attribute(self) -> None:
        """The ``_paused_debates`` module attribute must be gone
        — the only path for HITL pause state is now through the
        workflow state backend.
        """
        import backend.workflow.hitl.api as hitl_api

        assert not hasattr(hitl_api, "_paused_debates"), (
            "_paused_debates must be removed from hitl/api.py — use get_workflow_state().get_hitl_pause(...) instead"
        )
