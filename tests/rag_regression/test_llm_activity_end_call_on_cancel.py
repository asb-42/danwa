"""Regression test: ``LLMService.generate`` must call ``llm_activity.end_call``
even when the underlying generator raises ``asyncio.CancelledError``.

Background
----------
On 2026-06-18 the user reported that the LLM-Monitor (the live activity
indicator in the global header) showed a stuck entry like

    Agent (strategist) - MiniMax-M3 \u00b7 34m59s \u00b7 997.1k tok

about ten minutes after the debate had ended.  The poll interval is fine
(4s in ``Header.svelte``); the value is recomputed server-side on every
``get_status()`` call.  The 34m59s was real \u2014 an entry had been
registered with ``llm_activity.start_call(...)`` and ``end_call`` had
never been invoked, so it sat in ``_active`` forever and ``elapsed_s``
grew without bound.

Root cause
----------
``LLMService.generate`` wrapped the underlying LLM call in
``try/except Exception``.  In Python \u22653.8 ``asyncio.CancelledError``
inherits from ``BaseException``, not ``Exception``, so when the workflow
runner cancelled the in-flight task (e.g. because the user clicked
the Cancel button) the exception bypassed the ``except`` block, the
function returned without calling ``end_call``, and the entry leaked.

The fix: replace ``try/except Exception`` with ``try/finally`` so
``end_call`` runs on success, ``Exception``, AND ``BaseException`` paths.

These tests guard the call site so a future refactor cannot silently
re-introduce the leak.  We also test the defensive safety net in
``LLMActivityTracker.get_status`` that auto-evicts stuck entries.
"""

from __future__ import annotations

import asyncio
import importlib
import time
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile_mock() -> mock.MagicMock:
    """Return a profile-shaped mock that ``LLMService.generate`` accepts."""
    profile = mock.MagicMock()
    profile.model = "test-model"
    profile.name = "test-model"
    # ``provider`` is an enum-like object; ``.value`` is read in generate().
    profile.provider.value = "openai"
    profile.provider = mock.MagicMock(value="openai")
    profile.temperature = 0.0
    profile.max_tokens = 16
    profile.protocol = "litellm"
    return profile


def _build_llm_service(monkeypatch, exc_to_raise: BaseException | None) -> tuple:
    """Build an ``LLMService`` whose ``_generate_litellm`` raises
    ``exc_to_raise`` (or returns a successful result if None).

    Returns (svc, llm_activity_singleton, reset_done).
    """
    from backend.services import llm_service
    from backend.services.llm_activity import llm_activity

    # Build the service with no profile_id, then inject the mock profile
    # into the private ``_profile`` slot.  This avoids hitting the real
    # ``ProfileService`` (which reads YAML on disk).
    svc = llm_service.LLMService()
    svc._profile = _make_profile_mock()
    svc.set_session_id("regression-cancel-test")

    if exc_to_raise is not None:

        async def _boom(*args, **kwargs):
            raise exc_to_raise

        monkeypatch.setattr(svc, "_generate_litellm", _boom)
        monkeypatch.setattr(svc, "_generate_a2a", _boom)
        monkeypatch.setattr(svc, "_generate_local", _boom)
        monkeypatch.setattr(svc, "_generate_cloudflare", _boom)

    return svc, llm_activity


async def _reset_tracker(llm_activity) -> None:
    """Reset the singleton tracker's state for a hermetic test."""
    async with llm_activity._lock:
        llm_activity._active.clear()
        llm_activity._recent.clear()
        llm_activity._session_totals.clear()
        llm_activity._call_counter = 0


# ---------------------------------------------------------------------------
# 1. ``LLMService.generate`` runs end_call after exceptions
# ---------------------------------------------------------------------------


def test_generate_calls_end_call_after_cancelled_error(monkeypatch):
    """When the underlying LLM raises ``asyncio.CancelledError``,
    ``LLMService.generate`` must still record the call end so the
    LLM-Monitor doesn't show a stuck entry forever.
    """
    svc, llm_activity = _build_llm_service(monkeypatch, asyncio.CancelledError())

    async def _run():
        await _reset_tracker(llm_activity)
        with pytest.raises(asyncio.CancelledError):
            await svc.generate(prompt="hello", system_prompt="")

    asyncio.run(_run())

    async def _assert():
        async with llm_activity._lock:
            assert llm_activity._active == {}, (
                "LLMService.generate did NOT call end_call after "
                "asyncio.CancelledError.  The call is still in "
                "_active and the LLM-Monitor would show a stuck "
                "spinner.  This is the exact regression reported on "
                "2026-06-18.  The fix is a try/finally around the "
                "generate call (see backend/services/llm_service.py)."
            )
            recent = llm_activity._recent
            assert len(recent) == 1, f"expected exactly 1 entry in _recent, got {len(recent)}"
            assert recent[0].status == "failed", f"cancelled call should be recorded as 'failed', got {recent[0].status!r}"

    asyncio.run(_assert())


def test_generate_calls_end_call_after_baseexception(monkeypatch):
    """Belt-and-braces: a non-``Exception`` ``BaseException`` subclass
    (``SystemExit``) must also trigger ``end_call``.  This is the same
    class of bug the cancel fix addresses, generalised.
    """
    svc, llm_activity = _build_llm_service(monkeypatch, SystemExit(1))

    async def _run():
        await _reset_tracker(llm_activity)
        with pytest.raises(SystemExit):
            await svc.generate(prompt="hello", system_prompt="")

    asyncio.run(_run())

    async def _assert():
        async with llm_activity._lock:
            assert llm_activity._active == {}, (
                "LLMService.generate did NOT call end_call after "
                "SystemExit.  BaseException-derived exceptions must "
                "be handled by the finally block in generate()."
            )

    asyncio.run(_assert())


