"""A2AAdapter — unified interface for A2A calls (Phase 8).

Provides the same interface as LLMService.generate() so that
A2A agents are transparent to node execution.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from backend.a2a.client import A2AClient
from backend.a2a.exceptions import (
    A2AConnectionError,
    A2AError,
    A2AProtocolError,
    A2ATimeoutError,
)
from backend.a2a.url_validator import validate_a2a_url
from backend.services.llm_service import GenerationResult

logger = logging.getLogger(__name__)


class A2AAdapter:
    """Adapter that provides LLMService-compatible interface for A2A agents.

    Usage::

        adapter = A2AAdapter("http://agent.example.com", timeout=120)
        result = await adapter.invoke(messages=[...], config={...})
        # result is a GenerationResult, same as LLMService.generate()
    """

    def __init__(
        self,
        a2a_endpoint: str,
        timeout: int = 120,
        allow_private_ips: bool = False,
    ) -> None:
        """Initialise A2AAdapter."""
        self._endpoint = validate_a2a_url(a2a_endpoint, allow_private_ips)
        self._timeout = timeout
        self._allow_private_ips = allow_private_ips
        self._client = A2AClient(self._endpoint, timeout=float(timeout))

    async def invoke(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """Invoke the external A2A agent and return a GenerationResult.

        Args:
            messages: Chat messages in OpenAI format
                (``[{"role": "system", "content": "..."}, ...]``).
            config: Optional config with keys like ``context``, ``role``,
                ``round_num``, ``previous_outputs``.

        Returns:
            GenerationResult with content, token counts, duration, and model.

        Raises:
            A2ATimeoutError: If the A2A call exceeds the timeout.
            A2AConnectionError: If the HTTP connection fails.
            A2AProtocolError: If the response is not valid JSON-RPC.
            A2AAgentError: If the external agent returns an error.
        """
        config = config or {}
        start = time.monotonic()

        # Build the task payload
        message_text = self._build_task_payload(messages, config)

        try:
            raw_result = await self._client.send_task(
                message=message_text,
                metadata={
                    "context": config.get("context", ""),
                    "role": config.get("role", ""),
                    "round_num": config.get("round_num", 1),
                },
            )
        except TimeoutError as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            raise A2ATimeoutError(
                f"A2A call timed out after {self._timeout}s",
                endpoint=self._endpoint,
            ) from exc
        except ConnectionError as exc:
            raise A2AConnectionError(
                f"Failed to connect to A2A agent: {exc}",
                endpoint=self._endpoint,
            ) from exc
        except Exception as exc:
            if "json" in str(exc).lower() or "rpc" in str(exc).lower():
                raise A2AProtocolError(
                    f"Invalid JSON-RPC response: {exc}",
                    endpoint=self._endpoint,
                ) from exc
            raise A2AError(
                f"A2A call failed: {exc}",
                endpoint=self._endpoint,
            ) from exc

        # Extract response
        content, tokens_out = self._extract_response(raw_result)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        return GenerationResult(
            content=content,
            tokens_in=0,  # A2A agents may not report input tokens
            tokens_out=tokens_out,
            duration_ms=elapsed_ms,
            model=f"a2a:{self._endpoint}",
        )

    async def discover(self, endpoint: str | None = None) -> dict[str, Any]:
        """Discover the capabilities of an A2A agent.

        Args:
            endpoint: Override the endpoint URL (uses the constructor URL if None).

        Returns:
            Dict with keys: name, description, version, capabilities,
            skills, input_modes, output_modes.
        """
        url = endpoint or self._endpoint
        url = validate_a2a_url(url, self._allow_private_ips)

        try:
            card = await A2AClient(url, timeout=30.0).discover()
        except Exception as exc:
            raise A2AConnectionError(
                f"Failed to discover A2A agent: {exc}",
                endpoint=url,
            ) from exc

        return {
            "name": card.get("name", "Unknown"),
            "description": card.get("description", ""),
            "version": card.get("version", ""),
            "capabilities": card.get("capabilities", {}),
            "skills": card.get("skills", []),
            "input_modes": card.get("capabilities", {}).get("input_modes", ["text"]),
            "output_modes": card.get("capabilities", {}).get("output_modes", ["text"]),
        }

    @staticmethod
    def _build_task_payload(
        messages: list[dict[str, str]],
        config: dict[str, Any],
    ) -> str:
        """Convert messages + config into a structured prompt string for A2A."""
        parts: list[str] = []

        context = config.get("context", "")
        if context:
            parts.append(f"## Context\n{context}")

        role = config.get("role", "")
        if role:
            parts.append(f"\n## Your Role\nYou are the '{role}' in this debate.")

        round_num = config.get("round_num", 0)
        if round_num:
            parts.append(f"\n## Round\nThis is round {round_num}.")

        previous = config.get("previous_outputs", [])
        if previous:
            parts.append("\n## Previous Contributions")
            for i, prev in enumerate(previous):
                prev_role = prev.get("role", f"Agent {i + 1}")
                prev_content = prev.get("content", "")
                parts.append(f"\n### {prev_role}\n{prev_content}")

        # Add the actual messages
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                parts.append(f"\n## System Instructions\n{content}")
            elif role == "user":
                parts.append(f"\n## Task\n{content}")

        return "\n".join(parts)

    @staticmethod
    def _extract_response(result: dict[str, Any]) -> tuple[str, int]:
        """Extract text content and token count from an A2A task result.

        Returns:
            Tuple of (content_text, estimated_tokens).
        """
        # Try to extract from artifacts
        artifacts = result.get("artifacts", [])
        if artifacts:
            parts = []
            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("type") == "text":
                        parts.append(part.get("text", ""))
            content = "\n".join(parts)
        else:
            # Fallback: try result directly
            raw = result.get("result", None)
            if raw is None:
                content = ""
            elif isinstance(raw, str):
                content = raw
            elif isinstance(raw, dict):
                content = raw.get("text", "")
            else:
                content = str(raw)

        # Estimate tokens (rough: 1 token ≈ 4 chars)
        tokens = max(1, len(content) // 4) if content else 0
        return content, tokens
