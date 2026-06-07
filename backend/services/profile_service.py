"""Profile service — loads, validates, and manages profiles.

LLM profiles are loaded from ``blueprints.db`` (Single Source of Truth).
YAML files in ``profiles/llm/`` serve as seed/import source — on first
startup they are imported into the DB; subsequent startups read from DB.

Agent personas, prompt variants, and prompt content are all stored in
``blueprints.db`` as Single Source of Truth, with YAML files as backup.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import yaml

from backend.core.profiles import LLMProfile
from backend.models.project import ProjectConfig

logger = logging.getLogger(__name__)


# Default profile directory (relative to project root)
_DEFAULT_PROFILE_DIR = Path("profiles")


class ProfileService:
    """Manages LLM profiles.

    LLM profiles use ``blueprints.db`` as Single Source of Truth.
    YAML files in ``profiles/llm/`` serve as seed source — on first
    startup they are imported into the DB; subsequent reads come from DB.
    Writes go to both DB (primary) and YAML (backup).

    Supports project-scoped overrides via ``project_config``.  When a
    ``ProjectConfig`` is provided, its profile dictionaries are merged
    with the global profiles using the rule: same ID → project wins.
    """

    def __init__(
        self,
        profile_dir: Path | str = _DEFAULT_PROFILE_DIR,
        project_config: ProjectConfig | None = None,
        db_path: Path | str | None = None,
    ):
        """Initialise ProfileService."""
        self.profile_dir = Path(profile_dir)
        self._project_config = project_config
        self._db_path = Path(db_path) if db_path else Path("data/blueprints.db")
        self._llm_cache: dict[str, LLMProfile] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def ensure_loaded(self) -> None:
        """Load all profiles from disk if not already loaded."""
        if self._loaded:
            return
        self._load_llm_profiles()
        self._loaded = True
        logger.info("Profiles loaded: %d LLM profiles", len(self._llm_cache))

    def _load_llm_profiles(self) -> None:
        """Load LLM profiles from DB (primary) with YAML fallback.

        On first startup (DB empty), YAML files are imported into the DB.
        On subsequent startups, the DB is the authoritative source.
        """
        # Try loading from DB first
        if self._load_llm_profiles_from_db():
            return
        # Fallback: load from YAML and seed into DB
        self._load_llm_profiles_from_yaml()
        self._seed_yaml_to_db()

    def _load_llm_profiles_from_db(self) -> bool:
        """Load LLM profiles from blueprints.db. Returns True if successful."""
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            db_profiles = repo.list_llm_profiles(limit=500)
            if db_profiles:
                for bp in db_profiles:
                    try:
                        legacy = bp.to_legacy()
                        self._llm_cache[legacy.id] = legacy
                    except Exception:
                        logger.exception("Failed to convert DB LLM profile %s", bp.id)
                logger.info("Loaded %d LLM profiles from DB", len(self._llm_cache))
                return True
        except Exception:
            logger.warning(
                "Could not load LLM profiles from DB, falling back to YAML",
                exc_info=True,
            )
        return False

    def _load_llm_profiles_from_yaml(self) -> None:
        """Load LLM profiles from YAML files (legacy/seed source)."""
        llm_dir = self.profile_dir / "llm"
        if not llm_dir.is_dir():
            logger.warning("LLM profiles directory not found: %s", llm_dir)
            return
        for yaml_file in sorted(llm_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                profile = LLMProfile(**data)
                self._llm_cache[profile.id] = profile
            except Exception:
                logger.exception("Failed to load LLM profile from %s", yaml_file)

    def _seed_yaml_to_db(self) -> None:
        """Seed loaded YAML profiles into the DB (one-time migration)."""
        if not self._llm_cache:
            return
        try:
            from backend.blueprints.models import BlueprintLLMProfile
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            count = 0
            for profile in self._llm_cache.values():
                try:
                    bp = BlueprintLLMProfile.from_legacy(profile)
                    repo.save_llm_profile(bp)
                    count += 1
                except Exception:
                    logger.exception("Failed to seed LLM profile %s to DB", profile.id)
            logger.info("Seeded %d LLM profiles from YAML into DB", count)
        except Exception:
            logger.exception("Failed to seed LLM profiles to DB")

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Merge helpers (global + project override)
    # ------------------------------------------------------------------

    def _merged_llm_profiles(self) -> dict[str, LLMProfile]:
        """Return global LLM profiles merged with project overrides and module profiles.

        Priority (highest wins): project overrides > DB/cache > module defaults.
        """
        self.ensure_loaded()
        # Start with module profiles as defaults
        merged = {}
        from backend.services.module_profile_sync import get_llm_profiles_from_modules

        for mp in get_llm_profiles_from_modules():
            try:
                clean = {k: v for k, v in mp.items() if not k.startswith("_") and k in LLMProfile.model_fields}
                clean.setdefault("min_recommended_context", 1024)
                profile = LLMProfile(**clean)
                profile._source_module = mp.get("_source_module")  # type: ignore[attr-defined]
                profile._readonly = mp.get("_readonly", False)  # type: ignore[attr-defined]
                merged[profile.id] = profile
            except Exception:
                logger.warning("Failed to convert module LLM profile %s", mp.get("id", "?"))

        # DB/cache overrides module defaults
        merged.update(self._llm_cache)
        # Project overrides win
        if self._project_config and self._project_config.llm_profiles:
            merged.update(self._project_config.llm_profiles)
        return merged

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    def list_llm_profiles(self) -> list[LLMProfile]:
        """Return a list of llm profiles."""
        self.ensure_loaded()
        return list(self._merged_llm_profiles().values())

    def get_llm_profile(self, profile_id: str) -> LLMProfile | None:
        """Retrieve and return llm profile."""
        self.ensure_loaded()
        return self._merged_llm_profiles().get(profile_id)

    def save_llm_profile(self, profile: LLMProfile) -> LLMProfile:
        """Save an LLM profile to DB (primary) and YAML (backup).

        For new profiles (not in cache), auto-generates a short unique ID
        using ``uuid4().hex[:8]`` if no ID is provided.
        """
        self.ensure_loaded()

        # Auto-generate ID for new profiles
        is_new = profile.id not in self._llm_cache
        if is_new and not profile.id:
            profile.id = uuid.uuid4().hex[:8]
            logger.info("Auto-generated LLM profile ID: %s", profile.id)

        # Write to DB (primary)
        try:
            from backend.blueprints.models import BlueprintLLMProfile
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            bp = BlueprintLLMProfile.from_legacy(profile)
            repo.save_llm_profile(bp)
        except Exception:
            logger.exception("Failed to save LLM profile %s to DB", profile.id)

        # Write to YAML (backup/compatibility)
        try:
            llm_dir = self.profile_dir / "llm"
            llm_dir.mkdir(parents=True, exist_ok=True)
            yaml_path = llm_dir / f"{profile.id}.yaml"
            yaml_path.write_text(
                yaml.dump(
                    profile.model_dump(mode="json"),
                    default_flow_style=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save LLM profile %s to YAML", profile.id)

        # Update cache
        self._llm_cache[profile.id] = profile
        logger.info("LLM profile saved: %s", profile.id)
        return profile

    def delete_llm_profile(self, profile_id: str) -> bool:
        """Delete an LLM profile from DB and YAML."""
        self.ensure_loaded()
        if profile_id not in self._llm_cache:
            return False

        # Delete from DB
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            repo.delete_llm_profile(profile_id)
        except Exception:
            logger.exception("Failed to delete LLM profile %s from DB", profile_id)

        # Delete from YAML
        try:
            yaml_path = self.profile_dir / "llm" / f"{profile_id}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
        except Exception:
            logger.exception("Failed to delete LLM profile %s YAML file", profile_id)

        # Update cache
        del self._llm_cache[profile_id]
        logger.info("LLM profile deleted: %s", profile_id)
        return True

    # ------------------------------------------------------------------
    # Cost Estimation
    # ------------------------------------------------------------------

    def estimate_debate_cost(
        self,
        llm_profile_id: str,
        estimated_input_tokens: int = 2000,
        estimated_output_tokens: int = 1000,
        num_agents: int = 4,
        num_rounds: int = 3,
    ) -> float:
        """Estimate the cost of a debate run in USD."""
        profile = self.get_llm_profile(llm_profile_id)
        if not profile or not profile.cost_per_1k_input or not profile.cost_per_1k_output:
            return 0.0

        total_input = estimated_input_tokens * num_agents * num_rounds
        total_output = estimated_output_tokens * num_agents * num_rounds

        input_cost = (total_input / 1000) * profile.cost_per_1k_input
        output_cost = (total_output / 1000) * profile.cost_per_1k_output

        return round(input_cost + output_cost, 4)

    # ------------------------------------------------------------------
    # Reload
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Force reload all profiles from DB + disk."""
        self._llm_cache.clear()
        self._loaded = False
        self.ensure_loaded()
