"""Blueprint Canvas — idempotent YAML/MD importer.

Reads existing configuration files and creates Blueprint domain model
instances.  Supports:
- New-format LLM profiles from ``profiles/llm/*.yaml``
- Legacy-format LLM profiles from ``archive/config/llm_profiles.yaml``
- Agent personas from ``profiles/agents/*.yaml`` → ``RoleDefinition``
- Prompt templates from ``profiles/prompts/**/*.md`` and
  ``archive/config/prompts/*.md`` → ``PromptTemplate``

No auto-assembly of ``AgentBlueprint`` during import — visual composition
is a deliberate user interaction in Phase 3.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from backend.blueprints.models import (
    BlueprintLLMProfile,
    PromptTemplate,
    RoleDefinition,
    _compute_content_hash,
)
from backend.blueprints.repository import BlueprintRepository

logger = logging.getLogger(__name__)

_DEFAULT_PROFILE_DIR = Path("profiles")
_DEFAULT_ARCHIVE_DIR = Path("archive/config")


# ---------------------------------------------------------------------------
# Import result
# ---------------------------------------------------------------------------


@dataclass
class ImportResult:
    """Aggregated counts from an import run."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.updated + self.skipped

    def merge(self, other: ImportResult) -> None:
        """Merge another result into this one."""
        self.created += other.created
        self.updated += other.updated
        self.skipped += other.skipped
        self.errors.extend(other.errors)


# ---------------------------------------------------------------------------
# Importer
# ---------------------------------------------------------------------------


