"""Interjection service — manages user interjections during workflow execution.

Provides an in-memory, per-session queue for interjections that workflow
nodes can consume at interjection points.  Thread-safe via ``asyncio.Lock``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Interjection:
    """A single interjection item in the queue."""

    interjection_id: str
    session_id: str
    content: str
    source: str  # "user" | "system" | "api"
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"  # "pending" | "consumed"


class InterjectionService:
    """In-memory interjection queue per workflow session.

    Thread-safe via ``asyncio.Lock`` so it can be used from both
    API handlers (async) and workflow node functions (async).
    """

    def __init__(self) -> None:
        # session_id → list of Interjection objects
        self._queues: dict[str, list[Interjection]] = {}
        self._lock = asyncio.Lock()

    async def submit(
        self,
        session_id: str,
        content: str,
        source: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Add an interjection to the queue for a session.

        Args:
            session_id: The workflow session ID.
            content: The interjection text content.
            source: Origin of the interjection ("user", "system", "api").
            metadata: Optional metadata dict.

        Returns:
            The generated interjection_id.
        """
        interjection_id = f"inj-{uuid.uuid4().hex[:12]}"
        interjection = Interjection(
            interjection_id=interjection_id,
            session_id=session_id,
            content=content,
            source=source,
            metadata=metadata or {},
        )

        async with self._lock:
            self._queues.setdefault(session_id, []).append(interjection)
            queue_size = len(self._queues[session_id])

        # DIAGNOSTIC: Log submission with queue size so we can trace if consume() ever picks it up
        logger.info(
            "DIAG submit(): interjection=%s session=%s source=%s queue_size=%d",
            interjection_id,
            session_id,
            source,
            queue_size,
        )
        return interjection_id

    async def consume(self, session_id: str, node_id: str | None = None) -> list[dict[str, Any]]:
        """Pop all pending interjections for a session.

        Marks them as "consumed" and returns their data.

        Args:
            session_id: The workflow session ID.
            node_id: Optional node ID for logging context.

        Returns:
            List of interjection dicts with keys: interjection_id, content,
            source, metadata.
        """
        async with self._lock:
            queue = self._queues.get(session_id, [])
            queue_size = len(queue)
            pending = [ij for ij in queue if ij.status == "pending"]

            results: list[dict[str, Any]] = []
            for ij in pending:
                ij.status = "consumed"
                results.append(
                    {
                        "interjection_id": ij.interjection_id,
                        "content": ij.content,
                        "source": ij.source,
                        "metadata": ij.metadata,
                    }
                )

        # DIAGNOSTIC: Always log consume calls so we can trace the flow
        logger.info(
            "DIAG consume() called: session=%s node=%s | queue_size=%d pending=%d consumed=%d",
            session_id,
            node_id,
            queue_size,
            len(pending),
            len(results),
        )
        return results

    async def get_pending(self, session_id: str) -> list[dict[str, Any]]:
        """List pending interjections for a session without consuming them.

        Args:
            session_id: The workflow session ID.

        Returns:
            List of pending interjection dicts.
        """
        async with self._lock:
            queue = self._queues.get(session_id, [])
            return [
                {
                    "interjection_id": ij.interjection_id,
                    "content": ij.content,
                    "source": ij.source,
                    "metadata": ij.metadata,
                    "status": ij.status,
                }
                for ij in queue
                if ij.status == "pending"
            ]

    async def clear(self, session_id: str) -> None:
        """Remove all interjections for a session.

        Args:
            session_id: The workflow session ID.
        """
        async with self._lock:
            self._queues.pop(session_id, None)
        logger.info("Cleared interjection queue for session %s", session_id)


# Module-level singleton — shared across the application
interjection_service = InterjectionService()
