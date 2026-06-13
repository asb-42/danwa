"""LLM service — profile-based LLM calls.

For cloud providers (openrouter, openai, anthropic) uses litellm.
For local providers (LM Studio, Ollama, etc.) uses direct HTTP via httpx
to the OpenAI-compatible /v1/chat/completions endpoint — the same way
curl works.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from backend.core.profiles import LLMProfile, LLMProvider
from backend.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of an LLM generation call.

    Carries the generated content along with metadata about the call:
    real token counts (from litellm or local endpoint), wall-clock
    duration, and the model name used.

    When the LLM responds with tool calls instead of text, ``tool_calls``
    contains the list of parsed tool call dicts.
    """

    content: str = ""
    tool_calls: list[dict[str, Any]] | None = None
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
        """Initialise LLMService."""
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

        # Lazily-built cache of the per-user BYOK store (P4.5+ §4.1).
        # ``UserKeyStore`` opens a sqlite3 connection + a Fernet PRAGMA
        # in its ``__init__``; rebuilding it on every per-user LLM call
        # was 5-20 ms of avoidable overhead. The cache is process-local
        # and is invalidated by :meth:`_get_user_key_store` if the
        # underlying connection is dead (e.g. master-key rotation that
        # leaves the cached store pointed at a stale Fernet key).
        self._user_key_store_cache: Any = None

    @property
    def profile(self) -> LLMProfile | None:
        """Profile the instance."""
        return self._profile

    # Known placeholder values that should be treated as unset
    _API_KEY_PLACEHOLDERS = frozenset(
        {
            "YOUR_API_KEY_ENV_VAR",
            "YOUR_API_KEY",
            "REPLACE_ME",
            "CHANGEME",
            "",
        }
    )

    # Provider → list of well-known env var names to try as fallback
    _PROVIDER_DEFAULT_ENV_VARS: dict[str, list[str]] = {
        "openrouter": ["OPENROUTER_API_KEY", "OPENAI_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "local": ["LM_STUDIO_KEY", "LOCAL_LLM_API_KEY"],
        "ollama": ["OLLAMA_API_KEY", "LM_STUDIO_KEY"],
        "cloudflare": ["CLOUDFLARE_API_TOKEN"],
        "xiaomi": ["XIAOMI_API_KEY"],
        "opencode-zen": ["OPENCODE_ZEN_API_KEY"],
    }

    def _get_user_key_store(self) -> Any:
        """Return a process-cached :class:`UserKeyStore` (P4.5+ §4.1).

        ``UserKeyStore.__init__`` opens a sqlite3 connection and runs
        ``PRAGMA journal_mode=WAL`` + a Fernet init. Doing that on every
        per-user LLM call cost 5-20 ms.  We cache the instance on
        ``self`` and rebuild it only if the cached connection is dead
        (e.g. the underlying SQLite file was rotated or the Fernet key
        was changed underneath us, which surfaces as an
        :class:`OperationalError` on the next read).
        """
        # Lazy import: ``backend.persistence.user_key_store`` pulls in
        # ``cryptography`` (Fernet) which is not needed by callers that
        # never go through the BYOK path.
        from backend.persistence.user_key_store import UserKeyStore

        store = self._user_key_store_cache
        # ``_init_db`` re-runs an idempotent CREATE IF NOT EXISTS
        # which is the cheapest possible "is the connection still
        # alive" probe.  We always run the probe — even on a freshly
        # built store — so the dead-connection path is exercised
        # regardless of whether the cache was already populated.
        # If the connection is dead, sqlite3 raises
        # ``OperationalError`` (file-rotation, lock, etc.); a closed
        # connection raises ``ProgrammingError``.
        if store is None:
            store = UserKeyStore()
        try:
            store._init_db()
        except Exception:
            logger.debug(
                "LLMService: UserKeyStore connection is dead, rebuilding",
                exc_info=True,
            )
            store = UserKeyStore()
        self._user_key_store_cache = store
        return store

    def _resolve_api_key(self, required: bool = True) -> str:
        """Resolve the API key for this profile using the BYOK priority chain.

        Priority:
        1. Profile's direct ``api_key`` field (BYOK — set via API or UI)
        2. User-scoped key override (if user_id is set on the service)
        3. Environment variable (``api_key_env``)
        4. Provider-specific default env vars (fallback for placeholder configs)

        Args:
            required: If True, raises ValueError when no key is found.

        Returns:
            The resolved API key string, or empty string if not required and not found.
        """
        # 1. Profile-level BYOK key
        if self._profile.api_key:
            return self._profile.api_key

        # 2. User-scoped key override (stored in auth.db).  The store
        # is process-cached via :meth:`_get_user_key_store` so a single
        # sqlite3 connection + Fernet PRAGMA is reused across calls.
        if hasattr(self, "_user_id") and self._user_id:
            try:
                store = self._get_user_key_store()
                user_key = store.get_key(self._user_id, self._profile.id)
                if user_key:
                    return user_key
            except Exception:
                pass  # Fall through to env var

        # 3. Environment variable fallback
        api_key_env = self._profile.api_key_env
        # Skip known placeholder values
        if api_key_env and api_key_env not in self._API_KEY_PLACEHOLDERS:
            env_key = os.getenv(api_key_env, "")
            if env_key:
                return env_key

        # 4. Provider-specific default env vars (handles stale placeholder configs)
        provider = getattr(self._profile, "provider", None)
        provider_str = provider.value if hasattr(provider, "value") else str(provider or "")
        for env_name in self._PROVIDER_DEFAULT_ENV_VARS.get(provider_str, []):
            env_key = os.getenv(env_name, "")
            if env_key:
                logger.info(
                    "API key for profile '%s' resolved via provider fallback '%s'",
                    self._profile.id,
                    env_name,
                )
                return env_key

        # Also try common universal env vars
        for env_name in ("OPENAI_API_KEY", "LLM_API_KEY"):
            env_key = os.getenv(env_name, "")
            if env_key:
                logger.info(
                    "API key for profile '%s' resolved via universal fallback '%s'",
                    self._profile.id,
                    env_name,
                )
                return env_key

        if required:
            env_hint = (
                f"Set the {api_key_env} environment variable"
                if api_key_env and api_key_env not in self._API_KEY_PLACEHOLDERS
                else "Configure the api_key_env in the LLM profile or set an API key (BYOK)"
            )
            raise ValueError(
                f"API key not found for profile '{self._profile.id}' ({self._profile.name}). "
                f"{env_hint}, or configure a key in the profile settings (BYOK)."
            )
        return ""

    def set_user_context(self, user_id: str) -> None:
        """Set the user context for BYOK key resolution."""
        self._user_id = user_id

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
        context: str = "",
        language: str = "en",
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
            tools: Optional list of OpenAI-compatible tool definitions for
                   function calling. When provided, the LLM may respond with
                   ``tool_calls`` instead of text content.
            language: ISO 639-1 code of the active UI language.  Used to
                translate the injected "Today is {date}." date line so the
                prefix matches the user's locale.  Defaults to ``"en"``
                (English SSOT).  See
                :mod:`backend.services.prompt_date_prefix` for the
                caching + fallback policy (section 3.4 of the
                2026-06-12 code review).

        Returns:
            GenerationResult with content, token counts, duration, model name,
            and optionally tool_calls if the LLM chose to call a tool.

        Raises:
            RuntimeError: If no LLM profile is configured.
            ValueError: If the API key environment variable is not set.
        """
        if not self._profile:
            raise RuntimeError("No LLM profile configured")

        # --- Time Awareness — inject current date into every system prompt.
        # P4.3: English is the SSOT; other locales are translated on demand
        # (DB-cached) by ``prompt_date_prefix.get_date_prefix``.
        from backend.services.prompt_date_prefix import get_date_prefix

        date_line = get_date_prefix(language=language)
        if system_prompt:
            system_prompt = f"{date_line}\n\n{system_prompt}"
        else:
            system_prompt = date_line

        # Build messages
        messages: list[dict[str, str]] = []
        messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Resolve temperature / max_tokens with proper None handling
        temp = temperature if temperature is not None else self._profile.temperature
        tokens = max_tokens if max_tokens is not None else self._profile.max_tokens

        # --- LLM Activity Tracking ---
        from backend.services.llm_activity import llm_activity

        provider_name = self._profile.provider.value if self._profile.provider else "unknown"
        model_name = self._profile.model or self._profile.name
        call_id = await llm_activity.start_call(
            model=model_name,
            provider=provider_name,
            context=context,
        )

        try:
            # Route by protocol (Phase 8)
            protocol = getattr(self._profile, "protocol", "litellm")
            if protocol == "a2a":
                result = await self._generate_a2a(messages, temp, tokens, tools=tools)
            # Route: local/OpenAI-compatible providers → direct HTTP, cloud providers → litellm
            elif self._profile.provider.value in {"local", "ollama", "opencode-zen", "opencode-go"}:
                result = await self._generate_local(messages, temp, tokens, tools=tools, extra_kwargs=extra_kwargs)
            elif self._profile.provider == LLMProvider.CLOUDFLARE:
                result = await self._generate_cloudflare(messages, temp, tokens, extra_kwargs=extra_kwargs)
            else:
                result = await self._generate_litellm(messages, temp, tokens, tools=tools, extra_kwargs=extra_kwargs)

            await llm_activity.end_call(
                call_id,
                tokens_in=result.tokens_in,
                tokens_out=result.tokens_out,
                status="completed",
            )
            return result

        except Exception as exc:
            await llm_activity.end_call(
                call_id,
                status="failed",
                error=str(exc),
            )
            raise

    async def generate_with_fallback(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        on_fallback: Any | None = None,
        language: str = "en",
    ) -> GenerationResult:
        """Generate text with automatic fallback to a secondary LLM profile.

        Attempts generation using the primary profile. If an ``A2AError``
        is raised **and** a ``fallback_llm_profile_id`` is configured on
        the primary profile, retries the call with the fallback profile.

        Args:
            prompt: The user prompt text.
            system_prompt: Optional system prompt for the LLM.
            temperature: Override temperature (uses profile default if ``None``).
            max_tokens: Override max tokens (uses profile default if ``None``).
            on_fallback: Optional async callback ``(from_profile_id, to_profile_id,
                fallback_model, fallback_provider)`` invoked when a fallback
                actually occurs. Callers typically use this to publish an
                ``llm.fallback`` SSE event so the frontend can display a
                notification. The callback is wrapped in a ``try/except``
                so a failing callback never aborts the fallback itself.
            language: ISO 639-1 code of the active UI language; forwarded to
                :meth:`generate` so the injected date prefix is translated
                consistently.  Defaults to ``"en"`` (English SSOT).

        Returns:
            GenerationResult from the primary or fallback profile.

        Raises:
            A2AError: Re-raised if no fallback profile is configured.
            RuntimeError: If no LLM profile is configured.
            ValueError: If the API key cannot be resolved.
        """
        from backend.a2a.exceptions import A2AError

        try:
            return await self.generate(prompt, system_prompt, temperature, max_tokens, language=language)
        except A2AError:
            fallback_id = getattr(self._profile, "fallback_llm_profile_id", None)
            if not fallback_id:
                raise
            from_profile = self._profile.id
            logger.warning("A2A failed for profile %s, falling back to %s", from_profile, fallback_id)
            fallback_service = LLMService(profile_id=fallback_id, profile_service=self._profile_service)
            # T-3: Notify caller about fallback so it can emit an SSE event
            if on_fallback is not None:
                try:
                    fallback_model = getattr(fallback_service.profile, "model", "")
                    fallback_provider = str(getattr(fallback_service.profile, "provider", ""))
                    await on_fallback(from_profile, fallback_id, fallback_model, fallback_provider)
                except Exception:
                    logger.debug("on_fallback callback failed", exc_info=True)
            return await fallback_service.generate(prompt, system_prompt, temperature, max_tokens, language=language)

    async def _generate_a2a(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
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
        tools: list[dict[str, Any]] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
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
        api_key = self._resolve_api_key(required=False)

        payload: dict[str, Any] = {
            "model": self._profile.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            payload["tools"] = tools

        if extra_kwargs:
            allowed = {"temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty", "seed", "stop"}
            for k, v in extra_kwargs.items():
                if k in allowed and v is not None:
                    payload[k] = v

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
        choice = data["choices"][0]
        message = choice.get("message", {})
        content = message.get("content")
        finish_reason = choice.get("finish_reason", "")

        # Extract tool_calls if present (OpenAI-compatible local endpoints)
        tool_calls = None
        raw_tool_calls = message.get("tool_calls")
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                tool_calls.append(
                    {
                        "id": tc.get("id"),
                        "type": tc.get("type"),
                        "function": {
                            "name": tc["function"]["name"],
                            "arguments": tc["function"]["arguments"],
                        },
                    }
                )
            logger.info(
                "Local LLM returned %d tool_calls for model=%s, finish_reason=%s",
                len(tool_calls),
                self._profile.model,
                finish_reason,
            )

        if content is None or (isinstance(content, str) and content.strip() == ""):
            reasoning = message.get("reasoning_content", "")
            if reasoning:
                logger.info(
                    "Local LLM empty content for model=%s, extracting from reasoning_content (%d chars).",
                    self._profile.model,
                    len(reasoning),
                )
                content = reasoning
            else:
                logger.warning(
                    "Local LLM empty/None response for model=%s. Full choice: %s",
                    self._profile.model,
                    str(choice)[:500],
                )
                psf = message.get("provider_specific_fields", {})
                for k, v in (psf or {}).items():
                    logger.warning("  psf[%s] = %s", k, str(v)[:300])
                if content is None:
                    content = psf.get("reasoning_content", psf.get("content", "")) if psf else ""

        if content and "<think>" in content:
            cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if cleaned:
                logger.info(
                    "Stripped <think> block from local model=%s (%d → %d chars).",
                    self._profile.model,
                    len(content),
                    len(cleaned),
                )
                content = cleaned
            else:
                logger.warning(
                    "Local model %s returned ONLY a <think> block. First 200 chars: %s",
                    self._profile.model,
                    content[:200],
                )
                content = ""

        if finish_reason == "length" and content and not content.strip():
            logger.warning(
                "Local model %s hit max_tokens during reasoning. content=%r, finish_reason=%s",
                self._profile.model,
                content[:100],
                finish_reason,
            )

        # Extract real token usage from JSON response body
        tokens_in = 0
        tokens_out = 0
        if isinstance(data, dict):
            usage = data.get("usage")
            if usage:
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
            logger.info(
                "Tokens used: %d in / %d out",
                tokens_in,
                tokens_out,
            )

        return GenerationResult(
            content=content,
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            model=self._profile.model,
        )

    async def _generate_cloudflare(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """Call Cloudflare Workers AI via direct HTTP.

        API format:
          POST https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/run/{MODEL}
          Authorization: Bearer {API_KEY}
          Body: {"messages": [...]}
        """
        # Resolve account ID
        account_id_env = self._profile.account_id_env or "CLOUDFLARE_ACCOUNT_ID"
        account_id = os.getenv(account_id_env)
        if not account_id:
            raise ValueError(f"Cloudflare account ID not found. Set the {account_id_env} environment variable.")

        # Resolve API key
        api_key = self._resolve_api_key(required=True)

        model = self._profile.model
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"

        payload: dict[str, Any] = {
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if extra_kwargs:
            allowed = {"temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty", "seed", "stop"}
            for k, v in extra_kwargs.items():
                if k in allowed and v is not None:
                    payload[k] = v

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        logger.info(
            "LLM call (cloudflare): POST %s model=%s, temp=%.2f, max_tokens=%d",
            url,
            model,
            temperature,
            max_tokens,
        )

        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=self._profile.timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        duration_ms = int((time.monotonic() - t0) * 1000)

        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            raise RuntimeError(f"Cloudflare API error: {errors}")

        result = data.get("result", {})
        content = result.get("response", "")

        return GenerationResult(
            content=content,
            tokens_in=0,
            tokens_out=0,
            duration_ms=duration_ms,
            model=model,
        )

    async def _generate_litellm(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        tools: list[dict[str, Any]] | None = None,
        extra_kwargs: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """Call a cloud LLM via litellm (OpenRouter, OpenAI, Anthropic, etc.)."""
        try:
            import litellm
        except ImportError:
            raise ImportError("litellm is required for cloud LLM calls. Install it with: uv add litellm")

        api_key = self._resolve_api_key(required=True)

        model_name = self._profile.model
        provider_prefix = self._profile.provider.value
        # LiteLLM uses 'xiaomi_mimo/' prefix, not 'xiaomi/'
        if provider_prefix == "xiaomi":
            provider_prefix = "xiaomi_mimo"
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

        if tools:
            kwargs["tools"] = tools

        if self._profile.api_base:
            kwargs["api_base"] = self._profile.api_base

        if extra_kwargs:
            # Whitelist which params we allow from bundles
            allowed = {"temperature", "top_p", "top_k", "frequency_penalty", "presence_penalty", "seed", "stop"}
            for k, v in extra_kwargs.items():
                if k in allowed and v is not None:
                    kwargs[k] = v
                    if k == "temperature":
                        temperature = v  # update local var for logging

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

        # Extract tool_calls if present
        tool_calls = None
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls:
            tool_calls = []
            for tc in raw_tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                )
            logger.info(
                "LLM returned %d tool_calls for model=%s",
                len(tool_calls),
                model_name,
            )

        psf = getattr(message, "provider_specific_fields", None) or {}
        if content is None or (isinstance(content, str) and content.strip() == ""):
            logger.warning(
                "LLM empty/None content for model=%s. provider_specific_fields keys: %s. "
                "Full message attrs: content=%r, role=%r, refusal=%r, tool_calls=%r",
                model_name,
                list(psf.keys()),
                content,
                getattr(message, "role", None),
                getattr(message, "refusal", None),
                getattr(message, "tool_calls", None),
            )
            for k, v in psf.items():
                val_preview = str(v)[:300] if v else ""
                logger.warning("  psf[%s] = %s", k, val_preview)

        if not content:
            reasoning = psf.get("reasoning_content")
            if reasoning:
                logger.info(
                    "LLM returned reasoning_content for model=%s (using reasoning as answer).",
                    model_name,
                )
                content = reasoning
            elif psf.get("content"):
                logger.info(
                    "LLM returned content via provider_specific_fields for model=%s.",
                    model_name,
                )
                content = psf["content"]
            else:
                logger.warning(
                    "LLM returned None content for model=%s. Content filter or empty response.",
                    model_name,
                )
                content = ""

        if content and "<think>" in content:
            cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            if cleaned:
                logger.info(
                    "Stripped <think> block from model=%s response (%d chars reasoning → %d chars answer).",
                    model_name,
                    len(content),
                    len(cleaned),
                )
                content = cleaned
            else:
                logger.warning(
                    "Model %s returned ONLY a <think> block, no answer. First 200 chars: %s",
                    model_name,
                    content[:200],
                )
                content = ""

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
            tool_calls=tool_calls,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            duration_ms=duration_ms,
            model=self._profile.model,
        )

    def generate_sync(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        context: str = "",
        language: str = "en",
    ) -> GenerationResult:
        """Synchronous wrapper around async generate().

        Runs the async generation in a dedicated thread to avoid
        event-loop conflicts when called from FastAPI handlers.

        H-03 fix: replaced ``asyncio.new_event_loop()`` +
        ``asyncio.set_event_loop()`` with ``asyncio.run()`` which
        manages the loop lifecycle internally.  The deprecated
        ``set_event_loop`` was only needed when internal code called
        ``get_event_loop()`` — all such call sites have been
        migrated to ``get_running_loop()`` (Sprint 49), so
        ``asyncio.run()`` is now safe and more efficient.

        Args:
            language: ISO 639-1 code forwarded to :meth:`generate`; see
                P4.3 in :mod:`backend.services.prompt_date_prefix`.
        """
        import asyncio
        import concurrent.futures

        def _run_in_thread():
            return asyncio.run(
                self.generate(
                    prompt,
                    system_prompt,
                    temperature,
                    max_tokens,
                    context=context,
                    language=language,
                )
            )

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_run_in_thread)
            return future.result(timeout=120)

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
