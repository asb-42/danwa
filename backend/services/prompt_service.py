"""Prompt service — variant management with hot-reload.

Wraps prompt file loading with caching based on file modification time.
Supports variant overrides and fallback to default prompts.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_DEFAULT_PROMPTS_DIR = Path("profiles/prompts")


class PromptService:
    """Manages prompt templates with hot-reload support."""

    def __init__(self, prompts_dir: Path | str = _DEFAULT_PROMPTS_DIR):
        self.prompts_dir = Path(prompts_dir)
        self._cache: Dict[str, Dict] = {}
        self._lock = threading.RLock()

    def get_prompt(self, variant: str, role: str) -> Dict:
        """Load a prompt template with caching and hot-reload.

        Returns a dict with keys: content, hash, mtime, path.
        """
        cache_key = f"{variant}/{role}"

        # Determine file path
        if variant == "default":
            prompt_path = self.prompts_dir / "default" / f"{role}.md"
        else:
            prompt_path = self.prompts_dir / "variants" / variant / f"{role}.md"

        # Fallback to default if not found
        if not prompt_path.exists():
            fallback = self.prompts_dir / "default" / f"{role}.md"
            if fallback.exists():
                logger.warning(
                    "Prompt %s/%s not found, falling back to default/%s",
                    variant, role, role,
                )
                prompt_path = fallback
            else:
                raise FileNotFoundError(
                    f"Prompt not found: {variant}/{role} (looked at {prompt_path})"
                )

        current_mtime = prompt_path.stat().st_mtime

        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and cached["mtime"] == current_mtime:
                return cached

            # Hot-reload
            content = prompt_path.read_text(encoding="utf-8")
            data = {
                "content": content,
                "hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                "mtime": current_mtime,
                "path": str(prompt_path),
            }
            self._cache[cache_key] = data
            logger.info("Prompt loaded: %s/%s (hash=%s)", variant, role, data["hash"])
            return data

    def render(
        self,
        variant: str,
        role: str,
        variables: Optional[Dict[str, str]] = None,
    ) -> str:
        """Load a prompt and optionally substitute variables.

        Variables are replaced using simple {key} syntax.
        """
        data = self.get_prompt(variant, role)
        content = data["content"]

        if variables:
            for key, value in variables.items():
                content = content.replace(f"{{{key}}}", value)

        return content

    def list_available_roles(self, variant: str = "default") -> list[str]:
        """List available roles for a given variant."""
        if variant == "default":
            variant_dir = self.prompts_dir / "default"
        else:
            variant_dir = self.prompts_dir / "variants" / variant

        if not variant_dir.is_dir():
            return []

        return sorted(p.stem for p in variant_dir.glob("*.md"))

    def clear_cache(self) -> None:
        """Clear the prompt cache (forces reload on next access)."""
        with self._lock:
            self._cache.clear()
        logger.info("Prompt cache cleared")
