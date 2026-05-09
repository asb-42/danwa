"""A2A Payload Translator — bidirectional translation between local and A2A formats (Phase 8).

Translates between the local WorkflowState/node input format and A2A task payloads,
and converts A2A task results back to local GenerationResult format.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def translate_to_a2a(
    messages: list[dict[str, str]],
    context: str = "",
    role: str = "",
    round_num: int = 1,
    previous_outputs: list[dict] | None = None,
) -> str:
    """Convert local message format to A2A task message string.

    Args:
        messages: Chat messages in OpenAI format.
        context: The debate case/topic text.
        role: The agent's role (e.g. "strategist").
        round_num: Current round number.
        previous_outputs: List of previous agent outputs.

    Returns:
        Structured prompt string for A2A task.
    """
    parts: list[str] = []

    if context:
        parts.append(f"## Context\n{context}")

    if role:
        parts.append(f"\n## Your Role\nYou are the '{role}' in this debate.")

    if round_num:
        parts.append(f"\n## Round\nThis is round {round_num}.")

    if previous_outputs:
        parts.append("\n## Previous Contributions")
        for i, prev in enumerate(previous_outputs):
            prev_role = prev.get("role", f"Agent {i + 1}")
            prev_content = prev.get("content", "")
            parts.append(f"\n### {prev_role}\n{prev_content}")

    for msg in messages:
        msg_role = msg.get("role", "user")
        content = msg.get("content", "")
        if msg_role == "system":
            parts.append(f"\n## System Instructions\n{content}")
        elif msg_role == "user":
            parts.append(f"\n## Task\n{content}")

    return "\n".join(parts)


def translate_from_a2a(result: dict[str, Any]) -> dict[str, Any]:
    """Convert A2A task result to local GenerationResult-compatible dict.

    Args:
        result: Raw A2A task result dict.

    Returns:
        Dict with keys: content, tokens_in, tokens_out, duration_ms, model.
    """
    content = ""
    tokens_out = 0

    # Try to extract from artifacts
    artifacts = result.get("artifacts", [])
    if artifacts:
        text_parts = []
        for artifact in artifacts:
            for part in artifact.get("parts", []):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
        content = "\n".join(text_parts)

    # Fallback: try result directly
    if not content:
        raw = result.get("result", result)
        if isinstance(raw, str):
            content = raw
        elif isinstance(raw, dict):
            content = raw.get("text", "")
            if not content:
                content = ""
        else:
            content = str(raw) if raw else ""

    # Estimate tokens (rough: 1 token ≈ 4 chars)
    if content:
        tokens_out = max(1, len(content) // 4)

    return {
        "content": content,
        "tokens_in": 0,
        "tokens_out": tokens_out,
        "duration_ms": 0,
        "model": "a2a",
    }
