"""LLM Activity Tracker — lightweight singleton for monitoring LLM call traffic.

Tracks active and recent LLM calls so the frontend header can display
real-time status (model, tokens, duration) and warn about runaway usage.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class LLMCall:
    """A single LLM call record."""

    call_id: str
    model: str
    provider: str
    started_at: float
    finished_at: float | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    status: str = "running"  # "running" | "completed" | "failed"
    error: str = ""
    context: str = ""  # e.g. "Debate", "Translate", "TTS"


class LLMActivityTracker:
    """Global singleton that tracks LLM call activity.

    Thread-safe via ``asyncio.Lock`` so it can be reported from
    async LLM service calls and polled from API endpoints concurrently.
    """

    def __init__(self) -> None:
        """Initialise LLMActivityTracker."""
        self._lock = asyncio.Lock()
        self._active: dict[str, LLMCall] = {}  # call_id → LLMCall
        self._recent: list[LLMCall] = []  # last N completed calls
        self._max_recent: int = 50
        self._call_counter: int = 0
        self._session_totals: dict[str, int] = {}  # session_id → total_tokens

    async def start_call(
        self,
        model: str,
        provider: str = "",
        session_id: str = "",
        context: str = "",
    ) -> str:
        """Record the start of an LLM call.

        Args:
            model: Model name.
            provider: Provider identifier.
            session_id: Optional session ID for token tracking.
            context: What this call is for (e.g. "Debate", "Translate", "TTS").

        Returns:
            A unique call_id for this invocation.
        """
        async with self._lock:
            self._call_counter += 1
            call_id = f"llm-{self._call_counter}"
            call = LLMCall(
                call_id=call_id,
                model=model,
                provider=provider,
                started_at=time.monotonic(),
                context=context,
            )
            self._active[call_id] = call
            if session_id:
                self._session_totals.setdefault(session_id, 0)
        return call_id

    async def end_call(
        self,
        call_id: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        status: str = "completed",
        error: str = "",
        session_id: str = "",
    ) -> None:
        """Record the end of an LLM call."""
        async with self._lock:
            call = self._active.pop(call_id, None)
            if not call:
                return
            call.finished_at = time.monotonic()
            call.duration_ms = int((call.finished_at - call.started_at) * 1000)
            call.tokens_in = tokens_in
            call.tokens_out = tokens_out
            call.status = status
            call.error = error

            # Update session totals
            if session_id:
                self._session_totals[session_id] = self._session_totals.get(session_id, 0) + tokens_in + tokens_out

            # Keep in recent list (bounded)
            self._recent.append(call)
            if len(self._recent) > self._max_recent:
                self._recent = self._recent[-self._max_recent :]

    async def get_status(self) -> dict[str, Any]:
        """Get current activity status for the frontend header."""
        async with self._lock:
            active_calls = list(self._active.values())
            recent_calls = self._recent[-10:]  # Last 10 completed

            # Calculate totals
            total_tokens_all = sum(t for t in self._session_totals.values())

            # Build active call summaries
            active_summaries = []
            for call in active_calls:
                elapsed_s = time.monotonic() - call.started_at
                active_summaries.append(
                    {
                        "call_id": call.call_id,
                        "model": call.model,
                        "provider": call.provider,
                        "context": call.context,
                        "elapsed_s": round(elapsed_s, 1),
                    }
                )

            # Build recent call summaries
            recent_summaries = []
            for call in recent_calls:
                recent_summaries.append(
                    {
                        "call_id": call.call_id,
                        "model": call.model,
                        "provider": call.provider,
                        "tokens_in": call.tokens_in,
                        "tokens_out": call.tokens_out,
                        "duration_ms": call.duration_ms,
                        "status": call.status,
                        "error": call.error[:200] if call.error else "",
                    }
                )

            return {
                "active_count": len(active_calls),
                "active": active_summaries,
                "recent": recent_summaries,
                "total_tokens_all_sessions": total_tokens_all,
                "session_totals": dict(self._session_totals),
            }

    async def clear_session(self, session_id: str) -> None:
        """Clear session token tracking (e.g. after debate completes)."""
        async with self._lock:
            self._session_totals.pop(session_id, None)


# Module-level singleton
llm_activity = LLMActivityTracker()
