"""A2A Server — handles incoming A2A tasks from external agents.

When an external A2A agent sends a ``tasks/send`` request, the server
creates a Danwa debate and runs it asynchronously.  The external agent
can poll for results via ``tasks/get``.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from backend.a2a.schemas import A2AMessage, A2ATask
from backend.api.deps import get_audit_service, get_debate_store_for_project
from backend.a2a.task_manager import TaskManager, TaskStatus
from backend.models.schemas import DebateRequest
from backend.persistence.project_store import ProjectStore

logger = logging.getLogger(__name__)


class A2AServer:
    """Processes A2A tasks by creating and running Danwa debates."""

    def __init__(
        self,
        task_manager: TaskManager | None = None,
        project_id: str = "default",
        project_store: ProjectStore | None = None,
    ) -> None:
        self.task_manager = task_manager or TaskManager()
        self.project_id = project_id
        self._project_store = project_store

    # ------------------------------------------------------------------
    # JSON-RPC method handlers
    # ------------------------------------------------------------------

    async def handle_task_send(self, task: A2ATask) -> dict:
        """Handle ``tasks/send`` — create and run a debate.

        Returns immediately with a task acknowledgment.  The debate
        runs in a background coroutine.
        """
        task_id = task.id or str(uuid.uuid4())

        # Extract debate topic from message
        topic = self._extract_topic(task.message)
        if not topic:
            return self._error_response(task_id, "No text content in message")

        # Create task record
        self.task_manager.create_task(task_id, status=TaskStatus.SUBMITTED)

        # Start debate asynchronously
        asyncio.create_task(self._run_debate(task_id, topic))

        result = {
            "id": task_id,
            "status": {"state": TaskStatus.SUBMITTED.value},
        }
        if task.message:
            result["message"] = {
                "role": task.message.role,
                "parts": [{"type": p.type, "text": p.text} for p in task.message.parts],
            }
        return result

    async def handle_task_get(self, task_id: str) -> dict:
        """Handle ``tasks/get`` — return current task status and result."""
        task = self.task_manager.get_task(task_id)
        if not task:
            return self._error_response(task_id, "Task not found")

        result: dict = {
            "id": task_id,
            "status": {"state": task["status"].value},
        }

        if task["status"] == TaskStatus.COMPLETED:
            result["artifacts"] = [{"parts": [{"type": "text", "text": task["result"]}]}]
        elif task["status"] == TaskStatus.FAILED:
            result["status"]["message"] = task.get("error", "Unknown error")

        return result

    async def handle_task_cancel(self, task_id: str) -> dict:
        """Handle ``tasks/cancel`` — cancel a running debate."""
        task = self.task_manager.get_task(task_id)
        if not task:
            return self._error_response(task_id, "Task not found")

        self.task_manager.update_task(task_id, status=TaskStatus.CANCELED)
        return {"id": task_id, "status": {"state": TaskStatus.CANCELED.value}}

    # ------------------------------------------------------------------
    # Background debate execution
    # ------------------------------------------------------------------

    async def _run_debate(self, task_id: str, topic: str) -> None:
        """Run a debate for an A2A task (background coroutine).

        Creates a debate via the internal API, starts the workflow,
        and polls for completion.
        """
        try:
            self.task_manager.update_task(task_id, status=TaskStatus.WORKING)

            # Import here to avoid circular imports at module level
            from backend.models.schemas import CaseInput, DebateRequest

            request = DebateRequest(
                case=CaseInput(text=topic),
                language="de",
            )

            # Create and start debate via internal helpers
            debate_id = await self._create_and_start_debate(request)
            self.task_manager.update_task(task_id, debate_id=debate_id)

            # Poll for completion
            result = await self._wait_for_completion(debate_id)

            # Format result as A2A response
            output_text = self._format_debate_result(result)
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.COMPLETED,
                result=output_text,
            )

        except Exception as exc:
            logger.error("A2A debate failed for task %s: %s", task_id, exc, exc_info=True)
            self.task_manager.update_task(
                task_id,
                status=TaskStatus.FAILED,
                error=str(exc),
            )

    async def _create_and_start_debate(self, request: DebateRequest) -> str:
        """Create a debate and start the workflow. Returns the debate_id."""
        import uuid as _uuid

        from backend.api.deps import get_audit_service, get_debate_store_for_project
        from backend.models.schemas import DebateStatus
        from backend.services.debate_workflow import run_debate_workflow

        debate_id = str(_uuid.uuid4())
        store = get_debate_store_for_project(self.project_id, self._project_store)
        audit = get_audit_service()

        from datetime import UTC, datetime

        now = datetime.now(UTC)
        debate = {
            "debate_id": debate_id,
            "status": DebateStatus.PENDING,
            "request": request,
            "max_rounds": request.max_rounds,
            "current_round": 0,
            "rounds": [],
            "created_at": now,
            "updated_at": now,
            "result": None,
        }
        store.put(debate_id, debate)

        # Run workflow in background
        asyncio.create_task(run_debate_workflow(debate_id, self.project_id, audit, store, self._project_store))

        return debate_id

    async def _wait_for_completion(
        self,
        debate_id: str,
        poll_interval: float = 2.0,
        max_attempts: int = 300,
    ) -> dict:
        """Poll the debate store until the debate completes or fails."""
        from backend.api.deps import get_debate_store_for_project
        from backend.models.schemas import DebateStatus

        store = get_debate_store_for_project(self.project_id, self._project_store)

        for _ in range(max_attempts):
            debate = store.get(debate_id)
            if not debate:
                raise RuntimeError(f"Debate {debate_id} not found")

            status = debate.get("status")
            status_value = status.value if hasattr(status, "value") else status

            if status_value in (
                DebateStatus.COMPLETED.value,
                DebateStatus.FAILED.value,
            ):
                return debate.get("result") or {}

            await asyncio.sleep(poll_interval)

        raise TimeoutError(f"Debate {debate_id} did not complete in time")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_topic(message: A2AMessage | None) -> str | None:
        """Extract text topic from an A2A message."""
        if not message or not message.parts:
            return None
        for part in message.parts:
            if part.type == "text" and part.text:
                return part.text
        return None

    @staticmethod
    def _format_debate_result(result: dict) -> str:
        """Format a debate result as human-readable text."""
        parts: list[str] = []
        parts.append("## Debate Result")
        parts.append(f"Consensus: {result.get('final_consensus', 0):.1%}")
        parts.append(f"Rounds: {result.get('current_round', 0)}")
        parts.append("")
        parts.append(result.get("output", "No output generated."))

        # Include agent outputs
        for ao in result.get("agent_outputs", []):
            parts.append(f"\n### {ao.get('role', 'unknown').title()}")
            parts.append(ao.get("content", "")[:500])

        return "\n".join(parts)

    @staticmethod
    def _error_response(task_id: str, message: str) -> dict:
        """Build a JSON-RPC error result."""
        return {
            "id": task_id,
            "status": {"state": "failed", "message": message},
        }
