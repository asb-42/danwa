"""Bundle Export/Import — portable AgentBundle serialization.

Exports an AgentBundle with all its referenced entities (LLM profile,
RoleType, RoleDefinition, PromptTemplate, ToneProfile) as a self-contained
JSON document.  Import resolves ID conflicts and re-creates all entities.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from backend.blueprints.models import (
    AgentBundle,
    BlueprintLLMProfile,
    BundleComposition,
    RoleType,
    ToneProfile,
)
from backend.blueprints.module_lookups import (
    resolve_role_type,
)
from backend.blueprints.repository import BlueprintRepository

logger = logging.getLogger(__name__)

BUNDLE_EXPORT_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def export_bundle(bundle_id: str, repo: BlueprintRepository) -> dict[str, Any]:
    """Export a Bundle with all its referenced entities as a JSON-serializable dict.

    Args:
        bundle_id: The AgentBundle ID to export.
        repo: Repository instance.

    Returns:
        Dict with export metadata, bundle data, and all referenced entities.

    Raises:
        ValueError: If the bundle or any required reference is not found.
    """
    bundle = repo.get_bundle(bundle_id)
    if not bundle:
        raise ValueError(f"Bundle '{bundle_id}' not found")

    llm_profile = repo.get_llm_profile(bundle.llm_profile_id)
    if not llm_profile:
        raise ValueError(f"Referenced LLM profile '{bundle.llm_profile_id}' not found")

    role_type = resolve_role_type(bundle.role_type_id)
    if not role_type:
        raise ValueError(f"Referenced RoleType '{bundle.role_type_id}' not found")

    tone_profile: ToneProfile | None = None
    if bundle.tone_profile_id:
        tone_profile = repo.get_tone_profile(bundle.tone_profile_id)

    return {
        "export_version": BUNDLE_EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "type": "agent_bundle",
        "bundle": _serialize_bundle(bundle),
        "llm_profile": _serialize_llm_profile(llm_profile),
        "role_type": _serialize_role_type(role_type),
        "tone_profile": _serialize_tone_profile(tone_profile) if tone_profile else None,
    }


def export_bundle_with_dependencies(
    bundle_id: str,
    repo: BlueprintRepository,
    include_all_role_types: bool = False,
) -> dict[str, Any]:
    """Export a Bundle with all dependencies, optionally including all RoleTypes.

    Args:
        bundle_id: The AgentBundle ID to export.
        repo: Repository instance.
        include_all_role_types: If True, include all RoleTypes (useful for portability).

    Returns:
        Dict with export data including all referenced entities.
    """
    data = export_bundle(bundle_id, repo)

    if include_all_role_types:
        from backend.services.module_profile_sync import get_role_types_from_modules

        all_role_types = get_role_types_from_modules()
        data["all_role_types"] = [_serialize_role_type(RoleType(**rt)) for rt in all_role_types if rt.get("id")]

    return data


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


class ImportConflictStrategy:
    """How to handle ID conflicts during import."""

    SKIP = "skip"  # Skip if ID already exists
    OVERWRITE = "overwrite"  # Replace existing entity
    RENAME = "rename"  # Generate new ID


def import_bundle(
    data: dict[str, Any],
    repo: BlueprintRepository,
    conflict_strategy: str = ImportConflictStrategy.RENAME,
) -> AgentBundle:
    """Import a Bundle from an exported JSON dict.

    Args:
        data: The exported bundle dict.
        repo: Repository instance.
        conflict_strategy: How to handle ID conflicts (skip, overwrite, rename).

    Returns:
        The imported (or existing) AgentBundle.

    Raises:
        ValueError: If the data format is invalid.
    """
    if data.get("type") != "agent_bundle":
        raise ValueError(f"Expected type 'agent_bundle', got '{data.get('type')}'")

    if "bundle" not in data:
        raise ValueError("Missing 'bundle' key in export data")

    # Track ID mappings for cross-references
    id_map: dict[str, str] = {}

    # 1. Resolve RoleType from modules (no DB import needed)
    role_type_raw = data.get("role_type")
    if not role_type_raw:
        raise ValueError("Missing 'role_type' in bundle export")
    role_type = resolve_role_type(role_type_raw.get("id", ""))
    if not role_type:
        # Fallback: construct from raw data
        role_type = RoleType(**{k: v for k, v in role_type_raw.items() if k in RoleType.model_fields})

    # 2. Import LLM Profile (required)
    llm_raw = data.get("llm_profile")
    if not llm_raw:
        raise ValueError("Missing 'llm_profile' in bundle export")
    llm_profile = _import_llm_profile(llm_raw, repo, conflict_strategy, id_map)

    # 3. Import ToneProfile (optional)
    tone_profile: ToneProfile | None = None
    if data.get("tone_profile"):
        tone_profile = _import_tone_profile(data["tone_profile"], repo, conflict_strategy, id_map)

    # 4. Import Bundle with resolved references
    bundle_raw = data["bundle"]
    bundle = _import_bundle_entity(
        bundle_raw,
        repo,
        conflict_strategy,
        id_map,
        llm_profile.id,
        role_type.id,
        tone_profile.id if tone_profile else None,
    )

    logger.info(
        "Imported bundle '%s' (id=%s) from export version %s",
        bundle.name,
        bundle.id,
        data.get("export_version", "unknown"),
    )
    return bundle


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _serialize_bundle(b: AgentBundle) -> dict:
    """Serialize bundle the instance."""
    d: dict = {
        "id": b.id,
        "name": b.name,
        "description": b.description,
        "llm_profile_id": b.llm_profile_id,
        "role_type_id": b.role_type_id,
        "tone_profile_id": b.tone_profile_id,
        "tags": b.tags,
        "is_active": b.is_active,
        "model_params": b.model_params,
    }
    if b.composition:
        d["composition"] = b.composition.model_dump()
    return d


def _serialize_llm_profile(p: BlueprintLLMProfile) -> dict:
    """Serialize llm profile the instance."""
    return {
        "id": p.id,
        "name": p.name,
        "profile_type": p.profile_type,
        "provider": p.provider,
        "model": p.model,
        "api_base": p.api_base,
        "api_key_env": p.api_key_env,
        "max_tokens": p.max_tokens,
        "context_window": p.context_window,
        "temperature": p.temperature,
        "timeout": p.timeout,
        "cost_per_1k_input": p.cost_per_1k_input,
        "cost_per_1k_output": p.cost_per_1k_output,
        "description": p.description,
        "tags": p.tags,
        "protocol": p.protocol,
        "a2a_endpoint": p.a2a_endpoint,
        "a2a_timeout": p.a2a_timeout,
        "fallback_llm_profile_id": p.fallback_llm_profile_id,
        "a2a_config": p.a2a_config,
        "service_eligible": p.service_eligible,
    }


def _serialize_role_type(rt: RoleType) -> dict:
    """Serialize role type the instance."""
    return {
        "id": rt.id,
        "name": rt.name,
        "description": rt.description,
        "icon": rt.icon,
        "color": rt.color,
        "default_max_rounds": rt.default_max_rounds,
        "default_consensus_threshold": rt.default_consensus_threshold,
        "category": rt.category,
        "tags": rt.tags,
        "is_active": rt.is_active,
    }


def _serialize_tone_profile(tp: ToneProfile | None) -> dict | None:
    """Serialize tone profile the instance."""
    if tp is None:
        return None
    return {
        "id": tp.id,
        "name": tp.name,
        "description": tp.description,
        "style": tp.style,
        "formality": tp.formality,
        "verbosity": tp.verbosity,
        "emotional_valence": tp.emotional_valence,
        "rhetorical_mode": tp.rhetorical_mode,
        "custom_instructions": tp.custom_instructions,
        "is_system": tp.is_system,
    }


# ---------------------------------------------------------------------------
# Import entity helpers
# ---------------------------------------------------------------------------


def _resolve_id(original_id: str, id_map: dict[str, str], strategy: str, exists: bool) -> str:
    """Resolve an entity ID based on conflict strategy."""
    if original_id in id_map:
        return id_map[original_id]

    if not exists:
        id_map[original_id] = original_id
        return original_id

    if strategy == ImportConflictStrategy.SKIP:
        return original_id
    elif strategy == ImportConflictStrategy.OVERWRITE:
        id_map[original_id] = original_id
        return original_id
    else:  # RENAME
        new_id = f"{original_id}_{uuid.uuid4().hex[:6]}"
        id_map[original_id] = new_id
        return new_id


def _import_llm_profile(
    raw: dict,
    repo: BlueprintRepository,
    strategy: str,
    id_map: dict[str, str],
) -> BlueprintLLMProfile:
    """Import llm profile the instance."""
    existing = repo.get_llm_profile(raw["id"])
    resolved_id = _resolve_id(raw["id"], id_map, strategy, existing is not None)

    if existing and strategy == ImportConflictStrategy.SKIP:
        return existing

    profile = BlueprintLLMProfile(
        id=resolved_id,
        name=raw["name"],
        profile_type=raw.get("profile_type", "text"),
        provider=raw["provider"],
        model=raw["model"],
        api_base=raw.get("api_base"),
        api_key_env=raw.get("api_key_env", "OPENROUTER_API_KEY"),
        max_tokens=raw.get("max_tokens", 4096),
        context_window=raw.get("context_window"),
        temperature=raw.get("temperature", 0.7),
        timeout=raw.get("timeout", 600),
        cost_per_1k_input=raw.get("cost_per_1k_input"),
        cost_per_1k_output=raw.get("cost_per_1k_output"),
        description=raw.get("description", ""),
        tags=raw.get("tags", []),
        protocol=raw.get("protocol", "litellm"),
        a2a_endpoint=raw.get("a2a_endpoint"),
        a2a_timeout=raw.get("a2a_timeout", 120),
        fallback_llm_profile_id=raw.get("fallback_llm_profile_id"),
        a2a_config=raw.get("a2a_config", {}),
        service_eligible=raw.get("service_eligible", True),
    )

    # Persist when the profile is new, was renamed (so it lives under a
    # new ID), or when the caller asked to overwrite the existing one.
    # The previous logic skipped the save on RENAME, leaving the bundle
    # pointing at an LLM profile that was never inserted.
    if not existing or strategy == ImportConflictStrategy.OVERWRITE or resolved_id != raw["id"]:
        repo.save_llm_profile(profile)
    return profile


def _import_tone_profile(
    raw: dict,
    repo: BlueprintRepository,
    strategy: str,
    id_map: dict[str, str],
) -> ToneProfile:
    """Import tone profile the instance."""
    existing = repo.get_tone_profile(raw["id"])
    resolved_id = _resolve_id(raw["id"], id_map, strategy, existing is not None)

    if existing and strategy == ImportConflictStrategy.SKIP:
        return existing

    tp = ToneProfile(
        id=resolved_id,
        name=raw["name"],
        description=raw.get("description", ""),
        style=raw.get("style", "neutral"),
        formality=raw.get("formality", 0.5),
        verbosity=raw.get("verbosity", "normal"),
        emotional_valence=raw.get("emotional_valence", 0.5),
        rhetorical_mode=raw.get("rhetorical_mode", "none"),
        custom_instructions=raw.get("custom_instructions"),
        is_system=raw.get("is_system", False),
    )

    if not existing or strategy == ImportConflictStrategy.OVERWRITE or resolved_id != raw["id"]:
        repo.save_tone_profile(tp)
    return tp


def _import_bundle_entity(
    raw: dict,
    repo: BlueprintRepository,
    strategy: str,
    id_map: dict[str, str],
    resolved_llm_id: str,
    resolved_role_type_id: str,
    resolved_tone_id: str | None,
) -> AgentBundle:
    """Import bundle entity the instance."""
    existing = repo.get_bundle(raw["id"])
    resolved_id = _resolve_id(raw["id"], id_map, strategy, existing is not None)

    if existing and strategy == ImportConflictStrategy.SKIP:
        return existing

    composition = None
    composition_raw = raw.get("composition")
    if composition_raw:
        composition = BundleComposition(**composition_raw)

    bundle = AgentBundle(
        id=resolved_id,
        name=raw["name"],
        description=raw.get("description", ""),
        llm_profile_id=resolved_llm_id,
        role_type_id=resolved_role_type_id,
        tone_profile_id=resolved_tone_id,
        composition=composition,
        tags=raw.get("tags", []),
        is_active=raw.get("is_active", True),
        model_params=raw.get("model_params", {}),
    )

    if not existing or strategy == ImportConflictStrategy.OVERWRITE or resolved_id != raw["id"]:
        repo.save_bundle(bundle)
    return bundle
