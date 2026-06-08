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
from backend.a2a.task_manager import TaskManager, TaskStatus
from backend.api.deps import get_audit_service, get_debate_store_for_case, get_project_store
from backend.core.config import is_service_llm_eligible
from backend.models.schemas import DebateRequest

logger = logging.getLogger(__name__)


def _resolve_a2a_llm_profile(project_id: str | None = None) -> str | None:
    """Resolve the best LLM profile for A2A-initiated debates."""
    try:
        from backend.core.config import settings
        from backend.services.profile_service import ProfileService

        svc = ProfileService()

        # 1. Use the active (service) LLM profile if eligible
        if settings.service_llm_profile_id:
            active = svc.get_llm_profile(settings.service_llm_profile_id)
            if active:
                ok, reason = is_service_llm_eligible(active)
                if ok:
                    logger.info("A2A debate: using active LLM profile '%s'", active.id)
                    return active.id
                logger.debug("Active profile '%s' not eligible: %s", settings.service_llm_profile_id, reason)

        all_profiles = svc.list_llm_profiles()
        if not all_profiles:
            logger.warning("No LLM profiles available for A2A debate")
            return None

        eligible = []
        local_profiles = []
        for p in all_profiles:
            ok, _reason = is_service_llm_eligible(p)
            if ok:
                eligible.append(p)
                if p.provider.value in ("local", "ollama"):
                    local_profiles.append(p)

        if local_profiles:
            chosen = local_profiles[0]
            logger.info("A2A debate: using local LLM profile '%s' (provider=%s)", chosen.id, chosen.provider.value)
            return chosen.id

        if eligible:
            chosen = eligible[0]
            logger.info("A2A debate: using eligible LLM profile '%s' (provider=%s)", chosen.id, chosen.provider.value)
            return chosen.id

        logger.warning("A2A debate: no eligible profiles, using first available '%s'", all_profiles[0].id)
        return all_profiles[0].id
    except Exception as exc:
        logger.error("Failed to resolve LLM profile for A2A debate: %s", exc)
        return None


class A2AServer:
    """Processes A2A tasks by creating and running Danwa debates."""

    def __init__(
        self,
        task_manager: TaskManager | None = None,
        project_id: str = "_default",
        project_store=None,
    ) -> None:
        """Initialise A2AServer.

        The ``project_store`` parameter is kept for backward compatibility
        but is no longer used.
        """
        self.task_manager = task_manager or TaskManager()
        self.project_id = project_id

    # ------------------------------------------------------------------
    # JSON-RPC method handlers
    # ------------------------------------------------------------------

    async def handle_task_send(self, task: A2ATask) -> dict:
        """Handle ``tasks/send`` — create and run a debate.

        Returns immediately with a task acknowledgment.  The debate
        runs in a background coroutine.

        Metadata keys supported:
        - ``project_id``: Target project (defaults to ``_default``)
        - ``language``: Debate language code (defaults to ``de``)
        """
        task_id = task.id or str(uuid.uuid4())

        topic = self._extract_topic(task.message)
        if not topic:
            return self._error_response(task_id, "No text content in message")

        self.task_manager.create_task(task_id, status=TaskStatus.SUBMITTED)

        meta = task.metadata or {}
        project_id = meta.get("project_id", self.project_id)
        language = meta.get("language", "de")

        asyncio.create_task(self._run_debate(task_id, topic, project_id, language))

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
        elif task["status"] == TaskStatus.WORKING:
            debate_id = task.get("debate_id")
            if debate_id:
                progress = self._get_debate_progress(debate_id)
                if progress:
                    result["status"]["message"] = progress.get("status_message", "working")
                    result["progress"] = progress

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

    async def _run_debate(
        self,
        task_id: str,
        topic: str,
        project_id: str | None = None,
        language: str = "de",
    ) -> None:
        """Run a debate for an A2A task (background coroutine).

        Creates a debate via the internal API, starts the workflow,
        and polls for completion.
        """
        effective_project = project_id or self.project_id
        try:
            self.task_manager.update_task(task_id, status=TaskStatus.WORKING)

            from backend.models.schemas import CaseInput, DebateRequest

            llm_profile_id = _resolve_a2a_llm_profile(effective_project)

            request = DebateRequest(
                case=CaseInput(text=topic),
                language=language,
                llm_profile_id=llm_profile_id or "local-qwen",
            )

            debate_id = await self._create_and_start_debate(request, effective_project)
            self.task_manager.update_task(task_id, debate_id=debate_id)

            result = await self._wait_for_completion(debate_id, effective_project)

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

    async def _create_and_start_debate(
        self,
        request: DebateRequest,
        project_id: str | None = None,
    ) -> str:
        """Create a debate and start the workflow. Returns the debate_id."""
        import uuid as _uuid

        from backend.models.schemas import DebateStatus
        from backend.services.debate_workflow import run_debate_workflow

        effective_project = project_id or self.project_id
        debate_id = str(_uuid.uuid4())
        store = get_debate_store_for_case(effective_project)
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

        asyncio.create_task(run_debate_workflow(debate_id, effective_project, audit, store))

        return debate_id

    async def _wait_for_completion(
        self,
        debate_id: str,
        project_id: str | None = None,
        poll_interval: float = 2.0,
        max_attempts: int = 300,
    ) -> dict:
        """Poll the debate store until the debate completes or fails."""
        from backend.models.schemas import DebateStatus

        effective_project = project_id or self.project_id
        store = get_debate_store_for_case(effective_project)

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

    def _get_debate_progress(self, debate_id: str) -> dict | None:
        """Return detailed debate progress for a running debate."""
        from backend.models.schemas import DebateStatus

        for project in get_project_store().list_all():
            try:
                store = get_debate_store_for_case(project.id)
                debate = store.get(debate_id)
                if debate:
                    break
            except Exception:
                continue
        else:
            return None

        status = debate.get("status")
        status_value = status.value if hasattr(status, "value") else status

        current_round = debate.get("current_round", 0)
        max_rounds = debate.get("max_rounds", 3)
        rounds = debate.get("rounds", [])
        request = debate.get("request", {})

        agent_count = 4
        if hasattr(request, "agent_profile"):
            agent_count = len(request.agent_profile)
        elif isinstance(request, dict):
            agent_count = len(request.get("agent_profile", [])) or 4

        current_agent_index = 0
        if rounds:
            last_round = rounds[-1]
            agent_outputs = last_round.get("agent_outputs", [])
            current_agent_index = len(agent_outputs)

        role_order = ["strategist", "critic", "optimizer", "moderator"]
        current_agent = role_order[current_agent_index % agent_count] if current_agent_index < agent_count else role_order[-1]

        if status_value == DebateStatus.PENDING.value:
            if current_round > 0:
                status_message = (
                    f"Agent {current_agent_index + 1} of {agent_count} ({current_agent.title()}) in round {current_round} of {max_rounds}"
                )
            else:
                status_message = "Debate pending, preparing agents..."
        elif status_value in (DebateStatus.RUNNING.value, "running"):
            status_message = f"Agent {current_agent_index + 1} of {agent_count} ({current_agent.title()}) in round {current_round} of {max_rounds}"
        else:
            status_message = status_value

        return {
            "status_message": status_message,
            "current_round": current_round,
            "max_rounds": max_rounds,
            "current_agent_index": current_agent_index,
            "agent_count": agent_count,
            "current_agent_role": current_agent,
            "rounds_completed": len(rounds),
        }
