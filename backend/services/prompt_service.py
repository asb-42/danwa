"""Prompt service — variant management with hot-reload.

Wraps prompt file loading with caching based on file modification time.
Supports variant overrides and fallback to default prompts.

Prompts are loaded from the module filesystem (``modules/prompts-base/prompts/``).
"""

from __future__ import annotations

import hashlib
import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.models.schemas import TranslationEntry


# Lazy import to avoid circular dependency
def _get_translation_service():
    """Return (or lazily create) translation service."""
    from backend.services.translation_service import TranslationService

    return TranslationService()


# Translation language preference from environment
SUPPORTED_TARGET_LANGUAGES = {"de", "fr", "es", "it", "pt", "nl", "pl", "cs", "zh", "ja", "ko"}

logger = logging.getLogger(__name__)

_DEFAULT_PROMPTS_DIR = Path("modules/prompts-base/prompts")
_LEGACY_PROMPTS_DIR = Path("profiles/prompts")


class PromptService:
    """Manages prompt templates with hot-reload support."""

    def __init__(
        self,
        prompts_dir: Path | str = _DEFAULT_PROMPTS_DIR,
        argumentation_patterns_dir: Path | str | None = None,
    ):
        """Initialise PromptService."""
        self.prompts_dir = Path(prompts_dir)
        self._argumentation_patterns_dir = Path(argumentation_patterns_dir) if argumentation_patterns_dir else Path("profiles/argumentation-patterns")
        self._legacy_prompts_dir = Path("profiles/prompts")
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

        When a ``ProfileService`` is attached, DB content is checked first
        (Single Source of Truth).  Falls back to filesystem for project-
        specific overrides or when DB has no matching template.

        For non-default languages (e.g. 'en'), tries ``{role}-{lang}.md``
        first, then falls back to ``{role}.md``.

        Returns a dict with keys: content, hash, mtime, path (mtime for filesystem).
        """
        # Filesystem with hot-reload caching
        # Build candidate file names: language-specific first, then base
        candidates = []
        if language:
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
            raise FileNotFoundError(f"Prompt not found: {variant}/{role} (language={language})")

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

    def get_argumentation_pattern(
        self,
        pattern: str,
        role_type_id: str,
        language: str = "de",
    ) -> str | None:
        """Load an argumentation pattern prompt for a given role.

        Looks up profiles/argumentation-patterns/{pattern}/{role_type_id}.md
        with language fallback ({role_type_id}-{lang}.md then {role_type_id}.md).
        """
        base_dir = self._argumentation_patterns_dir or Path("profiles/argumentation-patterns")
        base = base_dir / pattern
        candidates = []
        if language:
            candidates.append(f"{role_type_id}-{language}.md")
        candidates.append(f"{role_type_id}.md")

        for name in candidates:
            p = base / name
            if p.exists():
                return p.read_text(encoding="utf-8")
        return None

    def clear_cache(self) -> None:
        """Clear the prompt cache (forces reload on next access)."""
        with self._lock:
            self._cache.clear()
        logger.info("Prompt cache cleared")

    def get_prompt_translated(
        self,
        variant: str,
        role: str,
        target_language: str,
        project_dir: Path | str | None = None,
        force_translation: bool = False,
    ) -> TranslationEntry:
        """Get a prompt and translate it, returning a TranslationEntry.

        Checks translation cache first. Falls back to source content.
        """
        source_data = self.get_prompt(variant, role, language="en", project_dir=project_dir)
        cache_key = f"{variant}/{role}/{target_language}"

        # Check translation cache first
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached and not force_translation:
                return cached

        # Use TranslationService for LLM-based translation
        try:
            trans_svc = _get_translation_service()
            entry = trans_svc.get_prompt_translated(
                module_id="prompts-base",
                file_path=f"{variant}/{role}",
                target_language=target_language,
                source_content=source_data.get("content", ""),
                source_hash=source_data.get("hash", ""),
                force=force_translation,
            )

            if entry and entry.translated_content:
                result = TranslationEntry(
                    module_id="prompts-base",
                    file_path=f"{variant}/{role}",
                    source_language="en",
                    target_language=target_language,
                    translated_content=entry.translated_content,
                    quality_score=entry.quality_score,
                    approved=entry.approved,
                )
                with self._lock:
                    self._cache[cache_key] = result
                return result
        except Exception:
            logger.exception(
                "Translation failed for %s/%s → %s, falling back to English content",
                variant,
                role,
                target_language,
            )

        # Fallback: return English source content when translation unavailable
        logger.warning(
            "Using English fallback for %s/%s (requested language: %s)",
            variant,
            role,
            target_language,
        )
        result = TranslationEntry(
            module_id="prompts-base",
            file_path=f"{variant}/{role}",
            source_language="en",
            target_language=target_language,
            translated_content=source_data.get("content", ""),
            quality_score=0.0,
            approved=False,
        )
        return result

    def translate_prompt(
        self,
        variant: str,
        role: str,
        target_language: str = "de",
        force: bool = False,
        auto_approve: bool = True,
        quality_threshold: float = 0.7,
    ) -> dict:
        """Translate a specific prompt using the TranslationService.

        Args:
            variant: Prompt variant (e.g. "default")
            role: Role name (e.g. "strategist")
            target_language: Target language code
            force: Force re-translation
            auto_approve: Auto-approve if quality meets threshold
            quality_threshold: Quality threshold for auto-approval

        Returns:
            Dict with translation result details
        """
        trans_svc = _get_translation_service()
        # Import source content first
        source_data = self.get_prompt(variant, role, language="en")
        trans_svc.import_source_content(
            module_id="prompts-base",
            file_path=f"{variant}/{role}",
            content=source_data.get("content", ""),
        )
        # Perform translation
        result = trans_svc.translate_module(
            module_id="prompts-base",
            target_language=target_language,
            force=force,
            auto_approve=auto_approve,
            quality_threshold=quality_threshold,
        )
        return {
            "module_id": result.module_id,
            "target_language": result.target_language,
            "files_translated": result.files_translated,
            "files_skipped": result.files_skipped,
            "status": result.status,
            "quality_scores": result.quality_scores,
        }

    def assemble_prompt(
        self,
        role_type_id: str,
        argumentation_pattern: str | None = None,
        workflow_variant: str = "default",
        language: str = "de",
        translate: bool = False,
    ) -> str:
        """Assemble the full system prompt from layers:

        1. Argumentation pattern base (if set)
        2. Workflow-variant prompt overlay
        3. Fallback to default variant if workflow_variant not found

        Args:
            role_type_id: The role type (strategist, critic, optimizer, moderator)
            argumentation_pattern: Optional argumentation pattern name
            workflow_variant: Workflow variant (default, kantian, steiner, etc.)
            language: Target language for the prompt (de|en)
            translate: If True, use TranslationService for translation
        """
        parts: list[str] = []

        # Layer 1: Argumentation pattern
        if argumentation_pattern:
            if translate and language != "en":
                ap_prompt = self.get_prompt_translated(
                    argumentation_pattern,
                    role_type_id,
                    target_language=language,
                ).translated_content
                if ap_prompt:
                    parts.append(ap_prompt)
            else:
                ap_prompt = self.get_argumentation_pattern(
                    argumentation_pattern,
                    role_type_id,
                    language,
                )
                if ap_prompt:
                    parts.append(ap_prompt)

        # Layer 2: Workflow-variant prompt
        try:
            if translate and language != "en":
                wf_data = self.get_prompt_translated(
                    workflow_variant,
                    role_type_id,
                    target_language=language,
                )
                wf_prompt = wf_data.translated_content
            else:
                wf_prompt_obj = self.get_prompt(workflow_variant, role_type_id, language=language)
                wf_prompt = wf_prompt_obj.get("content")
            if wf_prompt:
                parts.append(wf_prompt)
        except FileNotFoundError:
            try:
                if translate and language != "en":
                    wf_data = self.get_prompt_translated(
                        "default",
                        role_type_id,
                        target_language=language,
                    )
                    wf_prompt = wf_data.translated_content
                else:
                    wf_prompt_obj = self.get_prompt("default", role_type_id, language=language)
                    wf_prompt = wf_prompt_obj.get("content")
                if wf_prompt:
                    parts.append(wf_prompt)
            except FileNotFoundError as e:
                logger.warning(
                    "Prompt template not found for %s/%s (language=%s, translate=%s): %s",
                    workflow_variant,
                    role_type_id,
                    language,
                    translate,
                    e,
                )

        return "\n\n".join(parts)