class BlueprintImporter:
    """Imports existing YAML/MD configs into the Blueprint system."""

    def __init__(
        self,
        repo: BlueprintRepository,
        profile_dir: Path = _DEFAULT_PROFILE_DIR,
        archive_dir: Path = _DEFAULT_ARCHIVE_DIR,
    ):
        self.repo = repo
        self.profile_dir = Path(profile_dir)
        self.archive_dir = Path(archive_dir)

    # ------------------------------------------------------------------
    # Orchestrator
    # ------------------------------------------------------------------

    def import_all(self, dry_run: bool = False) -> ImportResult:
        """Run full import. Returns counts of imported/skipped/error items."""
        result = ImportResult()

        llm_result = self.import_llm_profiles(dry_run=dry_run)
        result.merge(llm_result)

        role_result = self.import_agent_personas(dry_run=dry_run)
        result.merge(role_result)

        prompt_result = self.import_prompt_templates(dry_run=dry_run)
        result.merge(prompt_result)

        logger.info(
            "Import complete: created=%d updated=%d skipped=%d errors=%d",
            result.created,
            result.updated,
            result.skipped,
            len(result.errors),
        )
        return result

    # ------------------------------------------------------------------
    # LLM Profiles
    # ------------------------------------------------------------------

    def import_llm_profiles(self, dry_run: bool = False) -> ImportResult:
        """Import LLM profiles from new-format YAML and legacy archive.

        Sources:
        - ``profiles/llm/*.yaml`` (new flat format)
        - ``archive/config/llm_profiles.yaml`` (legacy nested ``profiles:`` key)
        """
        result = ImportResult()

        # --- New format: profiles/llm/*.yaml ---
        llm_dir = self.profile_dir / "llm"
        if llm_dir.is_dir():
            for yaml_file in sorted(llm_dir.glob("*.yaml")):
                try:
                    data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                    if not isinstance(data, dict):
                        result.errors.append(f"{yaml_file}: not a valid YAML dict")
                        continue
                    profile = BlueprintLLMProfile(**data)
                    self._upsert_llm_profile(profile, result, dry_run)
                except Exception as exc:
                    result.errors.append(f"{yaml_file}: {exc}")
                    logger.warning("Failed to import LLM profile from %s: %s", yaml_file, exc)

        # --- Legacy format: archive/config/llm_profiles.yaml ---
        legacy_file = self.archive_dir / "llm_profiles.yaml"
        if legacy_file.is_file():
            result.merge(self._import_legacy_llm_profiles(legacy_file, dry_run))

        return result

    def _import_legacy_llm_profiles(
        self, legacy_file: Path, dry_run: bool
    ) -> ImportResult:
        """Parse the legacy nested ``profiles:`` format."""
        result = ImportResult()
        try:
            data = yaml.safe_load(legacy_file.read_text(encoding="utf-8"))
        except Exception as exc:
            result.errors.append(f"{legacy_file}: {exc}")
            return result

        if not isinstance(data, dict) or "profiles" not in data:
            result.errors.append(f"{legacy_file}: missing 'profiles' key")
            return result

        profiles_raw = data["profiles"]
        if not isinstance(profiles_raw, dict):
            result.errors.append(f"{legacy_file}: 'profiles' is not a dict")
            return result

        for profile_id, profile_data in profiles_raw.items():
            if not isinstance(profile_data, dict):
                result.errors.append(f"{legacy_file}:{profile_id}: not a dict")
                continue
            try:
                profile = self._convert_legacy_llm_profile(profile_id, profile_data)
                self._upsert_llm_profile(profile, result, dry_run)
            except Exception as exc:
                result.errors.append(f"{legacy_file}:{profile_id}: {exc}")
                logger.warning(
                    "Failed to import legacy LLM profile %s: %s", profile_id, exc
                )

        return result

    @staticmethod
    def _convert_legacy_llm_profile(
        profile_id: str, data: dict
    ) -> BlueprintLLMProfile:
        """Convert a legacy nested profile entry to a BlueprintLLMProfile.

        Legacy format::

            profiles:
              local_gemma:
                model: "google/gemma-4-26b-a4b"
                base_url: "http://..."
                api_key_env: "YOUR_API_KEY_ENV_VAR"
                params: { temperature: 0.4, top_p: 0.9, seed: 42 }
        """
        params = data.get("params", {}) or {}
        now = datetime.now(UTC)

        # Infer provider from model name or base_url
        model = data.get("model", "")
        base_url = data.get("base_url")
        provider = _infer_provider(model, base_url)

        return BlueprintLLMProfile(
            id=profile_id,
            name=profile_id.replace("_", "-").replace(".", "-"),
            provider=provider,
            model=model,
            api_base=base_url,
            api_key_env=data.get("api_key_env", "OPENROUTER_API_KEY"),
            temperature=params.get("temperature", 0.7),
            description=f"Imported from legacy config ({legacy_file_name})",
            tags=["legacy-import"],
            created_at=now,
            updated_at=now,
        )

    def _upsert_llm_profile(
        self,
        profile: BlueprintLLMProfile,
        result: ImportResult,
        dry_run: bool,
    ) -> None:
        """Idempotent upsert: skip if unchanged, update if changed, create if new."""
        existing = self.repo.get_llm_profile(profile.id)
        if existing:
            if _llm_profiles_equal(existing, profile):
                result.skipped += 1
                return
            if not dry_run:
                profile.updated_at = datetime.now(UTC)
                self.repo.save_llm_profile(profile)
            result.updated += 1
        else:
            if not dry_run:
                self.repo.save_llm_profile(profile)
            result.created += 1

    # ------------------------------------------------------------------
    # Agent Personas → RoleDefinition
    # ------------------------------------------------------------------

    def import_agent_personas(self, dry_run: bool = False) -> ImportResult:
        """Import agent personas from ``profiles/agents/*.yaml``."""
        result = ImportResult()
        agents_dir = self.profile_dir / "agents"
        if not agents_dir.is_dir():
            return result

        for yaml_file in sorted(agents_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    result.errors.append(f"{yaml_file}: not a valid YAML dict")
                    continue
                role_def = self._yaml_to_role_definition(data, str(yaml_file))
                self._upsert_role_definition(role_def, result, dry_run)
            except Exception as exc:
                result.errors.append(f"{yaml_file}: {exc}")
                logger.warning("Failed to import agent persona from %s: %s", yaml_file, exc)

        return result

    @staticmethod
    def _yaml_to_role_definition(data: dict, source_path: str) -> RoleDefinition:
        """Convert an agent persona YAML dict to a RoleDefinition.

        The ``system_prompt`` field is intentionally dropped — prompt content
        is referenced via ``prompt_template_id`` in the Blueprint system.
        """
        now = datetime.now(UTC)
        return RoleDefinition(
            id=data.get("id", Path(source_path).stem),
            name=data.get("name", data.get("id", "Unnamed")),
            role=data.get("role", "strategist"),
            description=data.get("description", ""),
            prompt_template_id=None,  # Not linked during import
            max_rounds=data.get("max_rounds", 5),
            consensus_threshold=data.get("consensus_threshold", 0.9),
            tags=list(data.get("tags", [])),
            created_at=now,
            updated_at=now,
        )

    def _upsert_role_definition(
        self,
        role_def: RoleDefinition,
        result: ImportResult,
        dry_run: bool,
    ) -> None:
        """Idempotent upsert for role definitions."""
        existing = self.repo.get_role_definition(role_def.id)
        if existing:
            if _role_definitions_equal(existing, role_def):
                result.skipped += 1
                return
            if not dry_run:
                role_def.updated_at = datetime.now(UTC)
                self.repo.save_role_definition(role_def)
            result.updated += 1
        else:
            if not dry_run:
                self.repo.save_role_definition(role_def)
            result.created += 1

    # ------------------------------------------------------------------
    # Prompt Templates
    # ------------------------------------------------------------------

    def import_prompt_templates(self, dry_run: bool = False) -> ImportResult:
        """Import prompt templates from MD files.

        Sources:
        - ``profiles/prompts/default/*.md``
        - ``profiles/prompts/variants/*/*.md``
        - ``archive/config/prompts/*.md``
        """
        result = ImportResult()

        # --- profiles/prompts/ ---
        prompts_dir = self.profile_dir / "prompts"
        if prompts_dir.is_dir():
            for md_file in sorted(prompts_dir.rglob("*.md")):
                if md_file.name == "README.md":
                    continue
                try:
                    template = self._md_file_to_prompt_template(md_file, prompts_dir)
                    self._upsert_prompt_template(template, result, dry_run)
                except Exception as exc:
                    result.errors.append(f"{md_file}: {exc}")
                    logger.warning(
                        "Failed to import prompt template from %s: %s", md_file, exc
                    )

        # --- archive/config/prompts/ ---
        archive_prompts = self.archive_dir / "prompts"
        if archive_prompts.is_dir():
            for md_file in sorted(archive_prompts.glob("*.md")):
                try:
                    template = self._md_file_to_prompt_template(
                        md_file, archive_prompts, is_archive=True
                    )
                    self._upsert_prompt_template(template, result, dry_run)
                except Exception as exc:
                    result.errors.append(f"{md_file}: {exc}")
                    logger.warning(
                        "Failed to import archive prompt from %s: %s", md_file, exc
                    )

        return result

    @staticmethod
    def _md_file_to_prompt_template(
        md_file: Path,
        base_dir: Path,
        *,
        is_archive: bool = False,
    ) -> PromptTemplate:
        """Convert a .md file to a PromptTemplate.

        Derives role, variant, and id from the file path relative to base_dir.
        """
        content = md_file.read_text(encoding="utf-8")
        relative = md_file.relative_to(base_dir)
        parts = relative.parts  # e.g. ("default", "strategist.md") or ("strategist.md")

        # Determine role from filename
        role_name = md_file.stem  # e.g. "strategist"
        if role_name not in ("strategist", "critic", "optimizer", "moderator"):
            # Try to infer from parent directory or use filename as-is
            role_name = "strategist"  # fallback

        # Determine variant from path
        # Handle "variants/kantian/strategist.md" structure
        if len(parts) >= 3 and parts[0] == "variants":
            variant = parts[1]  # e.g. "kantian", "steiner"
        elif len(parts) > 1 and parts[0] != "default":
            variant = parts[0]  # e.g. "kantian", "steiner"
        elif is_archive:
            variant = "archive"
        else:
            variant = "default"

        # Build ID
        if variant == "default":
            template_id = f"prompt-{role_name}"
        else:
            template_id = f"prompt-{role_name}-{variant}"

        now = datetime.now(UTC)
        return PromptTemplate(
            id=template_id,
            name=f"{role_name.title()} ({variant})",
            role=role_name,  # type: ignore[arg-type]
            content=content,
            language="de",  # Default; could be detected from content
            variant=variant,
            description=f"Imported from {md_file}",
            tags=["imported"],
            source_path=str(md_file),
            content_hash=_compute_content_hash(content),
            created_at=now,
            updated_at=now,
        )

    def _upsert_prompt_template(
        self,
        template: PromptTemplate,
        result: ImportResult,
        dry_run: bool,
    ) -> None:
        """Idempotent upsert for prompt templates."""
        existing = self.repo.get_prompt_template(template.id)
        if existing:
            if existing.content_hash == template.content_hash:
                result.skipped += 1
                return
            if not dry_run:
                template.updated_at = datetime.now(UTC)
                self.repo.save_prompt_template(template)
            result.updated += 1
        else:
            if not dry_run:
                self.repo.save_prompt_template(template)
            result.created += 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Module-level constant used in legacy description string
legacy_file_name = "archive/config/llm_profiles.yaml"


def _infer_provider(model: str, base_url: str | None) -> str:
    """Infer LLM provider from model name or base URL."""
    model_lower = model.lower()
    if base_url:
        url_lower = base_url.lower()
        if "openrouter" in url_lower:
            return "openrouter"
        if "localhost" in url_lower or "127.0.0.1" in url_lower or "192.168" in url_lower:
            return "local"

    if "anthropic" in model_lower:
        return "anthropic"
    if "openai" in model_lower or "gpt" in model_lower:
        return "openai"
    if "qwen" in model_lower or "google" in model_lower or "gemma" in model_lower:
        return "openrouter"  # Most non-OpenAI/Anthropic models go through OpenRouter

    return "openrouter"  # safe default


def _llm_profiles_equal(a: BlueprintLLMProfile, b: BlueprintLLMProfile) -> bool:
    """Compare two LLM profiles ignoring timestamps."""
    return (
        a.name == b.name
        and a.provider == b.provider
        and a.model == b.model
        and a.api_base == b.api_base
        and a.api_key_env == b.api_key_env
        and a.max_tokens == b.max_tokens
        and a.context_window == b.context_window
        and a.temperature == b.temperature
        and a.timeout == b.timeout
        and a.cost_per_1k_input == b.cost_per_1k_input
        and a.cost_per_1k_output == b.cost_per_1k_output
        and a.description == b.description
        and a.tags == b.tags
    )


def _role_definitions_equal(a: RoleDefinition, b: RoleDefinition) -> bool:
    """Compare two role definitions ignoring timestamps."""
    return (
        a.name == b.name
        and a.role_type_id == b.role_type_id
        and a.description == b.description
        and a.prompt_template_id == b.prompt_template_id
        and a.max_rounds == b.max_rounds
        and a.consensus_threshold == b.consensus_threshold
        and a.tags == b.tags
    )
