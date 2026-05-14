"""LLM service — profile-based LLM calls.

For cloud providers (openrouter, openai, anthropic) uses litellm.
For local providers (LM Studio, Ollama, etc.) uses direct HTTP via httpx
to the OpenAI-compatible /v1/chat/completions endpoint — the same way
curl works.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.core.profiles import LLMProfile
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of an LLM generation call.

    Carries the generated content along with metadata about the call:
    real token counts (from litellm or local endpoint), wall-clock
    duration, and the model name used.
    """

    content: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: int = 0
    model: str = ""


class LLMService:
    """Generates text using a configured LLM profile."""

    def __init__(
        self,
        profile_id: str | None = None,
        profile_service: ProfileService | None = None,
    ):
        self._profile_service = profile_service or ProfileService()
        self._profile: LLMProfile | None = None

        if profile_id:
            self._profile = self._profile_service.get_llm_profile(profile_id)
            if not self._profile:
                raise ValueError(f"LLM profile '{profile_id}' not found")
        else:
            # Use first available profile as default
            profiles = self._profile_service.list_llm_profiles()
            self._profile = profiles[0] if profiles else None

    @property
    def profile(self) -> LLMProfile | None:
        return self._profile

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Generate text using the configured LLM.

        For local providers, uses direct HTTP to the OpenAI-compatible
        /v1/chat/completions endpoint (same as curl).
        For cloud providers, uses litellm.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt for the LLM.
            temperature: Override temperature (uses profile default if None).
            max_tokens: Override max tokens (uses profile default if None).

        Returns:
            GenerationResult with content, token counts, duration, and model name.

        Raises:
            RuntimeError: If no LLM profile is configured.
            ValueError: If the API key environment variable is not set.
        """
        if not self._profile:
            raise RuntimeError("No LLM profile configured")

        # Build messages
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Resolve temperature / max_tokens with proper None handling
        temp = temperature if temperature is not None else self._profile.temperature
        tokens = max_tokens if max_tokens is not None else self._profile.max_tokens

        # Route by protocol (Phase 8)
        protocol = getattr(self._profile, "protocol", "litellm")
        if protocol == "a2a":
            return await self._generate_a2a(messages, temp, tokens)
        # Route: local/OpenAI-compatible providers → direct HTTP, cloud providers → litellm
        local_providers = {"local", "ollama", "opencode-zen", "opencode-go", "xiaomi"}
        if self._profile.provider.value in local_providers:
            return await self._generate_local(messages, temp, tokens)
        else:
            return await self._generate_litellm(messages, temp, tokens)

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Generate with automatic fallback on A2A failure."""
        from backend.a2a.exceptions import A2AError

        try:
            return await self.generate(prompt, system_prompt, temperature, max_tokens)
        except A2AError:
            fallback_id = getattr(self._profile, "fallback_llm_profile_id", None)
            if not fallback_id:
                raise
            logger.warning("A2A failed for profile %s, falling back to %s", self._profile.id, fallback_id)
            fallback_service = LLMService(profile_id=fallback_id, profile_service=self._profile_service)
            return await fallback_service.generate(prompt, system_prompt, temperature, max_tokens)

    async def _generate_a2a(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Generate via A2A protocol using A2AAdapter."""
        from backend.a2a.adapter import A2AAdapter
        from backend.core.config import settings

        endpoint = getattr(self._profile, "a2a_endpoint", None)
        if not endpoint:
            raise RuntimeError(f"LLM profile '{self._profile.id}' has protocol='a2a' but no a2a_endpoint")
        timeout = getattr(self._profile, "a2a_timeout", 120)
        adapter = A2AAdapter(endpoint, timeout=timeout, allow_private_ips=settings.a2a_allow_private_ips)
        return await adapter.invoke(messages=messages, config={})

    async def _generate_local(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Call a local OpenAI-compatible endpoint directly via httpx.

        This is the same as:
            curl http://<api_base>/chat/completions \\
              -H "Content-Type: application/json" \\
              -d '{"model": "<model>", "messages": [...]}'
        """
        api_base = self._profile.api_base
        if not api_base:
            raise ValueError(f"Local profile '{self._profile.id}' requires api_base (e.g. http://192.168.178.200:1234/v1)")

        # Ensure api_base ends with /v1 and build the chat completions URL
        api_base = api_base.rstrip("/")
        if not api_base.endswith("/v1"):
            api_base = f"{api_base}/v1"
        url = f"{api_base}/chat/completions"

        # Get API key (optional for local, but include if set)
        api_key = os.getenv(self._profile.api_key_env, "")

        payload: dict[str, Any] = {
            "model": self._profile.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        logger.info(
            "LLM call (local): POST %s model=%s, temp=%.2f, max_tokens=%d",
            url,
            self._profile.model,
            temperature,
            max_tokens,
        )

        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=self._profile.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        duration_ms = int((time.monotonic() - t0) * 1000)

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        # Extract real token usage if available
        usage = data.get("usage")
        tokens_in = usage.get("prompt_tokens", 0) if usage else 0
        tokens_out = usage.get("completion_tokens", 0) if usage else 0

        if tokens_in or tokens_out:
            logger.info(
                "Tokens used: %d in / %d out",
                tokens_in,
                tokens_out,
            )

        return GenerationResult(
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            model=self._profile.model,
        )

    async def _generate_litellm(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Call a cloud LLM via litellm (OpenRouter, OpenAI, Anthropic, etc.)."""
        try:
            import litellm
        except ImportError:
            raise ImportError("litellm is required for cloud LLM calls. Install it with: uv add litellm")

        # Get API key from environment
        api_key = os.getenv(self._profile.api_key_env)
        if not api_key:
            raise ValueError(f"API key not found. Set the {self._profile.api_key_env} environment variable.")

        # Auto-prepend provider prefix for litellm routing.
        # e.g. "openrouter" + "tencent/hy3-preview:free" → "openrouter/tencent/hy3-preview:free"
        model_name = self._profile.model
        provider_prefix = self._profile.provider.value
        if not model_name.startswith(f"{provider_prefix}/"):
            model_name = f"{provider_prefix}/{model_name}"

        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self._profile.timeout,
            "api_key": api_key,
        }

        if self._profile.api_base:
            kwargs["api_base"] = self._profile.api_base

        logger.info(
            "LLM call (litellm): model=%s, temp=%.2f, max_tokens=%d",
            model_name,
            temperature,
            max_tokens,
        )

        t0 = time.monotonic()
        response = await litellm.acompletion(**kwargs)
        duration_ms = int((time.monotonic() - t0) * 1000)

        message = response.choices[0].message
        content = message.content

        # Thinking/reasoning models (e.g. tencent/hy3-preview) may return
        # the actual response in reasoning_content while content is None.
        if content is None:
            psf = getattr(message, "provider_specific_fields", None) or {}
            reasoning = psf.get("reasoning_content")
            if reasoning:
                logger.info(
                    "LLM returned reasoning_content for model=%s (thinking model detected, using reasoning output).",
                    model_name,
                )
                content = reasoning
            else:
                logger.warning(
                    "LLM returned None content for model=%s. This may indicate a content filter or empty response.",
                    model_name,
                )
                content = ""

        # Extract real token usage
        tokens_in = 0
        tokens_out = 0
        if hasattr(response, "usage") and response.usage:
            tokens_in = response.usage.prompt_tokens
            tokens_out = response.usage.completion_tokens
            logger.info(
                "Tokens used: %d in / %d out",
                tokens_in,
                tokens_out,
            )

        return GenerationResult(
            content=content,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            model=model_name,
        )

    def generate_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> GenerationResult:
        """Synchronous wrapper around async generate().

        Uses asyncio.run() to execute the async generation in a sync context.
        """
        import asyncio

        return asyncio.run(self.generate(prompt, system_prompt, temperature, max_tokens))

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a given token count in USD."""
        if not self._profile or not self._profile.cost_per_1k_input or not self._profile.cost_per_1k_output:
            return 0.0
        input_cost = (input_tokens / 1000) * self._profile.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self._profile.cost_per_1k_output
        return round(input_cost + output_cost, 6)
