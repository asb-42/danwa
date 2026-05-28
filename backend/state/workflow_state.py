"""Workflow state store — Redis-backed or in-memory fallback.

Provides a unified API for workflow pause/resume/cancel/status that works
both with Redis (multi-process) and without (single-process in-memory).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class WorkflowStateBackend(Protocol):
    """Interface for workflow state operations."""

    def get_status(self, session_id: str) -> str: ...
    def set_status(self, session_id: str, status: str) -> None: ...
    def is_cancelled(self, session_id: str) -> bool: ...
    def cancel(self, session_id: str) -> None: ...
    def clear_cancel(self, session_id: str) -> None: ...
    def is_paused(self, session_id: str) -> bool: ...
    def pause(self, session_id: str) -> None: ...
    def resume(self, session_id: str) -> None: ...
    def cleanup(self, session_id: str) -> None: ...


class InMemoryWorkflowState:
    """In-memory workflow state — single-process only."""

    def __init__(self):
        self._status: dict[str, str] = {}
        self._cancelled: set[str] = set()
        self._pause_events: dict[str, asyncio.Event] = {}

    def get_status(self, session_id: str) -> str:
        return self._status.get(session_id, "unknown")

    def set_status(self, session_id: str, status: str) -> None:
        self._status[session_id] = status

    def is_cancelled(self, session_id: str) -> bool:
        return session_id in self._cancelled

    def cancel(self, session_id: str) -> None:
        self._cancelled.add(session_id)
        self._status[session_id] = "cancelled"

    def clear_cancel(self, session_id: str) -> None:
        self._cancelled.discard(session_id)

    def is_paused(self, session_id: str) -> bool:
        event = self._pause_events.get(session_id)
        if event is None:
            return False
        return not event.is_set()

    def pause(self, session_id: str) -> None:
        if session_id not in self._pause_events:
            self._pause_events[session_id] = asyncio.Event()
            self._pause_events[session_id].set()
        self._pause_events[session_id].clear()
        self._status[session_id] = "paused"

    def resume(self, session_id: str) -> None:
        if session_id not in self._pause_events:
            self._pause_events[session_id] = asyncio.Event()
        self._pause_events[session_id].set()
        self._status[session_id] = "running"

    def get_pause_event(self, session_id: str) -> asyncio.Event:
        if session_id not in self._pause_events:
            self._pause_events[session_id] = asyncio.Event()
            self._pause_events[session_id].set()
        return self._pause_events[session_id]

    def cleanup(self, session_id: str) -> None:
        self._status.pop(session_id, None)
        self._cancelled.discard(session_id)
        self._pause_events.pop(session_id, None)


class RedisWorkflowState:
    """Redis-backed workflow state — multi-process safe.

    Requires redis package and a configured redis_url.
    """

    def __init__(self, redis_url: str):
        import redis

        self.redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = "danwa:wf:"
        logger.info("RedisWorkflowState connected to %s", redis_url)

    def _key(self, session_id: str, suffix: str) -> str:
        return f"{self._prefix}{suffix}:{session_id}"

    def get_status(self, session_id: str) -> str:
        val = self.redis.get(self._key(session_id, "status"))
        return val or "unknown"

    def set_status(self, session_id: str, status: str) -> None:
        self.redis.setex(self._key(session_id, "status"), 3600, status)

    def is_cancelled(self, session_id: str) -> bool:
        return self.redis.exists(self._key(session_id, "cancelled")) == 1

    def cancel(self, session_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self._key(session_id, "cancelled"), "1")
        pipe.setex(self._key(session_id, "status"), 3600, "cancelled")
        pipe.execute()

    def clear_cancel(self, session_id: str) -> None:
        self.redis.delete(self._key(session_id, "cancelled"))

    def is_paused(self, session_id: str) -> bool:
        return self.redis.exists(self._key(session_id, "paused")) == 1

    def pause(self, session_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.set(self._key(session_id, "paused"), "1")
        pipe.setex(self._key(session_id, "status"), 3600, "paused")
        pipe.execute()

    def resume(self, session_id: str) -> None:
        pipe = self.redis.pipeline()
        pipe.delete(self._key(session_id, "paused"))
        pipe.setex(self._key(session_id, "status"), 3600, "running")
        pipe.execute()

    def cleanup(self, session_id: str) -> None:
        self.redis.delete(
            self._key(session_id, "status"),
            self._key(session_id, "cancelled"),
            self._key(session_id, "paused"),
        )


def get_workflow_state() -> InMemoryWorkflowState | RedisWorkflowState:
    """Get the appropriate workflow state backend based on configuration.

    Returns RedisWorkflowState if redis_url is configured, otherwise
    InMemoryWorkflowState.
    """
    from backend.core.config import settings

    if settings.redis_url:
        try:
            return RedisWorkflowState(settings.redis_url)
        except Exception as e:
            logger.warning("Redis unavailable (%s), falling back to in-memory state", e)

    return InMemoryWorkflowState()
