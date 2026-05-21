"""Module type derivation — maps directory names and module_id prefixes to ModuleType/ModuleCategory."""

from __future__ import annotations

from pathlib import Path

from backend.modules.models import ModuleType, ModuleCategory

# Directory name → ModuleType mapping
_DIR_TO_TYPE: dict[str, ModuleType] = {
    "llm-profiles": ModuleType.LLM_PROFILE,
    "agent-argumentation-patterns": ModuleType.PROMPT_VARIANT,
    "workflows": ModuleType.WORKFLOW_TEMPLATE,
    "agent-bundles": ModuleType.BUNDLE,
    "ui-translations": ModuleType.LANGUAGE_PACK,
    "agent-tone-profiles": ModuleType.TONE_PROFILE,
    "agent-prompt-modifiers": ModuleType.ARGUMENTATION_PATTERN,
}

# Directory name → ModuleCategory mapping
_DIR_TO_CATEGORY: dict[str, ModuleCategory] = {
    "llm-profiles": ModuleCategory.LLM_PROFILES,
    "agent-argumentation-patterns": ModuleCategory.PROMPTS,
    "workflows": ModuleCategory.WORKFLOWS,
    "agent-bundles": ModuleCategory.BUNDLES,
    "ui-translations": ModuleCategory.TRANSLATIONS,
    "agent-tone-profiles": ModuleCategory.TONE_PROFILES,
    "agent-prompt-modifiers": ModuleCategory.PROMPTS,
}

# module_id prefix → ModuleType (for mixed directories like agent-cores)
_PREFIX_TO_TYPE: dict[str, ModuleType] = {
    "agent-": ModuleType.AGENT_PERSONA,
    "role-": ModuleType.ROLE_TYPE,
    "tone-": ModuleType.TONE_PROFILE,
    "prompt-": ModuleType.PROMPT_VARIANT,
    "workflow-": ModuleType.WORKFLOW_TEMPLATE,
    "llm-": ModuleType.LLM_PROFILE,
    "bundle-": ModuleType.BUNDLE,
}


def derive_module_type(parent_dir_name: str, module_id: str) -> ModuleType:
    if mod_type := _DIR_TO_TYPE.get(parent_dir_name):
        return mod_type
    for prefix, mod_type in _PREFIX_TO_TYPE.items():
        if module_id.startswith(prefix):
            return mod_type
    return ModuleType.AGENT_PERSONA


def derive_module_category(parent_dir_name: str) -> ModuleCategory:
    return _DIR_TO_CATEGORY.get(parent_dir_name, ModuleCategory.AGENTS)


def parent_dir_name(module_dir: Path, modules_dir: Path) -> str:
    try:
        rel = module_dir.relative_to(modules_dir)
        parts = rel.parts
        return parts[0] if len(parts) > 1 else ""
    except ValueError:
        return ""
