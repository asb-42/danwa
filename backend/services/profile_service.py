"""Profile service — loads, validates, and manages YAML-based profiles.

Replaces the old ConfigManager with typed Pydantic models and a
directory-based profile structure (one file per profile).
"""

from __future__ import annotations

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

    Profiles are loaded from YAML files in the ``profiles/`` directory.
    CRUD operations write back to the same files.

    Supports project-scoped overrides via ``project_config``.  When a
    ``ProjectConfig`` is provided, its profile dictionaries are merged
    with the global profiles using the rule: same ID → project wins.
    """

    def __init__(
        self,
        profile_dir: Path | str = _DEFAULT_PROFILE_DIR,
        project_config: ProjectConfig | None = None,
    ):
        self.profile_dir = Path(profile_dir)
        self._project_config = project_config
        self._llm_cache: dict[str, LLMProfile] = {}
        self._agent_cache: dict[str, AgentPersona] = {}
        self._prompt_cache: dict[str, PromptVariant] = {}
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

    def _load_agent_personas(self) -> None:
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

    def _load_prompt_variants(self) -> None:
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
        """Save an LLM profile to disk and cache."""
        self.ensure_loaded()
        llm_dir = self.profile_dir / "llm"
        llm_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = llm_dir / f"{profile.id}.yaml"
        yaml_path.write_text(
            yaml.dump(
                profile.model_dump(mode="json"), default_flow_style=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        self._llm_cache[profile.id] = profile
        logger.info("LLM profile saved: %s", profile.id)
        return profile

    def delete_llm_profile(self, profile_id: str) -> bool:
        self.ensure_loaded()
        if profile_id not in self._llm_cache:
            return False
        yaml_path = self.profile_dir / "llm" / f"{profile_id}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()
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
        """Save an agent persona to disk and cache."""
        self.ensure_loaded()
        agents_dir = self.profile_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        yaml_path = agents_dir / f"{persona.id}.yaml"
        yaml_path.write_text(
            yaml.dump(
                persona.model_dump(mode="json"), default_flow_style=False, allow_unicode=True
            ),
            encoding="utf-8",
        )
        self._agent_cache[persona.id] = persona
        logger.info("Agent persona saved: %s", persona.id)
        return persona

    def delete_agent_persona(self, persona_id: str) -> bool:
        self.ensure_loaded()
        if persona_id not in self._agent_cache:
            return False
        yaml_path = self.profile_dir / "agents" / f"{persona_id}.yaml"
        if yaml_path.exists():
            yaml_path.unlink()
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

    def preview_prompt(self, variant_id: str, agent_role: str) -> str:
        """Load and return the prompt text for a given variant and agent role.

        Falls back to the default variant if the requested variant or role
        prompt is not found.
        """
        self.ensure_loaded()
        variant = self._prompt_cache.get(variant_id)
        if not variant:
            variant = self._prompt_cache.get("default")
        if not variant:
            raise ValueError(f"No prompt variant found (requested: {variant_id})")

        # Check for override
        if agent_role in variant.overrides:
            prompt_path = Path(variant.overrides[agent_role])
        else:
            prompt_path = Path(variant.base_path) / f"{agent_role}.md"

        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

        # Fallback to default
        default_variant = self._prompt_cache.get("default")
        if default_variant:
            fallback_path = Path(default_variant.base_path) / f"{agent_role}.md"
            if fallback_path.exists():
                return fallback_path.read_text(encoding="utf-8")

        raise FileNotFoundError(
            f"Prompt not found for role '{agent_role}' in variant '{variant_id}'"
        )

    def delete_prompt_variant(self, variant_id: str) -> bool:
        self.ensure_loaded()
        if variant_id not in self._prompt_cache:
            return False
        variant = self._prompt_cache[variant_id]
        variant_path = Path(variant.base_path)
        if variant_path.is_dir():
            shutil.rmtree(variant_path)
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

        # Create the variant directory
        variants_dir = self.profile_dir / "prompts" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        variant_dir = variants_dir / variant_id
        variant_dir.mkdir(parents=True, exist_ok=True)

        # Write prompt files for each role
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
        """Force reload all profiles from disk."""
        self._llm_cache.clear()
        self._agent_cache.clear()
        self._prompt_cache.clear()
        self._loaded = False
        self.ensure_loaded()
