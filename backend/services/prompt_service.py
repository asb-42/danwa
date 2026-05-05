"""Prompt service — variant management with hot-reload.

Wraps prompt file loading with caching based on file modification time.
Supports variant overrides and fallback to default prompts.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_PROMPTS_DIR = Path("profiles/prompts")


class PromptService:
    """Manages prompt templates with hot-reload support."""

    def __init__(self, prompts_dir: Path | str = _DEFAULT_PROMPTS_DIR):
        self.prompts_dir = Path(prompts_dir)
        self._cache: dict[str, dict] = {}
        self._lock = threading.RLock()

    def get_prompt(
        self,
        variant: str,
        role: str,
        language: str = "de",
        project_dir: Path | str | None = None,
    ) -> dict:
        """Load a prompt template with caching and hot-reload.

        For non-default languages (e.g. 'en'), tries ``{role}-{lang}.md``
        first, then falls back to ``{role}.md``.

        If ``project_dir`` is given, project-specific prompts are checked
        first (``{project_dir}/prompts/{variant}/{role}.md``) before
        falling back to the global prompts directory.

        Returns a dict with keys: content, hash, mtime, path.
        """
        # Build candidate file names: language-specific first, then base
        candidates = []
        if language and language != "de":
            candidates.append(f"{role}-{language}.md")
        candidates.append(f"{role}.md")

        # Try project-specific prompts first
        prompt_path = None
        if project_dir is not None:
            project_prompts = Path(project_dir) / "prompts"
            if variant == "default":
                project_base = project_prompts / "default"
            else:
                project_base = project_prompts / "variants" / variant
            for name in candidates:
                path = project_base / name
                if path.exists():
                    prompt_path = path
                    break

        # Determine global base directory
        if prompt_path is None:
            if variant == "default":
                base_dir = self.prompts_dir / "default"
            else:
                base_dir = self.prompts_dir / "variants" / variant

            # Try candidates in order
            for name in candidates:
                path = base_dir / name
                if path.exists():
                    prompt_path = path
                    break

            # Fallback to default variant if variant-specific not found
            if prompt_path is None:
                default_dir = self.prompts_dir / "default"
                for name in candidates:
                    path = default_dir / name
                    if path.exists():
                        logger.warning(
                            "Prompt %s/%s not found, falling back to default/%s",
                            variant,
                            role,
                            name,
                        )
                        prompt_path = path
                        break

        if prompt_path is None:
            raise FileNotFoundError(
                f"Prompt not found: {variant}/{role} (language={language})"
            )

        cache_key = f"{variant}/{role}/{language}"

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
        variables: dict[str, str] | None = None,
        language: str = "de",
        project_dir: Path | str | None = None,
    ) -> str:
        """Load a prompt and optionally substitute variables.

        Variables are replaced using simple {key} syntax.
        """
        data = self.get_prompt(variant, role, language=language, project_dir=project_dir)
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
