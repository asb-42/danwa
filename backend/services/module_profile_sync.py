"""Module Profile Sync — bridges installed modules to blueprint entity tables.

Option B: Instead of copying module data into DB tables, this service
reads enabled module profiles at list-time and merges them with DB results.
Module-sourced entries are marked with `_source_module` and `_readonly=True`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from backend.modules.models import ModuleType
from backend.modules.type_derivation import derive_module_type, parent_dir_name, resolve_manifest_type

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = ROOT / "modules"

# Mapping: module type → (profile_format, entity_key)
# entity_key is the field name used as the unique identifier in the entity dict
MODULE_TYPE_ID_FIELD: dict[str, str] = {
    ModuleType.LLM_PROFILE: "id",
    ModuleType.ROLE_TYPE: "id",
    ModuleType.AGENT_PERSONA: "id",
    ModuleType.TONE_PROFILE: "id",
    ModuleType.PROMPT_VARIANT: "id",
    ModuleType.WORKFLOW_TEMPLATE: "id",
    ModuleType.BUNDLE: "id",
}


def _get_enabled_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Return list of enabled module manifests from the modules directory."""
    modules = []
    if not modules_dir.exists():
        return modules

    # Collect module dirs: root level + one level of subdirectories
    mod_dirs = []
    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith(".") or ".bak." in entry.name:
            continue
        if (entry / "manifest.json").exists():
            mod_dirs.append(entry)
        else:
            for sub in sorted(entry.iterdir()):
                if sub.is_dir() and not sub.name.startswith(".") and ".bak." not in sub.name:
                    mod_dirs.append(sub)

    for mod_dir in mod_dirs:
        manifest_path = mod_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        # Check enabled status from module_registry
        enabled = _is_module_enabled(mod_dir.name)
        if not enabled:
            continue

        module_id = mod_dir.name
        # Derive type from manifest type (with alias resolution), fall back to
        # directory + module_id prefix derivation
        parent = parent_dir_name(mod_dir, modules_dir)
        manifest_type = manifest.get("type")
        derived_type = resolve_manifest_type(manifest_type) if manifest_type else derive_module_type(parent, module_id)

        modules.append(
            {
                "module_id": module_id,
                "manifest": manifest,
                "dir": mod_dir,
                "type": derived_type,
            }
        )

    return modules


