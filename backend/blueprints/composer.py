"""BundleComposer — creates/edits/exports AgentBundles from modular components.

Three assembly paths exist in the system:

  Path A (BundleResolver — legacy):  role_type + role_definition + prompt_template
  Path B (PromptService — fallback): argumentation-pattern + workflow-variant
  Path C (BundleComposer — new):     agent_core + argumentation_pattern + tone_profile
                                       + prompt_modifier + llm_profile

This module implements Path C for the Builder UI (Build → Bundle Composer).

Module references (agent_core_id, argumentation_pattern_id, etc.) are stored
in the ``BundleComposition`` sub-model inside ``AgentBundle.composition``.
At resolve time, ``ComposerService.compose()`` loads content from the module
filesystem, so there is NO duplication of inline content in the database.

FUTURE: A dependency resolver from ``danwa-modules`` GitHub repo will
automatically fetch missing module dependencies during import.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.blueprints.models import AgentBundle, BundleComposition, ToneProfile
from backend.blueprints.repository import BlueprintRepository
from backend.services.composer_service import ComposerService, Composition
from backend.services.module_profile_sync import (
    get_prompt_modifiers_from_modules,
    get_tone_profiles_from_modules,
    seed_prompt_modifiers_to_db,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
MODULES_DIR = ROOT / "modules"
AGENT_BUNDLES_DIR = MODULES_DIR / "agent-bundles"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class BundleComposer:
    """Creates, reads, previews, exports, and imports composition-based AgentBundles."""

    def __init__(self, repo: BlueprintRepository | None = None):
        """Initialise BundleComposer."""
        self.repo = repo or BlueprintRepository()
        self._composer = ComposerService()
        self._modules_dir = MODULES_DIR

    # ------------------------------------------------------------------
    # Components listing
    # ------------------------------------------------------------------

    def list_components(self) -> dict[str, list[dict[str, Any]]]:
        """Return all available components across all 5 categories.

        Returns:
            Dict with keys: ``agent_cores``, ``argumentation_patterns``,
            ``tone_profiles``, ``prompt_modifiers``, ``llm_profiles``.
            Each value is a list of dicts with ``id``, ``name``, etc.
        """
        return {
            "agent_cores": ComposerService.list_agent_cores(),
            "argumentation_patterns": ComposerService.list_argumentation_patterns(),
            "tone_profiles": ComposerService.list_tone_profiles(),
            "prompt_modifiers": self._list_prompt_modifiers(),
            "llm_profiles": self._list_llm_profiles(),
        }

    @staticmethod
    def _list_prompt_modifiers() -> list[dict[str, str]]:
        """List prompt modifiers from modules, seeded into DB."""
        # Ensure DB is seeded
        seed_prompt_modifiers_to_db()
        return [
            {
                "id": m.get("id") or m.get("_source_module", ""),
                "name": m.get("name") or m.get("_module_name", ""),
                "content_preview": m.get("content", "")[:120],
                "description": m.get("description", ""),
            }
            for m in get_prompt_modifiers_from_modules()
        ]

    @staticmethod
    def _list_llm_profiles() -> list[dict[str, str]]:
        """List llm profiles the instance."""
        repo = BlueprintRepository()
        profiles = repo.list_llm_profiles(limit=200)
        return [
            {
                "id": p.id,
                "name": p.name,
                "provider": p.provider,
                "model": p.model,
                "description": p.description,
            }
            for p in profiles
        ]

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def preview(self, composition: Composition) -> str:
        """Assemble and return the concatenated system prompt without persisting.

        Args:
            composition: The four component IDs (agent_core, argumentation_pattern,
                         tone_profile, prompt_modifier).

        Returns:
            The assembled system prompt string, or empty string if no components.
        """
        return self._composer.compose(composition)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        composition: Composition,
        description: str = "",
        llm_profile_id: str = "",
    ) -> AgentBundle:
        """Create a new AgentBundle from a modular composition.

        Imports referenced module content into DB tables where needed
        (LLM profile, Tone profile, Role type) for canvas compatibility,
        but stores the ORIGINAL module IDs in ``BundleComposition``
        for dependency tracking and export.

        Args:
            name: Bundle display name.
            composition: The four component IDs.
            description: Optional description.
            llm_profile_id: LLM profile ID (references blueprint_llm_profiles).

        Returns:
            The created AgentBundle.
        """
        bundle_id = f"bundle-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)

        # Resolve LLM profile (required)
        _ = self.repo.get_llm_profile(llm_profile_id)

        # Resolve tone profile (optional — import from module if not in DB)
        tone_profile_id = None
        if composition.tone_profile_id:
            tone_profile_id = self._ensure_tone_profile(composition.tone_profile_id)

        # Resolve role type (required — derive from agent_core or use default)
        role_type_id = self._resolve_role_type_id(composition.agent_core_id)

        # Build composition model
        comp = BundleComposition(
            agent_core_id=composition.agent_core_id,
            argumentation_pattern_id=composition.argumentation_pattern_id,
            prompt_modifier_id=composition.prompt_modifier_id,
        )

        bundle = AgentBundle(
            id=bundle_id,
            name=name,
            description=description,
            llm_profile_id=llm_profile_id,
            role_type_id=role_type_id,
            tone_profile_id=tone_profile_id,
            composition=comp,
            tags=[],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.repo.save_bundle(bundle)
        logger.info(
            "Created composer bundle '%s' (id=%s) with agent_core=%s pattern=%s tone=%s modifier=%s llm=%s",
            name,
            bundle_id,
            composition.agent_core_id or "(none)",
            composition.argumentation_pattern_id or "(none)",
            composition.tone_profile_id or "(none)",
            composition.prompt_modifier_id or "(none)",
            llm_profile_id or "(none)",
        )
        return bundle

    def update(
        self,
        bundle_id: str,
        name: str | None = None,
        composition: Composition | None = None,
        description: str | None = None,
        llm_profile_id: str | None = None,
    ) -> AgentBundle | None:
        """Update an existing composer bundle's composition or metadata.

        Args:
            bundle_id: The bundle ID.
            name: New name (or None to keep).
            composition: New composition (or None to keep).
            description: New description (or None to keep).
            llm_profile_id: New LLM profile ID (or None to keep).

        Returns:
            The updated AgentBundle, or None if not found.
        """
        bundle = self.repo.get_bundle(bundle_id)
        if not bundle:
            return None

        if name is not None:
            bundle.name = name
        if description is not None:
            bundle.description = description
        if llm_profile_id is not None:
            bundle.llm_profile_id = llm_profile_id
        if composition is not None:
            bundle.composition = BundleComposition(
                agent_core_id=composition.agent_core_id,
                argumentation_pattern_id=composition.argumentation_pattern_id,
                prompt_modifier_id=composition.prompt_modifier_id,
            )
            # Re-resolve role_type if agent_core changed
            if composition.agent_core_id:
                bundle.role_type_id = self._resolve_role_type_id(composition.agent_core_id)
            # Re-resolve tone profile
            if composition.tone_profile_id:
                bundle.tone_profile_id = self._ensure_tone_profile(composition.tone_profile_id) or ""

        bundle.updated_at = datetime.now(UTC)
        self.repo.save_bundle(bundle)
        logger.info("Updated composer bundle '%s' (id=%s)", bundle.name, bundle_id)
        return bundle

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export(self, bundle_id: str) -> dict[str, Any]:
        """Export a bundle as a portable module manifest + profile.

        The export contains ONLY module ID references (no inline content).
        Dependencies are declared in ``manifest.json`` for future resolution.

        Returns:
            Dict with ``manifest`` and ``profile`` keys.
        """
        bundle = self.repo.get_bundle(bundle_id)
        if not bundle:
            raise ValueError(f"Bundle '{bundle_id}' not found")

        composition = bundle.composition
        if not composition:
            raise ValueError(f"Bundle '{bundle_id}' has no composition — use bundle_io.export_bundle instead")

        # Build dependency list from composition fields
        dependencies: dict[str, str] = {}
        if composition.agent_core_id:
            dependencies[f"agent-cores/{composition.agent_core_id}"] = ">=1.0.0"
        if composition.argumentation_pattern_id:
            dependencies[f"agent-argumentation-patterns/{composition.argumentation_pattern_id}"] = ">=1.0.0"
        if bundle.tone_profile_id:
            dependencies[f"agent-tone-profiles/{bundle.tone_profile_id}"] = ">=1.0.0"
        if composition.prompt_modifier_id:
            dependencies[f"prompt-modifiers/{composition.prompt_modifier_id}"] = ">=1.0.0"
        if bundle.llm_profile_id:
            dependencies[f"llm-profiles/{bundle.llm_profile_id.removeprefix('llm-')}"] = ">=1.0.0"

        manifest = {
            "schema_version": "2.0.0",
            "module_id": bundle.id,
            "name": {"en": bundle.name, "de": bundle.name},
            "description": {"en": bundle.description, "de": bundle.description},
            "version": "1.0.0",
            "type": "bundle",
            "category": "bundles",
            "profile_file": "profile.json",
            "profile_format": "json",
            "dependencies": dependencies,
        }

        profile = {
            "id": bundle.id,
            "name": bundle.name,
            "description": bundle.description,
            "llm_profile_id": bundle.llm_profile_id,
            "role_type_id": bundle.role_type_id,
            "tone_profile_id": bundle.tone_profile_id,
            "composition": composition.model_dump() if composition else None,
            "is_active": bundle.is_active,
        }

        return {"manifest": manifest, "profile": profile}

    def export_to_directory(self, bundle_id: str) -> Path:
        """Export a bundle to ``modules/agent-bundles/<bundle-id>/`` on disk.

        Creates ``manifest.json`` and ``profile.json``.

        Args:
            bundle_id: The bundle ID.

        Returns:
            Path to the created directory.
        """
        data = self.export(bundle_id)
        bundle_dir = AGENT_BUNDLES_DIR / bundle_id
        bundle_dir.mkdir(parents=True, exist_ok=True)

        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(json.dumps(data["manifest"], indent=2, ensure_ascii=False), encoding="utf-8")

        profile_path = bundle_dir / "profile.json"
        profile_path.write_text(json.dumps(data["profile"], indent=2, ensure_ascii=False), encoding="utf-8")

        logger.info("Exported bundle '%s' to %s", bundle_id, bundle_dir)
        return bundle_dir

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def import_from_directory(self, module_id: str) -> AgentBundle:
        """Import a bundle from ``modules/agent-bundles/<module-id>/``.

        Reads ``manifest.json`` and ``profile.json``, creates/updates the
        AgentBundle in DB.

        FUTURE: Resolve ``dependencies`` from ``danwa-modules`` repo if
        any required modules are missing locally.

        Args:
            module_id: The module directory name under ``modules/agent-bundles/``.

        Returns:
            The imported AgentBundle.

        Raises:
            FileNotFoundError: If the module directory or profile is missing.
            ValueError: If the profile data is invalid.
        """
        bundle_dir = AGENT_BUNDLES_DIR / module_id
        if not bundle_dir.is_dir():
            raise FileNotFoundError(f"Agent bundle module directory not found: {bundle_dir}")

        manifest_path = bundle_dir / "manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"manifest.json not found in {bundle_dir}")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        profile_path = bundle_dir / manifest.get("profile_file", "profile.json")
        if not profile_path.exists():
            raise FileNotFoundError(f"Profile file not found: {profile_path}")

        profile = json.loads(profile_path.read_text(encoding="utf-8"))

        # Parse composition
        composition_raw = profile.get("composition")
        if not composition_raw:
            raise ValueError(f"Bundle profile '{module_id}' has no composition")

        composition = Composition(
            agent_core_id=composition_raw.get("agent_core_id", ""),
            argumentation_pattern_id=composition_raw.get("argumentation_pattern_id", ""),
            tone_profile_id=composition_raw.get("tone_profile_id", ""),
            prompt_modifier_id=composition_raw.get("prompt_modifier_id", ""),
        )

        # Check if bundle already exists
        existing = self.repo.get_bundle(profile["id"])
        if existing:
            logger.info("Bundle '%s' already exists in DB — updating", profile["id"])
            return (
                self.update(
                    bundle_id=profile["id"],
                    name=profile.get("name", existing.name),
                    composition=composition,
                    description=profile.get("description"),
                    llm_profile_id=profile.get("llm_profile_id"),
                )
                or existing
            )

        return self.create(
            name=profile.get("name", module_id),
            composition=composition,
            description=profile.get("description", ""),
            llm_profile_id=profile.get("llm_profile_id", ""),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_tone_profile(self, module_id: str) -> str | None:
        """Import a tone profile module into DB if not already present.

        Returns the DB ID of the tone profile, or None on failure.
        """
        # Check if already in DB
        existing = self.repo.get_tone_profile(module_id)
        if existing:
            return existing.id

        # Load from module filesystem
        for mod in get_tone_profiles_from_modules():
            if mod.get("id") == module_id or mod.get("_source_module") == module_id:
                try:
                    tp = ToneProfile(
                        id=module_id,
                        name=mod.get("name", module_id),
                        description=mod.get("description", ""),
                        style=mod.get("style", "neutral"),
                        formality=mod.get("formality", 0.5),
                        verbosity=mod.get("verbosity", "normal"),
                        emotional_valence=mod.get("emotional_valence", 0.5),
                        rhetorical_mode=mod.get("rhetorical_mode", "none"),
                        custom_instructions=mod.get("custom_instructions"),
                        is_system=True,
                    )
                    self.repo.save_tone_profile(tp)
                    return tp.id
                except Exception:
                    logger.warning("Failed to import tone profile '%s' to DB", module_id, exc_info=True)
                    return None
        return None

    @staticmethod
    def _resolve_role_type_id(agent_core_id: str) -> str:
        """Derive a role_type_id from an agent_core module ID.

        E.g. ``strategist-default`` → ``strategist``, ``critic-stoic`` → ``critic``.
        Falls back to ``strategist`` if no agent_core_id.
        """
        if not agent_core_id:
            return "strategist"
        # Module IDs are like "strategist-default" or "critic-stoic"
        # Extract the role part (before first hyphen or the whole thing if no hyphen)
        parts = agent_core_id.split("-")
        if len(parts) >= 2:
            return parts[0]
        return agent_core_id
