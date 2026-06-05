"""Prompt Composer — assembles the final system prompt from four independent components.

Component roles:
  - Agent Core:    "What you are"    — functional role definition
  - Arg. Pattern:  "How you argue"   — argumentation methodology
  - Tone Profile:  "Your style"      — emotionality & communication
  - Prompt Modifier: "Presentation"  — output formatting & finetuning

The Composer loads each component from its module, concatenates with
section headers, and returns the final system prompt.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from backend.services.module_profile_sync import (
    get_agent_personas_from_modules,
    get_argumentation_patterns_from_modules,
    get_prompt_modifiers_from_modules,
    get_tone_profiles_from_modules,
)
from backend.services.tone_prompt_injector import inject_tone_profile

logger = logging.getLogger(__name__)


@dataclass
class Composition:
    """The four component IDs that define an agent's system prompt."""

    agent_core_id: str = ""
    argumentation_pattern_id: str = ""
    tone_profile_id: str = ""
    prompt_modifier_id: str = ""


class ComposerService:
    """Assembles system prompts from modular components.

    Loads each component from the module system and concatenates them
    into a single system prompt with clear section delimiters.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose(self, composition: Composition) -> str:
        """Assemble a system prompt from the given composition.

        Args:
            composition: The four component IDs.

        Returns:
            Fully assembled system prompt string.
        """
        parts: list[str] = []

        # 1. Agent Core — functional role definition
        core_text = self._load_agent_core(composition.agent_core_id)
        if core_text:
            parts.append(core_text)

        # 2. Argumentation Pattern — how to argue
        pattern_text = self._load_argumentation_pattern(composition.argumentation_pattern_id)
        if pattern_text:
            parts.append(f"## Argumentation Approach\n\n{pattern_text}")

        # 3. Tone Profile — style & emotionality
        tone_text = self._load_tone_profile(composition.tone_profile_id)
        if tone_text:
            parts.append(f"## Communication Style\n\n{tone_text}")

        # 4. Prompt Modifier — presentation & finetuning
        modifier_text = self._load_prompt_modifier(composition.prompt_modifier_id)
        if modifier_text:
            parts.append(modifier_text)

        return "\n\n".join(parts).strip()

    # ------------------------------------------------------------------
    # Component loaders
    # ------------------------------------------------------------------

    def _load_agent_core(self, core_id: str) -> str:
        """Load an agent core's system_prompt by module ID."""
        if not core_id:
            return ""
        try:
            from backend.services.module_profile_sync import get_agent_personas_from_modules

            for mp in get_agent_personas_from_modules():
                if mp.get("id") == core_id:
                    prompt = mp.get("system_prompt", "")
                    if prompt.strip():
                        return prompt.strip()
        except Exception:
            logger.exception("Failed to load agent core '%s'", core_id)
        return ""

    def _load_argumentation_pattern(self, pattern_id: str) -> str:
        """Load an argumentation pattern's content by module ID."""
        if not pattern_id:
            return ""
        try:
            # Patterns are stored as prompt-variant modules with markdown content
            get_argumentation_patterns_from_modules()
            # We need the actual content — look it up via module path
            from backend.modules.models import ModuleType
            from backend.services.module_profile_sync import _get_enabled_modules, _read_module_profile

            for mod in _get_enabled_modules():
                if mod["type"] != ModuleType.PROMPT_VARIANT:
                    continue
                if mod["module_id"] != pattern_id and mod["module_id"].replace("-en", "") != pattern_id:
                    continue
                profile = _read_module_profile(mod["dir"], mod["manifest"])
                if profile is None:
                    continue
                content = profile.get("content", "")
                if content.strip():
                    return content.strip()
        except Exception:
            logger.exception("Failed to load argumentation pattern '%s'", pattern_id)
        return ""

    def _load_tone_profile(self, tone_id: str) -> str:
        """Load a tone profile and convert to style instructions."""
        if not tone_id:
            return ""
        try:
            modules = get_tone_profiles_from_modules()
            for mod in modules:
                if mod.get("id") == tone_id or mod.get("_source_module") == tone_id:
                    # Markdown-based module profile — use content directly
                    content = mod.get("content", "")
                    if content:
                        return f"\n\n[TONE PROFILE]\n{content.strip()}"
                    # Structured profile (DB or legacy JSON) — convert via injector
                    from backend.blueprints.models import ToneProfile

                    profile = ToneProfile(
                        id=mod.get("id", tone_id),
                        name=mod.get("name", tone_id),
                        style=mod.get("style", "neutral"),
                        formality=mod.get("formality", 0.5),
                        verbosity=mod.get("verbosity", "normal"),
                        emotional_valence=mod.get("emotional_valence", 0.5),
                        rhetorical_mode=mod.get("rhetorical_mode", "none"),
                        custom_instructions=mod.get("custom_instructions"),
                    )
                    return inject_tone_profile("", profile)
        except Exception:
            logger.exception("Failed to load tone profile '%s'", tone_id)
        return ""

    def _load_prompt_modifier(self, modifier_id: str) -> str:
        """Load a prompt modifier's content by module ID."""
        if not modifier_id:
            return ""
        try:
            modifiers = get_prompt_modifiers_from_modules()
            for mod in modifiers:
                if mod.get("id") == modifier_id or mod.get("_source_module") == modifier_id:
                    content = mod.get("content", "")
                    if content.strip():
                        return content.strip()
        except Exception:
            logger.exception("Failed to load prompt modifier '%s'", modifier_id)
        return ""

    # ------------------------------------------------------------------
    # Listing helpers (for API/frontend dropdowns)
    # ------------------------------------------------------------------

    @staticmethod
    def list_agent_cores() -> list[dict[str, str]]:
        """List all available agent cores for UI dropdowns."""
        modules = get_agent_personas_from_modules()
        return [
            {
                "id": m.get("id") or m.get("_source_module", ""),
                "name": m.get("name") or m.get("_module_name", ""),
                "role": m.get("role", ""),
                "description": m.get("description", ""),
                "source": "module",
            }
            for m in modules
        ]

    @staticmethod
    def list_argumentation_patterns() -> list[dict[str, str]]:
        """List all available argumentation patterns for UI dropdowns."""
        from backend.modules.models import ModuleType
        from backend.services.module_profile_sync import _get_enabled_modules, _read_module_profile

        results = []
        for mod in _get_enabled_modules():
            if mod["type"] != ModuleType.PROMPT_VARIANT:
                continue
            profile = _read_module_profile(mod["dir"], mod["manifest"])
            if profile is None:
                continue
            manifest_name = mod["manifest"].get("name", {})
            results.append(
                {
                    "id": mod["module_id"],
                    "name": manifest_name.get("en", manifest_name.get("de", mod["module_id"])),
                    "role": profile.get("role", ""),
                    "description": mod["manifest"].get("description", {}).get("en", ""),
                }
            )
        return results

    @staticmethod
    def list_tone_profiles() -> list[dict[str, str]]:
        """List all available tone profiles for UI dropdowns."""
        return [
            {
                "id": m.get("id") or m.get("_source_module", ""),
                "name": m.get("name") or m.get("_module_name", ""),
                "style": m.get("style", ""),
                "description": m.get("description", ""),
            }
            for m in get_tone_profiles_from_modules()
        ]

    @staticmethod
    def list_prompt_modifiers() -> list[dict[str, str]]:
        """List all available prompt modifiers for UI dropdowns."""
        return [
            {
                "id": m.get("id") or m.get("_source_module", ""),
                "name": m.get("name") or m.get("_module_name", ""),
                "description": m.get("description", ""),
            }
            for m in get_prompt_modifiers_from_modules()
        ]