def _is_module_enabled(module_id: str) -> bool:
    """Check if a module is enabled in the module_registry DB."""
    import sqlite3

    db_path = ROOT / "data" / "blueprints.db"
    if not db_path.exists():
        return True  # If no DB, assume enabled

    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT enabled FROM module_registry WHERE id = ?",
            (module_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return True  # Not in registry yet, assume enabled
        return bool(row[0])
    except (sqlite3.Error, Exception):
        return True


def _derive_profile_format(profile_file: str, manifest_format: str | None) -> str | None:
    if manifest_format:
        return manifest_format
    ext = Path(profile_file).suffix.lower()
    return {"yaml": "yaml", "yml": "yaml", "json": "json", "md": "markdown"}.get(ext)


def _read_module_profile(mod_dir: Path, manifest: dict) -> dict[str, Any] | None:
    """Read and parse a module's profile file."""
    profile_file = manifest.get("profile_file")
    profile_format = _derive_profile_format(profile_file, manifest.get("profile_format"))

    if not profile_file:
        return None

    profile_path = mod_dir / profile_file
    if not profile_path.exists():
        return None

    content = profile_path.read_text(encoding="utf-8")
    if profile_format == "yaml":
        return yaml.safe_load(content)
    elif profile_format == "json":
        return json.loads(content)
    elif profile_format == "markdown":
        return {"content": content}
    return None


def _mark_readonly(data: dict, module_id: str, manifest: dict) -> dict:
    """Add metadata fields to mark an entity as module-sourced and read-only."""
    data["_source_module"] = module_id
    data["_readonly"] = True
    data["_module_name"] = manifest.get("name", {}).get("en", module_id)
    data["_module_version"] = manifest.get("version", "0.0.0")
    return data


def get_llm_profiles_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get LLM profiles from enabled llm-profile modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.LLM_PROFILE:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        # Ensure required fields have defaults
        profile.setdefault("is_active", True)
        profile.setdefault("service_eligible", True)
        results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_role_types_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get role types from enabled role-type modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.ROLE_TYPE:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        profile.setdefault("is_active", True)
        profile.setdefault("default_max_rounds", 5)
        profile.setdefault("default_consensus_threshold", 0.9)
        profile.setdefault("category", "functional")
        results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_agent_personas_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get agent personas from enabled agent-persona modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.AGENT_PERSONA:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        # Map role_type → role (some modules use role_type)
        if "role_type" in profile and "role" not in profile:
            profile["role"] = profile.pop("role_type")
        profile.setdefault("max_rounds", 5)
        profile.setdefault("consensus_threshold", 0.9)
        profile.setdefault("tags", [])
        profile.setdefault("llm_profile_id", "")
        results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_tone_profiles_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get tone profiles from enabled tone-profile modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.TONE_PROFILE:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        profile.setdefault("style", "neutral")
        profile.setdefault("formality", 0.5)
        profile.setdefault("verbosity", "medium")
        profile.setdefault("emotional_valence", 0.5)
        profile.setdefault("rhetorical_mode", "balanced")
        results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_prompt_templates_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get prompt templates from enabled prompt-variant modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.PROMPT_VARIANT:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        # Prompt profiles from modules have content field
        if "content" in profile:
            profile.setdefault("id", mod["module_id"])
            # Derive name from manifest (localized) or fallback to module_id
            manifest_name = mod["manifest"].get("name", {})
            profile.setdefault("name", manifest_name.get("en", manifest_name.get("de", mod["module_id"])))
            profile.setdefault("role", "strategist")
            profile.setdefault("variant", "default")
            # Use manifest language if available, otherwise detect from profile filename
            manifest_lang = mod["manifest"].get("language")
            if manifest_lang:
                profile.setdefault("language", manifest_lang)
            else:
                profile.setdefault("language", "en")
            profile.setdefault("variables", [])
            results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_workflow_templates_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get workflow templates from enabled workflow-template modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.WORKFLOW_TEMPLATE:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        profile.setdefault("category", "custom")
        profile.setdefault("tags", [])
        results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_bundles_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get agent bundles from enabled bundle modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.BUNDLE:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        profile.setdefault("is_active", True)
        results.append(_mark_readonly(profile, mod["module_id"], mod["manifest"]))
    return results


def get_argumentation_patterns_from_modules(modules_dir: Path = MODULES_DIR) -> list[str]:
    """Get argumentation pattern names from enabled argumentation-pattern modules."""
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.ARGUMENTATION_PATTERN:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        name = profile.get("name") or profile.get("id") or mod["module_id"]
        if name not in results:
            results.append(name)
    return results


def get_prompt_modifiers_from_modules(modules_dir: Path = MODULES_DIR) -> list[dict[str, Any]]:
    """Get prompt modifiers from enabled prompt-modifier modules.

    Returns a list of dicts with keys: id, name, content, description.
    """
    results = []
    for mod in _get_enabled_modules(modules_dir):
        if mod["type"] != ModuleType.PROMPT_MODIFIER:
            continue
        profile = _read_module_profile(mod["dir"], mod["manifest"])
        if profile is None:
            continue
        content = profile.get("content", "")
        if not content.strip():
            continue
        manifest_name = mod["manifest"].get("name", {})
        entry = {
            "id": mod["module_id"],
            "name": manifest_name.get("en", manifest_name.get("de", mod["module_id"])),
            "content": content,
            "description": mod["manifest"].get("description", {}).get("en", ""),
        }
        results.append(_mark_readonly(entry, mod["module_id"], mod["manifest"]))
    return results
