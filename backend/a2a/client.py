"""A2A Client — calls external A2A agents as debate participants.

Uses httpx to send JSON-RPC 2.0 requests to external A2A servers.
Supports both synchronous task completion and async polling.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

import httpx

logger = logging.getLogger(__name__)


class A2AClient:
    """Invokes external A2A agents for debate participation."""

    def __init__(self, agent_url: str, timeout: float = 120.0) -> None:
        """Initialise A2AClient."""
        self.agent_url = agent_url.rstrip("/")
        self.timeout = timeout
        self._agent_card: dict | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    async def discover(self) -> dict:
        """Fetch the external agent's Agent Card for capability discovery."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.agent_url}/.well-known/agent.json")
            resp.raise_for_status()
            self._agent_card = resp.json()
            return self._agent_card

    # ------------------------------------------------------------------
    # Task operations
    # ------------------------------------------------------------------

    async def send_task(
        self,
        message: str,
        task_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        """Send a task to the external A2A agent.

        Returns the raw result dict from the JSON-RPC response.
        """
        task_id = task_id or str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": message}],
                },
                "metadata": metadata or {},
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                self.agent_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            result = resp.json()

        return result.get("result", {})

    async def get_task(self, task_id: str) -> dict:
        """Poll for task status/result."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tasks/get",
            "params": {"id": task_id},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.agent_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            result = resp.json()

        return result.get("result", {})

    # ------------------------------------------------------------------
    # High-level debate integration
    # ------------------------------------------------------------------

    async def invoke_agent(
        self,
        context: str,
        role: str,
        round_num: int,
        previous_outputs: list[dict],
    ) -> str:
        """Invoke an external agent as a debate participant.

        Builds a structured prompt from the debate context and sends it
        to the external agent.  Returns the agent's text response.
        """
        # Build structured prompt
        prompt_parts = [
            f"You are participating in a multi-agent debate as the '{role}' in round {round_num}.",
            "",
            "## Debate Topic",
            context,
            "",
            "## Previous Agent Outputs",
        ]
        for ao in previous_outputs:
            prompt_parts.append(f"### {ao.get('role', 'unknown').title()}")
            prompt_parts.append(ao.get("content", "")[:1000])
            prompt_parts.append("")

        prompt_parts.append(f"Please provide your {role} analysis. Be thorough and specific.")

        message = "\n".join(prompt_parts)

        # Send task and get result
        result = await self.send_task(message)

        # Extract text from synchronous response
        status = result.get("status", {}).get("state", "")
        if status == "completed":
            return self._extract_text_from_result(result)

        # If task is async, poll for completion
        task_id = result.get("id")
        if task_id and status in ("submitted", "working"):
            return await self._poll_for_result(task_id)

        return f"[A2A Agent {role}] No response received."

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _poll_for_result(self, task_id: str, max_attempts: int = 60) -> str:
        """Poll for task completion with exponential backoff."""
        for attempt in range(max_attempts):
            result = await self.get_task(task_id)
            status = result.get("status", {}).get("state", "")

            if status == "completed":
                text = self._extract_text_from_result(result)
                if text:
                    return text
                return "[A2A Agent] Completed but no text output."

            if status in ("failed", "canceled"):
                error = result.get("status", {}).get("message", "Unknown error")
                return f"[A2A Agent] Task {status}: {error}"

            # Exponential backoff: 1s, 2s, 4s, ... capped at 10s
            wait = min(2**attempt, 10)
            await asyncio.sleep(wait)

        return "[A2A Agent] Timeout waiting for response."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_text_from_result(result: dict) -> str | None:
        """Extract text content from A2A task result artifacts."""
        artifacts = result.get("artifacts", [])
        for artifact in artifacts:
            parts = artifact.get("parts", [])
            for part in parts:
                if part.get("type") == "text" and part.get("text"):
                    return part["text"]
        return None
