import os
import yaml
import litellm
from pathlib import Path
from typing import Dict, Any, Optional

CONFIG_PATH = Path("config/llm_profiles.yaml")


class LLMRouter:
    """Routes LLM calls to different profiles. Supports a default profile and per-role overrides."""

    def __init__(self, profile_name: str | None = None):
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        self._config = config
        profiles = config.get("profiles", {})
        if not profiles:
            raise ValueError(
                f"No LLM profiles found in {CONFIG_PATH}. "
                "Please add at least one profile."
            )
        if profile_name is None:
            profile_name = next(iter(profiles))
        self._default_profile_name = profile_name
        self._default_profile = self._load_profile(profile_name)
        self._role_profiles: Dict[str, Dict] = {}

    def _load_profile(self, profile_name: str) -> Dict:
        profiles = self._config.get("profiles", {})
        if profile_name not in profiles:
            available = list(profiles.keys())
            raise KeyError(
                f"LLM profile '{profile_name}' not found. "
                f"Available profiles: {available}"
            )
        profile = profiles[profile_name].copy()
        # Resolve api_key from environment variable, with fallback
        api_key_env = profile.get("api_key_env", "")
        if api_key_env and api_key_env in os.environ:
            profile["api_key"] = os.environ[api_key_env]
        elif "api_key" not in profile:
            # No env var set and no hardcoded key — use empty string
            # (works for local LLMs like LM Studio that don't need auth)
            profile["api_key"] = ""
        # Auto-prefix model with 'openai/' for LiteLLM if no provider prefix
        # and a custom base_url is set (e.g. LM Studio, Ollama, vLLM)
        model = profile.get("model", "")
        if "/" not in model and profile.get("base_url"):
            profile["model"] = f"openai/{model}"
        return profile

    def set_role_profile(self, role: str, profile_name: str):
        """Assign a specific LLM profile to a role."""
        self._role_profiles[role] = self._load_profile(profile_name)

    def set_role_profiles(self, role_map: Dict[str, str]):
        """Assign multiple role->profile mappings at once."""
        for role, profile_name in role_map.items():
            self._role_profiles[role] = self._load_profile(profile_name)

    def get_profile_for_role(self, role: str) -> Dict:
        """Get the LLM profile for a role (falls back to default)."""
        if role in self._role_profiles:
            return self._role_profiles[role]
        return self._default_profile

    async def call(
        self,
        system_prompt: str,
        user_prompt: str,
        temp_override: float | None = None,
        role: Optional[str] = None,
    ) -> Dict[str, Any]:
        profile = self.get_profile_for_role(role) if role else self._default_profile
        params = profile["params"].copy()
        if temp_override is not None:
            params["temperature"] = temp_override

        response = await litellm.acompletion(
            model=profile["model"],
            api_base=profile["base_url"],
            api_key=profile["api_key"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            **params,
        )
        return {
            "content": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens,
            "model": response.model,
            "finish_reason": response.choices[0].finish_reason,
        }
