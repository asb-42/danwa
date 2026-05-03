"""LLM service — profile-based LLM calls via litellm.

Provides a unified interface for generating text using any configured
LLM profile. Reads API keys from environment variables.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

from backend.core.profiles import LLMProfile
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


class LLMService:
    """Generates text using a configured LLM profile."""

    def __init__(
        self,
        profile_id: Optional[str] = None,
        profile_service: Optional[ProfileService] = None,
    ):
        self._profile_service = profile_service or ProfileService()
        self._profile: Optional[LLMProfile] = None

        if profile_id:
            self._profile = self._profile_service.get_llm_profile(profile_id)
            if not self._profile:
                raise ValueError(f"LLM profile '{profile_id}' not found")
        else:
            # Use first available profile as default
            profiles = self._profile_service.list_llm_profiles()
            self._profile = profiles[0] if profiles else None

    @property
    def profile(self) -> Optional[LLMProfile]:
        return self._profile

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using the configured LLM.

        Args:
            prompt: The user prompt.
            system_prompt: Optional system prompt for the LLM.
            temperature: Override temperature (uses profile default if None).
            max_tokens: Override max tokens (uses profile default if None).

        Returns:
            The generated text response.

        Raises:
            RuntimeError: If no LLM profile is configured.
            ValueError: If the API key environment variable is not set.
        """
        if not self._profile:
            raise RuntimeError("No LLM profile configured")

        # Import litellm lazily to avoid import errors when not installed
        try:
            import litellm
        except ImportError:
            raise ImportError(
                "litellm is required for LLM calls. "
                "Install it with: uv add litellm"
            )

        # Build messages
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Get API key from environment
        api_key = os.getenv(self._profile.api_key_env)
        if not api_key and self._profile.provider.value != "local":
            raise ValueError(
                f"API key not found. Set the {self._profile.api_key_env} "
                f"environment variable."
            )

        # Build completion kwargs
        # Use `if ... is not None` to avoid treating 0.0 as falsy
        kwargs: Dict = {
            "model": self._profile.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self._profile.temperature,
            "max_tokens": max_tokens if max_tokens is not None else self._profile.max_tokens,
            "timeout": self._profile.timeout,
        }

        if self._profile.api_base:
            kwargs["api_base"] = self._profile.api_base
        if api_key:
            kwargs["api_key"] = api_key

        logger.info(
            "LLM call: model=%s, temp=%.2f, max_tokens=%d",
            self._profile.model,
            kwargs["temperature"],
            kwargs["max_tokens"],
        )

        response = await litellm.acompletion(**kwargs)
        content = response.choices[0].message.content

        # Log token usage
        if hasattr(response, "usage") and response.usage:
            logger.info(
                "Tokens used: %d in / %d out",
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
            )

        return content

    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a given token count in USD."""
        if (
            not self._profile
            or not self._profile.cost_per_1k_input
            or not self._profile.cost_per_1k_output
        ):
            return 0.0

        input_cost = (input_tokens / 1000) * self._profile.cost_per_1k_input
        output_cost = (output_tokens / 1000) * self._profile.cost_per_1k_output

        return round(input_cost + output_cost, 4)
