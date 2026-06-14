"""Tests for backend/workflow/workflow_routers.py — gate/feedback routers.

Focus areas (previously uncovered):
* ``route_sequential`` and ``route_after_interjection`` (trivially constant)
* ``route_conditional`` — first-match wins, fallback to last target, empty
  conditions, ``SafeEvalError`` per-condition, generic ``Exception`` per
  condition, all-fail fallback, SSE publish, audit log
* ``_publish_gate_decision`` — best-effort swallowing of publish/audit errors
* ``_get_publish`` — lazy import of the publish_async module
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch

from backend.workflow.workflow_routers import (
    _get_publish,
    _publish_gate_decision,
    route_after_interjection,
    route_conditional,
    route_sequential,
)

# ---------------------------------------------------------------------------
# Simple routers
# ---------------------------------------------------------------------------


class TestSimpleRouters:
    def test_route_sequential_returns_next(self) -> None:
        assert route_sequential({"session_id": "s1"}) == "next"  # type: ignore[arg-type]

    def test_route_after_interjection_returns_next(self) -> None:
        assert route_after_interjection({"session_id": "s1"}) == "next"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _get_publish
# ---------------------------------------------------------------------------


class TestGetPublish:
    def test_lazy_loads_publish_async(self) -> None:
        # Reset the module-level cache
        import backend.workflow.workflow_routers as r

        r._publish_async = None
        with patch("backend.api.events.publish_async", autospec=True) as publish:
            result = _get_publish()
            assert result is publish
            # Second call returns the same cached value
            assert _get_publish() is publish
        # Cleanup
        r._publish_async = None


# ---------------------------------------------------------------------------
# _publish_gate_decision
# ---------------------------------------------------------------------------


class TestPublishGateDecision:
    def setup_method(self) -> None:
        import backend.workflow.workflow_routers as r

        self._r = r
        self._r._publish_async = None

    def teardown_method(self) -> None:
        self._r._publish_async = None

    def test_publishes_sse_and_audits(self) -> None:
        sent: list[tuple[str, str, dict]] = []

        async def fake_publish(sid: str, kind: str, payload: dict) -> None:
            sent.append((sid, kind, payload))

        with (
            patch("backend.api.events.publish_async", side_effect=fake_publish),
            patch("backend.workflow.audit_logger.get_audit_logger") as get_logger,
        ):
            logger = get_logger.return_value
            import asyncio

            asyncio.run(
                _publish_gate_decision(
                    "s1",
                    "g1",
                    "x > 0",
                    True,
                    "approved",
                    False,
                    [],
                    1,
                )
            )
        assert len(sent) == 1
        sid, kind, payload = sent[0]
        assert sid == "s1"
        assert kind == "gate.decision"
        assert payload["gate_node_id"] == "g1"
        assert payload["chosen_target"] == "approved"
        # Audit logger invoked
        logger.log_gate_decision.assert_called_once()

    def test_swallow_sse_publish_error(self, caplog) -> None:
        async def boom(sid: str, kind: str, payload: dict) -> None:
            raise RuntimeError("sse down")

        with (
            patch("backend.api.events.publish_async", side_effect=boom),
            patch("backend.workflow.audit_logger.get_audit_logger"),
        ):
            import asyncio

            with caplog.at_level(logging.DEBUG, logger="backend.workflow.workflow_routers"):
                # Must not raise
                asyncio.run(_publish_gate_decision("s1", "g1", "x>0", True, "ok", False, [], 1))
        assert any("Failed to publish gate.decision" in rec.message for rec in caplog.records)

    def test_swallow_audit_error(self, caplog) -> None:
        async def ok_publish(*a, **k) -> None:
            return None

        def bad_logger():
            raise RuntimeError("audit down")

        with (
            patch("backend.api.events.publish_async", side_effect=ok_publish),
            patch(
                "backend.workflow.audit_logger.get_audit_logger",
                side_effect=bad_logger,
            ),
        ):
            import asyncio

            with caplog.at_level(logging.DEBUG, logger="backend.workflow.workflow_routers"):
                # Must not raise
                asyncio.run(_publish_gate_decision("s1", "g1", "x>0", True, "ok", False, [], 1))
        assert any("Failed to log gate decision" in rec.message for rec in caplog.records)


# ---------------------------------------------------------------------------
# route_conditional — happy path / first-match / fallback
# ---------------------------------------------------------------------------


def _run_router(router, state: dict) -> str:
    """Run an async router synchronously via asyncio.run."""
    import asyncio

    return asyncio.run(router(state))


class TestRouteConditionalFirstMatch:
    def test_returns_first_matching_target(self) -> None:
        router = route_conditional(
            {
                "approve": "score > 0.7",
                "revise": "score > 0.3",
                "reject": "score <= 0.3",
            }
        )
        state = {"session_id": "s1", "current_round": 1, "score": 0.8}
        assert _run_router(router, state) == "approve"

    def test_falls_through_to_second_condition(self) -> None:
        router = route_conditional(
            {
                "approve": "score > 0.9",
                "revise": "score > 0.3",
            }
        )
        state = {"session_id": "s1", "current_round": 2, "score": 0.5}
        assert _run_router(router, state) == "revise"

    def test_falls_back_to_last_target_when_none_match(self) -> None:
        router = route_conditional(
            {
                "approve": "score > 0.9",
                "revise": "score > 0.9",
                "reject": "score > 0.9",
            }
        )
        state = {"session_id": "s1", "current_round": 1, "score": 0.1}
        assert _run_router(router, state) == "reject"


class TestRouteConditionalErrors:
    def test_safe_eval_error_continues_to_next_condition(self) -> None:
        # First condition raises SafeEvalError; second matches
        router = route_conditional(
            {
                "bad": "__import__('os').system('rm -rf /')",  # unsafe → SafeEvalError
                "good": "score > 0.0",
            }
        )
        state = {"session_id": "s1", "current_round": 1, "score": 0.5}
        assert _run_router(router, state) == "good"

    def test_runtime_error_in_condition_continues(self) -> None:
        # First condition raises generic Exception (e.g. NameError)
        router = route_conditional(
            {
                "broken": "undefined_var_xyz > 0",
                "fallback": "score > 0.0",
            }
        )
        state = {"session_id": "s1", "current_round": 1, "score": 0.5}
        assert _run_router(router, state) == "fallback"

    def test_all_conditions_unsafe_falls_back_to_last(self) -> None:
        router = route_conditional(
            {
                "first": "__import__('os')",
                "last": "__import__('os')",
            }
        )
        state = {"session_id": "s1", "current_round": 1, "score": 0.0}
        # No condition matches → fallback to last key
        assert _run_router(router, state) == "last"

    def test_empty_conditions_returns_end(self) -> None:
        router = route_conditional({})
        state = {"session_id": "s1", "current_round": 1}
        assert _run_router(router, state) == "end"


def _patch_publish():
    """Replace _publish_gate_decision with a recorder (module-level helper)."""
    sent: list[dict[str, Any]] = []

    async def fake_publish(*args, **kwargs):
        sent.append({"args": args, "kwargs": kwargs})

    return sent, patch(
        "backend.workflow.workflow_routers._publish_gate_decision",
        side_effect=fake_publish,
    )


class TestRouteConditionalPublishing:
    def test_publishes_decision_on_match(self) -> None:
        sent, patcher = _patch_publish()
        with patcher:
            router = route_conditional({"approve": "score > 0.5"})
            state = {"session_id": "abc", "current_round": 3, "score": 0.9}
            _run_router(router, state)
        assert len(sent) == 1
        args = sent[0]["args"]
        assert args[0] == "abc"
        assert args[1] == ""  # gate_node_id
        assert args[2] == "score > 0.5"
        assert args[3] is True  # result
        assert args[4] == "approve"  # chosen_target
        assert args[5] is False  # fallback_used
        assert args[7] == 3  # current_round

    def test_publishes_fallback_when_no_match(self) -> None:
        sent, patcher = _patch_publish()
        with patcher:
            router = route_conditional(
                {
                    "approve": "score > 0.9",
                    "reject": "score < 0.1",
                }
            )
            state = {"session_id": "abc", "current_round": 2, "score": 0.5}
            _run_router(router, state)
        # Exactly one publish call (for the fallback)
        assert len(sent) == 1
        args = sent[0]["args"]
        assert args[2] == "(none matched)"
        assert args[3] is False
        assert args[4] == "reject"  # fallback to last key
        assert args[5] is True  # fallback_used


class TestRouteConditionalEvaluations:
    def test_safe_eval_error_records_evaluation_with_error(self) -> None:
        sent, patcher = _patch_publish()
        with patcher:
            router = route_conditional(
                {
                    "bad": "__import__('os')",
                    "good": "score > 0",
                }
            )
            state = {"session_id": "s1", "current_round": 1, "score": 0.1}
            _run_router(router, state)
        # Last publish call carries the full evaluations list
        args = sent[0]["args"]
        evals = args[6]
        # The bad condition should have an "error" key
        bad = [e for e in evals if e["target"] == "bad"][0]
        assert "error" in bad
        assert bad["result"] is False
        # The good one was evaluated
        good = [e for e in evals if e["target"] == "good"][0]
        assert good["result"] is True
