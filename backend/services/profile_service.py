"""Profile service — loads, validates, and manages profiles.

LLM profiles are loaded from ``blueprints.db`` (Single Source of Truth).
YAML files in ``profiles/llm/`` serve as seed/import source — on first
startup they are imported into the DB; subsequent startups read from DB.

Agent personas, prompt variants, and prompt content are all stored in
``blueprints.db`` as Single Source of Truth, with YAML files as backup.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path

import yaml

from backend.core.profiles import (
    AgentPersona,
    LLMProfile,
    PromptVariant,
)
from backend.models.project import ProjectConfig

logger = logging.getLogger(__name__)

# Default profile directory (relative to project root)
_DEFAULT_PROFILE_DIR = Path("profiles")


class ProfileService:
    """Manages LLM profiles, agent personas, and prompt variants.

    LLM profiles use ``blueprints.db`` as Single Source of Truth.
    YAML files in ``profiles/llm/`` serve as seed source — on first
    startup they are imported into the DB; subsequent reads come from DB.
    Writes go to both DB (primary) and YAML (backup).

    Agent personas, prompt variants, and prompt content use DB as SSOT.

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
        self.profile_dir = Path(profile_dir)
        self._project_config = project_config
        self._db_path = Path(db_path) if db_path else Path("data/blueprints.db")
        self._llm_cache: dict[str, LLMProfile] = {}
        self._agent_cache: dict[str, AgentPersona] = {}
        self._prompt_cache: dict[str, PromptVariant] = {}
        self._prompt_content_cache: dict[str, dict] = {}  # db:variant/role/lang → {content, hash, path}
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def ensure_loaded(self) -> None:
        """Load all profiles from disk if not already loaded."""
        if self._loaded:
            return
        self._load_llm_profiles()
        self._load_agent_personas()
        self._load_prompt_variants()
        self._loaded = True
        logger.info(
            "Profiles loaded: %d LLM, %d agents, %d prompt variants",
            len(self._llm_cache),
            len(self._agent_cache),
            len(self._prompt_cache),
        )

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

    def _load_agent_personas(self) -> None:
        """Load agent personas from DB (primary) with YAML fallback."""
        if self._load_agent_personas_from_db():
            return
        self._load_agent_personas_from_yaml()
        self._seed_agent_personas_to_db()

    def _load_agent_personas_from_db(self) -> bool:
        """Load agent personas from role_definitions in blueprints.db."""
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            db_roles = repo.list_role_definitions(limit=500)
            if db_roles:
                for rd in db_roles:
                    try:
                        # Resolve prompt content for system_prompt
                        system_prompt = ""
                        if rd.prompt_template_id:
                            pt = repo.get_prompt_template(rd.prompt_template_id)
                            if pt:
                                system_prompt = pt.content
                        legacy = rd.to_legacy(
                            system_prompt=system_prompt,
                            llm_profile_id="",  # will be resolved at runtime
                        )
                        self._agent_cache[legacy.id] = legacy
                    except Exception:
                        logger.exception("Failed to convert DB role definition %s", rd.id)
                logger.info(
                    "Loaded %d agent personas from DB",
                    len(self._agent_cache),
                )
                return True
        except Exception:
            logger.warning(
                "Could not load agent personas from DB, falling back to YAML",
                exc_info=True,
            )
        return False

    def _load_agent_personas_from_yaml(self) -> None:
        """Load agent personas from YAML files (legacy/seed source)."""
        agents_dir = self.profile_dir / "agents"
        if not agents_dir.is_dir():
            logger.warning("Agent personas directory not found: %s", agents_dir)
            return
        for yaml_file in sorted(agents_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                persona = AgentPersona(**data)
                self._agent_cache[persona.id] = persona
            except Exception:
                logger.exception("Failed to load agent persona from %s", yaml_file)

    def _seed_agent_personas_to_db(self) -> None:
        """Seed loaded YAML agent personas into the DB."""
        if not self._agent_cache:
            return
        try:
            from backend.blueprints.models import RoleDefinition
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            count = 0
            for persona in self._agent_cache.values():
                try:
                    rd = RoleDefinition.from_legacy(persona)
                    repo.save_role_definition(rd)
                    count += 1
                except Exception:
                    logger.exception("Failed to seed agent persona %s to DB", persona.id)
            logger.info("Seeded %d agent personas from YAML into DB", count)
        except Exception:
            logger.exception("Failed to seed agent personas to DB")

    def _load_prompt_variants(self) -> None:
        """Load prompt variants from DB (primary) with YAML fallback."""
        if self._load_prompt_variants_from_db():
            return
        self._load_prompt_variants_from_yaml()
        self._seed_prompts_to_db()

    def _load_prompt_variants_from_db(self) -> bool:
        """Load prompt variants from prompt_templates in blueprints.db."""
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            db_templates = repo.list_prompt_templates(limit=500)
            if db_templates:
                # Group by variant to build PromptVariant entries
                variants: dict[str, list] = {}
                for pt in db_templates:
                    variants.setdefault(pt.variant, []).append(pt)

                for variant_name, templates in variants.items():
                    # Store templates in a special dict keyed by variant/role
                    # PromptVariant.base_path is unused for DB mode
                    self._prompt_cache[variant_name] = PromptVariant(
                        id=variant_name,
                        name=variant_name.capitalize(),
                        base_path=f"db:{variant_name}",
                        description=f"DB prompt variant: {variant_name}",
                    )
                    # Cache template content for PromptService DB mode
                    for pt in templates:
                        cache_key = f"db:{variant_name}/{pt.role}/{pt.language}"
                        self._prompt_content_cache[cache_key] = {
                            "content": pt.content,
                            "hash": pt.content_hash,
                            "path": f"db:{pt.id}",
                        }
                logger.info(
                    "Loaded %d prompt variants (%d templates) from DB",
                    len(variants),
                    len(db_templates),
                )
                return True
        except Exception:
            logger.warning(
                "Could not load prompt variants from DB, falling back to YAML",
                exc_info=True,
            )
        return False

    def _load_prompt_variants_from_yaml(self) -> None:
        """Load prompt variants from YAML/MD files (legacy/seed source)."""
        prompts_dir = self.profile_dir / "prompts"
        if not prompts_dir.is_dir():
            logger.warning("Prompts directory not found: %s", prompts_dir)
            return

        # Default variant
        default_dir = prompts_dir / "default"
        if default_dir.is_dir():
            self._prompt_cache["default"] = PromptVariant(
                id="default",
                name="Default",
                base_path=str(default_dir),
                description="Default prompt set",
            )

        # Named variants from subdirectories
        variants_dir = prompts_dir / "variants"
        if variants_dir.is_dir():
            for variant_dir in sorted(variants_dir.iterdir()):
                if variant_dir.is_dir():
                    self._prompt_cache[variant_dir.name] = PromptVariant(
                        id=variant_dir.name,
                        name=variant_dir.name.capitalize(),
                        base_path=str(variant_dir),
                        description=f"Prompt variant: {variant_dir.name}",
                    )

    def _seed_prompts_to_db(self) -> None:
        """Seed loaded YAML prompt files into the DB and populate content cache."""
        try:
            from backend.blueprints.models import PromptTemplate
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            count = 0
            for variant_name, variant in self._prompt_cache.items():
                base = Path(variant.base_path)
                if not base.is_dir():
                    continue
                for md_file in sorted(base.glob("*.md")):
                    try:
                        role = md_file.stem
                        content = md_file.read_text(encoding="utf-8")
                        template = PromptTemplate(
                            id=f"{variant_name}-{role}",
                            name=f"{variant_name}/{role}",
                            role=role,
                            content=content,
                            variant=variant_name,
                            source_path=str(md_file),
                        )
                        repo.save_prompt_template(template)
                        # Populate content cache for same-session DB access
                        cache_key = f"db:{variant_name}/{role}/de"
                        self._prompt_content_cache[cache_key] = {
                            "content": content,
                            "hash": template.content_hash,
                            "path": f"db:{template.id}",
                        }
                        count += 1
                    except Exception:
                        logger.exception(
                            "Failed to seed prompt %s/%s to DB",
                            variant_name,
                            md_file.name,
                        )
            logger.info("Seeded %d prompt templates from YAML into DB", count)
        except Exception:
            logger.exception("Failed to seed prompts to DB")

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Merge helpers (global + project override)
    # ------------------------------------------------------------------

    def _merged_llm_profiles(self) -> dict[str, LLMProfile]:
        """Return global LLM profiles merged with project overrides."""
        self.ensure_loaded()
        merged = dict(self._llm_cache)
        if self._project_config and self._project_config.llm_profiles:
            merged.update(self._project_config.llm_profiles)
        return merged

    def _merged_agent_personas(self) -> dict[str, AgentPersona]:
        """Return global agent personas merged with project overrides."""
        self.ensure_loaded()
        merged = dict(self._agent_cache)
        if self._project_config and self._project_config.agent_personas:
            merged.update(self._project_config.agent_personas)
        return merged

    def _merged_prompt_variants(self) -> dict[str, PromptVariant]:
        """Return global prompt variants merged with project overrides."""
        self.ensure_loaded()
        merged = dict(self._prompt_cache)
        if self._project_config and self._project_config.prompt_variants:
            merged.update(self._project_config.prompt_variants)
        return merged

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    def list_llm_profiles(self) -> list[LLMProfile]:
        self.ensure_loaded()
        return list(self._merged_llm_profiles().values())

    def get_llm_profile(self, profile_id: str) -> LLMProfile | None:
        self.ensure_loaded()
        return self._merged_llm_profiles().get(profile_id)

    def save_llm_profile(self, profile: LLMProfile) -> LLMProfile:
        """Save an LLM profile to DB (primary) and YAML (backup)."""
        self.ensure_loaded()

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
    # Agent Personas
    # ------------------------------------------------------------------

    def list_agent_personas(self, role: str | None = None) -> list[AgentPersona]:
        self.ensure_loaded()
        personas = list(self._merged_agent_personas().values())
        if role:
            personas = [p for p in personas if p.role == role]
        return personas

    def get_agent_persona(self, persona_id: str) -> AgentPersona | None:
        self.ensure_loaded()
        return self._merged_agent_personas().get(persona_id)

    def save_agent_persona(self, persona: AgentPersona) -> AgentPersona:
        """Save an agent persona to DB (primary) and YAML (backup)."""
        self.ensure_loaded()

        # Write to DB (primary)
        try:
            from backend.blueprints.models import RoleDefinition
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            rd = RoleDefinition.from_legacy(persona)
            repo.save_role_definition(rd)
        except Exception:
            logger.exception("Failed to save agent persona %s to DB", persona.id)

        # Write to YAML (backup)
        try:
            agents_dir = self.profile_dir / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            yaml_path = agents_dir / f"{persona.id}.yaml"
            yaml_path.write_text(
                yaml.dump(
                    persona.model_dump(mode="json"),
                    default_flow_style=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.exception("Failed to save agent persona %s to YAML", persona.id)

        # Update cache
        self._agent_cache[persona.id] = persona
        logger.info("Agent persona saved: %s", persona.id)
        return persona

    def delete_agent_persona(self, persona_id: str) -> bool:
        """Delete an agent persona from DB and YAML."""
        self.ensure_loaded()
        if persona_id not in self._agent_cache:
            return False

        # Delete from DB
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            repo.delete_role_definition(persona_id)
        except Exception:
            logger.exception("Failed to delete agent persona %s from DB", persona_id)

        # Delete from YAML
        try:
            yaml_path = self.profile_dir / "agents" / f"{persona_id}.yaml"
            if yaml_path.exists():
                yaml_path.unlink()
        except Exception:
            logger.exception("Failed to delete agent persona %s YAML file", persona_id)

        # Update cache
        del self._agent_cache[persona_id]
        logger.info("Agent persona deleted: %s", persona_id)
        return True

    # ------------------------------------------------------------------
    # Prompt Variants
    # ------------------------------------------------------------------

    def list_prompt_variants(self) -> list[PromptVariant]:
        self.ensure_loaded()
        return list(self._merged_prompt_variants().values())

    def get_prompt_variant(self, variant_id: str) -> PromptVariant | None:
        self.ensure_loaded()
        return self._merged_prompt_variants().get(variant_id)

    def get_prompt_content(
        self,
        variant: str,
        role: str,
        language: str = "de",
    ) -> dict | None:
        """Get prompt content, checking DB cache first, then filesystem.

        Returns a dict with keys: content, hash, path — or None if not found.
        """
        self.ensure_loaded()

        # 1. Check DB content cache (primary — SSOT)
        cache_key = f"db:{variant}/{role}/{language}"
        cached = self._prompt_content_cache.get(cache_key)
        if cached:
            return cached

        # 2. Try language-specific file first, then base
        candidates = []
        if language and language != "de":
            candidates.append(f"{role}-{language}.md")
        candidates.append(f"{role}.md")

        variant_obj = self._prompt_cache.get(variant)
        if variant_obj and variant_obj.base_path.startswith("db:"):
            # DB-only variant with no filesystem — check default variant filesystem
            pass
        elif variant_obj:
            base = Path(variant_obj.base_path)
            for name in candidates:
                path = base / name
                if path.exists():
                    content = path.read_text(encoding="utf-8")
                    return {
                        "content": content,
                        "hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                        "path": str(path),
                    }

        # 3. Fallback to default variant filesystem
        default_obj = self._prompt_cache.get("default")
        if default_obj and not default_obj.base_path.startswith("db:"):
            base = Path(default_obj.base_path)
            for name in candidates:
                path = base / name
                if path.exists():
                    logger.warning(
                        "Prompt %s/%s not found, falling back to default/%s",
                        variant,
                        role,
                        name,
                    )
                    content = path.read_text(encoding="utf-8")
                    return {
                        "content": content,
                        "hash": hashlib.sha256(content.encode()).hexdigest()[:16],
                        "path": str(path),
                    }

        return None

    def preview_prompt(self, variant_id: str, agent_role: str) -> str:
        """Load and return the prompt text for a given variant and agent role.

        Checks DB content cache first, then filesystem.
        Falls back to the default variant if the requested variant or role
        prompt is not found.
        """
        self.ensure_loaded()

        # Try DB-first via get_prompt_content
        data = self.get_prompt_content(variant_id, agent_role)
        if data:
            return data["content"]

        raise FileNotFoundError(f"Prompt not found for role '{agent_role}' in variant '{variant_id}'")

    def delete_prompt_variant(self, variant_id: str) -> bool:
        """Delete a prompt variant from DB and filesystem."""
        self.ensure_loaded()
        if variant_id not in self._prompt_cache:
            return False

        # Delete from DB
        try:
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            templates = repo.list_prompt_templates(variant=variant_id, limit=500)
            for pt in templates:
                repo.delete_prompt_template(pt.id)
            logger.info(
                "Deleted %d prompt templates from DB for variant %s",
                len(templates),
                variant_id,
            )
        except Exception:
            logger.exception("Failed to delete prompt variant %s from DB", variant_id)

        # Delete from filesystem
        variant = self._prompt_cache[variant_id]
        variant_path = Path(variant.base_path)
        if variant_path.is_dir():
            shutil.rmtree(variant_path)

        # Remove from content cache
        keys_to_remove = [k for k in self._prompt_content_cache if k.startswith(f"db:{variant_id}/")]
        for k in keys_to_remove:
            del self._prompt_content_cache[k]

        del self._prompt_cache[variant_id]
        logger.info("Prompt variant deleted: %s", variant_id)
        return True

    def create_prompt_variant(
        self,
        variant_id: str,
        name: str,
        description: str = "",
        prompts: dict[str, str] | None = None,
    ) -> PromptVariant:
        """Create a new prompt variant with per-role prompt content.

        Writes to both DB (primary) and filesystem (backup).

        Args:
            variant_id: Unique identifier (lowercase, alphanumeric + hyphens).
            name: Display name.
            description: Optional description.
            prompts: Dict of role → prompt content (e.g. {"strategist": "...", "critic": "..."}).

        Returns:
            The created PromptVariant.

        Raises:
            ValueError: If variant_id already exists.
        """
        self.ensure_loaded()
        if variant_id in self._prompt_cache:
            raise ValueError(f"Prompt variant '{variant_id}' already exists")

        # Write to DB (primary)
        try:
            from backend.blueprints.models import PromptTemplate
            from backend.blueprints.repository import BlueprintRepository

            repo = BlueprintRepository(self._db_path)
            if prompts:
                for role, content in prompts.items():
                    template = PromptTemplate(
                        id=f"{variant_id}-{role}",
                        name=f"{variant_id}/{role}",
                        role=role,
                        content=content,
                        variant=variant_id,
                    )
                    repo.save_prompt_template(template)
                    # Update content cache
                    cache_key = f"db:{variant_id}/{role}/de"
                    self._prompt_content_cache[cache_key] = {
                        "content": content,
                        "hash": template.content_hash,
                        "path": f"db:{template.id}",
                    }
        except Exception:
            logger.exception("Failed to save prompt variant %s to DB", variant_id)

        # Write to filesystem (backup)
        variants_dir = self.profile_dir / "prompts" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        variant_dir = variants_dir / variant_id
        variant_dir.mkdir(parents=True, exist_ok=True)

        if prompts:
            for role, content in prompts.items():
                prompt_file = variant_dir / f"{role}.md"
                prompt_file.write_text(content, encoding="utf-8")

        variant = PromptVariant(
            id=variant_id,
            name=name,
            base_path=str(variant_dir),
            description=description,
        )
        self._prompt_cache[variant_id] = variant
        logger.info("Prompt variant created: %s at %s", variant_id, variant_dir)
        return variant

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
        self._agent_cache.clear()
        self._prompt_cache.clear()
        self._prompt_content_cache.clear()
        self._loaded = False
        self.ensure_loaded()