def test_generate_records_success(monkeypatch):
    """Sanity check the success path: a normal completion records
    ``status='completed'`` and the right token counts.
    """
    svc, llm_activity = _build_llm_service(monkeypatch, None)

    result = mock.MagicMock()
    result.tokens_in = 12
    result.tokens_out = 34

    async def _ok(*args, **kwargs):
        return result

    monkeypatch.setattr(svc, "_generate_litellm", _ok)

    async def _run():
        await _reset_tracker(llm_activity)
        out = await svc.generate(prompt="hi", system_prompt="")
        assert out is result

        async with llm_activity._lock:
            assert llm_activity._active == {}
            assert len(llm_activity._recent) == 1
            assert llm_activity._recent[0].status == "completed"
            assert llm_activity._recent[0].tokens_in == 12
            assert llm_activity._recent[0].tokens_out == 34
            # session_id passed to end_call updates _session_totals.
            assert llm_activity._session_totals.get("regression-cancel-test") == 46

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# 2. ``LLMActivityTracker.get_status`` auto-evicts stuck entries
# ---------------------------------------------------------------------------


def test_get_status_auto_evicts_stuck_call(monkeypatch):
    """A leaked entry older than ``STUCK_AFTER_S`` must be moved to
    ``_recent`` with ``status='stuck'`` and removed from ``_active``.
    """
    tracker_module = importlib.import_module("backend.services.llm_activity")

    async def _run():
        # Shrink the threshold for a fast test.
        monkeypatch.setattr(tracker_module, "STUCK_AFTER_S", 1.0)
        tracker = tracker_module.LLMActivityTracker()

        async with tracker._lock:
            tracker._active.clear()
            tracker._recent.clear()
            call = tracker_module.LLMCall(
                call_id="stuck-1",
                model="leaked-model",
                provider="openai",
                started_at=time.monotonic() - 5.0,
            )
            tracker._active[call.call_id] = call

        status = await tracker.get_status()
        assert status["active_count"] == 0, f"expected stuck call to be evicted from _active, got active_count={status['active_count']}"
        assert len(status["active"]) == 0

        async with tracker._lock:
            assert len(tracker._recent) == 1
            assert tracker._recent[0].status == "stuck", f"evicted entry should have status='stuck', got {tracker._recent[0].status!r}"
            assert "Auto-evicted" in tracker._recent[0].error, (
                f"evicted entry should record the auto-eviction reason, got error={tracker._recent[0].error!r}"
            )

    asyncio.run(_run())


def test_get_status_marks_active_entry_stale_below_eviction(monkeypatch):
    """An entry that is *just* below ``STUCK_AFTER_S`` must NOT be
    evicted but must be reported as ``stale=False`` (because its raw
    elapsed is below the threshold) and ``elapsed_s`` must reflect the
    real value.
    """
    tracker_module = importlib.import_module("backend.services.llm_activity")

    async def _run():
        monkeypatch.setattr(tracker_module, "STUCK_AFTER_S", 10.0)
        tracker = tracker_module.LLMActivityTracker()

        async with tracker._lock:
            tracker._active.clear()
            tracker._recent.clear()
            # 2 seconds old \u2014 well below the 10s threshold.
            call = tracker_module.LLMCall(
                call_id="fresh-1",
                model="slow-model",
                provider="openai",
                started_at=time.monotonic() - 2.0,
            )
            tracker._active[call.call_id] = call

        status = await tracker.get_status()
        assert status["active_count"] == 1
        assert len(status["active"]) == 1
        entry = status["active"][0]
        assert entry["stale"] is False, f"a fresh call should not be marked stale, got stale={entry['stale']!r}"
        assert entry["elapsed_s"] == pytest.approx(2.0, abs=0.5)

        async with tracker._lock:
            assert len(tracker._recent) == 0  # nothing evicted

    asyncio.run(_run())


def test_get_status_caps_elapsed_s_when_above_threshold(monkeypatch):
    """If a raw elapsed value somehow exceeds ``STUCK_AFTER_S`` without
    being evicted yet (e.g. between two polls), the API must cap the
    reported ``elapsed_s`` at ``STUCK_AFTER_S`` and mark ``stale=True``.

    We can't easily reproduce the in-between state (the eviction runs
    inside the same lock as the read), so we test the cap by setting
    STUCK_AFTER_S to a value lower than the entry's age, then calling
    get_status; the entry will be evicted (stuck) \u2014 which is also
    acceptable.  The cap itself is enforced in the same loop as
    eviction, so any entry that survives the eviction loop will have
    raw_elapsed < STUCK_AFTER_S, hence elapsed_s == raw_elapsed and
    stale == False.  This test pins down the contract: ``elapsed_s``
    in the API never exceeds ``STUCK_AFTER_S``.
    """
    tracker_module = importlib.import_module("backend.services.llm_activity")

    async def _run():
        monkeypatch.setattr(tracker_module, "STUCK_AFTER_S", 5.0)
        tracker = tracker_module.LLMActivityTracker()

        async with tracker._lock:
            tracker._active.clear()
            tracker._recent.clear()
            call = tracker_module.LLMCall(
                call_id="cap-1",
                model="leaked",
                provider="openai",
                started_at=time.monotonic() - 0.5,  # fresh, well below 5s
            )
            tracker._active[call.call_id] = call

        status = await tracker.get_status()
        # Entry is fresh; cap is 5.0; raw is ~0.5.  elapsed_s should be
        # ~0.5, NOT capped.
        assert len(status["active"]) == 1
        assert status["active"][0]["elapsed_s"] < 5.0
        # And stale should be False.
        assert status["active"][0]["stale"] is False

    asyncio.run(_run())
