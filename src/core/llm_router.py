import os
import yaml
import litellm
from pathlib import Path
from typing import Dict, Any

CONFIG_PATH = Path("config/llm_profiles.yaml")

class LLMRouter:
    def __init__(self, profile_name: str = "local_lm_studio"):
        with open(CONFIG_PATH, "r") as f:
            config = yaml.safe_load(f)
        self.profile = config["profiles"][profile_name]
        self._setup_env()

    def _setup_env(self):
        if self.profile.get("api_key_env") and self.profile["api_key_env"] in os.environ:
            self.profile["api_key"] = os.environ[self.profile["api_key_env"]]

    async def call(self, system_prompt: str, user_prompt: str, temp_override: float | None = None) -> Dict[str, Any]:
        params = self.profile["params"].copy()
        if temp_override is not None:
            params["temperature"] = temp_override

        response = await litellm.acompletion(
            model=self.profile["model"],
            api_base=self.profile["base_url"],
            api_key=self.profile["api_key"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            **params
        )
        return {
            "content": response.choices[0].message.content,
            "tokens_used": response.usage.total_tokens,
            "model": response.model,
            "finish_reason": response.choices[0].finish_reason
        }