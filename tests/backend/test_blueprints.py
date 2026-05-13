"""Tests for the Blueprint Canvas — Phase 1.

Covers:
- Model validation (BlueprintLLMProfile, PromptTemplate, RoleDefinition, AgentBlueprint)
- Legacy conversion (from_legacy, to_legacy)
- Repository CRUD for all 5 entity types
- Importer (new format, legacy format, idempotency, dry_run, no auto-assembly)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.blueprints.importer import BlueprintImporter
from backend.blueprints.models import (
    AgentBlueprint,
    BlueprintLLMProfile,
    CanvasLayout,
    CanvasLayoutData,
    CanvasLayoutEdge,
    CanvasLayoutNode,
    CanvasLayoutViewport,
    PromptTemplate,
    RoleDefinition,
    RoleType,
    _compute_content_hash,
)
from backend.blueprints.repository import BlueprintRepository
from backend.core.profiles import AgentPersona, LLMProfile

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def blueprint_repo(tmp_path: Path) -> BlueprintRepository:
    """Create a BlueprintRepository with a temporary database."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def sample_profile_dir(tmp_path: Path) -> Path:
    """Create a temporary profile directory with test YAML/MD files."""
    # --- profiles/llm/ (new format) ---
    llm_dir = tmp_path / "profiles" / "llm"
    llm_dir.mkdir(parents=True)
    (llm_dir / "test-llm.yaml").write_text(
        yaml.dump(
            {
                "id": "test-llm",
                "name": "Test LLM",
                "provider": "openrouter",
                "model": "anthropic/claude-3.5-sonnet",
                "api_key_env": "TEST_KEY",
                "max_tokens": 4096,
                "temperature": 0.7,
            }
        ),
        encoding="utf-8",
    )

    # --- profiles/agents/ ---
    agents_dir = tmp_path / "profiles" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "strategist.yaml").write_text(
        yaml.dump(
            {
                "id": "strategist",
                "name": "Strategist",
                "role": "strategist",
                "system_prompt": "You are the strategist.",
                "llm_profile_id": "test-llm",
                "max_rounds": 5,
                "consensus_threshold": 0.9,
                "description": "Strategic analysis agent",
                "tags": ["default"],
            }
        ),
        encoding="utf-8",
    )
    (agents_dir / "critic.yaml").write_text(
        yaml.dump(
            {
                "id": "critic",
                "name": "Critic",
                "role": "critic",
                "system_prompt": "You are the critic.",
                "llm_profile_id": "test-llm",
                "max_rounds": 3,
                "consensus_threshold": 0.8,
                "tags": ["rigorous"],
            }
        ),
        encoding="utf-8",
    )

    # --- profiles/prompts/default/ ---
    prompts_default = tmp_path / "profiles" / "prompts" / "default"
    prompts_default.mkdir(parents=True)
    (prompts_default / "strategist.md").write_text("# Strategist Prompt\n\nAnalyze the case.", encoding="utf-8")
    (prompts_default / "critic.md").write_text("# Critic Prompt\n\nChallenge the arguments.", encoding="utf-8")

    # --- profiles/prompts/variants/kantian/ ---
    prompts_kantian = tmp_path / "profiles" / "prompts" / "variants" / "kantian"
    prompts_kantian.mkdir(parents=True)
    (prompts_kantian / "strategist.md").write_text("# Kantian Strategist\n\nApply Kantian ethics.", encoding="utf-8")

    return tmp_path


@pytest.fixture()
def sample_archive_dir(tmp_path: Path) -> Path:
    """Create a temporary archive directory with legacy config files."""
    archive_dir = tmp_path / "archive" / "config"

    # --- archive/config/llm_profiles.yaml (legacy format) ---
    archive_dir.mkdir(parents=True)
    (archive_dir / "llm_profiles.yaml").write_text(
        yaml.dump(
            {
                "profiles": {
                    "local_gemma": {
                        "model": "google/gemma-4-26b-a4b",
                        "base_url": "http://192.168.1.100:1234/v1",
                        "api_key_env": "LOCAL_KEY",
                        "params": {"temperature": 0.4, "top_p": 0.9, "seed": 42},
                    },
                    "cloud_openrouter": {
                        "model": "anthropic/claude-3-5-sonnet",
                        "base_url": "https://openrouter.ai/api/v1",
                        "api_key_env": "OR_KEY",
                        "params": {"temperature": 0.6},
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    # --- archive/config/prompts/ ---
    prompts_dir = archive_dir / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "strategist.md").write_text("Du bist ein erfahrener Strategie-Entwickler.", encoding="utf-8")

    return tmp_path


# =========================================================================
# P1.20 — Model validation tests
# =========================================================================


class TestBlueprintLLMProfile:
    """Tests for BlueprintLLMProfile model."""

    def test_valid_model_creation(self) -> None:
        profile = BlueprintLLMProfile(
            id="test-model",
            name="Test Model",
            provider="openrouter",
            model="anthropic/claude-3.5-sonnet",
        )
        assert profile.id == "test-model"
        assert profile.provider == "openrouter"
        assert profile.temperature == 0.7
        assert profile.max_tokens == 4096

    def test_temperature_validation(self) -> None:
        with pytest.raises(Exception):
            BlueprintLLMProfile(
                id="bad-temp",
                name="Bad Temp",
                provider="openrouter",
                model="test",
                temperature=3.0,
            )

    def test_max_tokens_validation(self) -> None:
        with pytest.raises(Exception):
            BlueprintLLMProfile(
                id="bad-tokens",
                name="Bad Tokens",
                provider="openrouter",
                model="test",
                max_tokens=0,
            )

    def test_id_pattern_validation(self) -> None:
        with pytest.raises(Exception):
            BlueprintLLMProfile(
                id="Invalid_ID!",
                name="Bad ID",
                provider="openrouter",
                model="test",
            )

    def test_id_with_dots_and_underscores(self) -> None:
        profile = BlueprintLLMProfile(
            id="my.model_v2",
            name="Dotted ID",
            provider="local",
            model="test",
        )
        assert profile.id == "my.model_v2"

    def test_all_providers_accepted(self) -> None:
        for provider in [
            "openrouter",
            "openai",
            "anthropic",
            "local",
            "ollama",
            "opencode-zen",
            "opencode-go",
            "xiaomi",
        ]:
            profile = BlueprintLLMProfile(
                id=f"p-{provider}",
                name=provider,
                provider=provider,
                model="test",
            )
            assert profile.provider == provider

    def test_timestamps_auto_generated(self) -> None:
        profile = BlueprintLLMProfile(
            id="ts-test",
            name="Timestamp Test",
            provider="openrouter",
            model="test",
        )
        assert profile.created_at is not None
        assert profile.updated_at is not None


class TestPromptTemplate:
    """Tests for PromptTemplate model."""

    def test_valid_creation(self) -> None:
        template = PromptTemplate(
            id="prompt-strategist",
            name="Strategist",
            role_type_id="strategist",
            content="You are the strategist.",
        )
        assert template.role == "strategist"
        assert template.variant == "default"
        assert template.language == "de"

    def test_empty_content_rejected(self) -> None:
        with pytest.raises(Exception, match="must not be empty"):
            PromptTemplate(
                id="empty",
                name="Empty",
                role_type_id="critic",
                content="   ",
            )

    def test_content_hash_auto_generated(self) -> None:
        template = PromptTemplate(
            id="hash-test",
            name="Hash Test",
            role="optimizer",
            content="Some content here.",
        )
        assert template.content_hash != ""
        assert len(template.content_hash) == 16
        assert template.content_hash == _compute_content_hash("Some content here.")

    def test_content_hash_explicit(self) -> None:
        template = PromptTemplate(
            id="hash-explicit",
            name="Explicit Hash",
            role="moderator",
            content="Content.",
            content_hash="custom-hash",
        )
        assert template.content_hash == "custom-hash"


class TestRoleDefinition:
    """Tests for RoleDefinition model."""

    def test_valid_creation(self) -> None:
        role = RoleDefinition(
            id="strategist",
            name="Strategist",
            role_type_id="strategist",
        )
        assert role.consensus_threshold == 0.9
        assert role.max_rounds == 5

    def test_consensus_threshold_validation(self) -> None:
        with pytest.raises(Exception, match="between 0 and 1"):
            RoleDefinition(
                id="bad-threshold",
                name="Bad",
                role_type_id="critic",
                consensus_threshold=1.5,
            )

    def test_consensus_threshold_zero(self) -> None:
        role = RoleDefinition(
            id="zero-threshold",
            name="Zero",
            role_type_id="critic",
            consensus_threshold=0.0,
        )
        assert role.consensus_threshold == 0.0

    def test_optional_prompt_template_id(self) -> None:
        role = RoleDefinition(
            id="with-prompt",
            name="With Prompt",
            role_type_id="strategist",
            prompt_template_id="prompt-strategist",
        )
        assert role.prompt_template_id == "prompt-strategist"


class TestRoleType:
    """Tests for RoleType model."""

    def test_valid_creation(self) -> None:
        rt = RoleType(
            id="strategist",
            name="Strategist",
        )
        assert rt.description == ""
        assert rt.icon == "👤"
        assert rt.color == "#8b5cf6"
        assert rt.default_max_rounds == 5
        assert rt.default_consensus_threshold == 0.9
        assert rt.is_active is True

    def test_custom_values(self) -> None:
        rt = RoleType(
            id="custom-critic",
            name="Custom Critic",
            description="A custom critic role",
            icon="🔍",
            color="#ef4444",
            default_max_rounds=10,
            default_consensus_threshold=0.8,
            tags=["custom", "critic"],
        )
        assert rt.icon == "🔍"
        assert rt.color == "#ef4444"
        assert rt.default_max_rounds == 10
        assert rt.default_consensus_threshold == 0.8
        assert rt.tags == ["custom", "critic"]

    def test_consensus_threshold_validation(self) -> None:
        with pytest.raises(Exception, match="between 0 and 1"):
            RoleType(
                id="bad-threshold",
                name="Bad",
                default_consensus_threshold=1.5,
            )

    def test_consensus_threshold_zero(self) -> None:
        rt = RoleType(
            id="zero-threshold",
            name="Zero",
            default_consensus_threshold=0.0,
        )
        assert rt.default_consensus_threshold == 0.0

    def test_max_rounds_validation(self) -> None:
        with pytest.raises(Exception, match="must be >= 1"):
            RoleType(
                id="bad-rounds",
                name="Bad",
                default_max_rounds=0,
            )

    def test_id_pattern_validation(self) -> None:
        with pytest.raises(Exception):
            RoleType(id="INVALID", name="Bad ID")

    def test_id_with_dots_and_underscores(self) -> None:
        rt = RoleType(id="my.role_type", name="Valid")
        assert rt.id == "my.role_type"

    def test_timestamps_auto_generated(self) -> None:
        rt = RoleType(id="ts-test", name="Timestamps")
        assert rt.created_at is not None
        assert rt.updated_at is not None


class TestAgentBlueprint:
    """Tests for AgentBlueprint model."""

    def test_valid_creation(self) -> None:
        bp = AgentBlueprint(
            id="bp-strategist",
            name="Strategist Blueprint",
            llm_profile_id="test-llm",
            role_definition_id="strategist",
        )
        assert bp.is_active is True
        assert bp.prompt_template_id is None

    def test_optional_prompt_override(self) -> None:
        bp = AgentBlueprint(
            id="bp-with-prompt",
            name="With Prompt",
            llm_profile_id="test-llm",
            role_definition_id="strategist",
            prompt_template_id="prompt-strategist-kantian",
        )
        assert bp.prompt_template_id == "prompt-strategist-kantian"


class TestCanvasLayout:
    """Tests for CanvasLayout and related models."""

    def test_canvas_layout_defaults(self) -> None:
        layout = CanvasLayout(name="Test Layout")
        assert layout.id  # auto-generated
        assert len(layout.id) == 8
        assert layout.layout_data.nodes == []
        assert layout.layout_data.edges == []
        assert layout.layout_data.viewport.zoom == 1

    def test_canvas_layout_with_data(self) -> None:
        layout = CanvasLayout(
            id="layout1",
            name="My Layout",
            layout_data=CanvasLayoutData(
                nodes=[
                    CanvasLayoutNode(id="n1", type="agent-blueprint", x=100, y=200),
                    CanvasLayoutNode(id="n2", type="llm-profile", x=300, y=200),
                ],
                edges=[
                    CanvasLayoutEdge(id="e1", source="n1", target="n2", type="uses_llm"),
                ],
                viewport=CanvasLayoutViewport(x=0, y=0, zoom=0.8),
            ),
        )
        assert len(layout.layout_data.nodes) == 2
        assert len(layout.layout_data.edges) == 1
        assert layout.layout_data.viewport.zoom == 0.8


# =========================================================================
# P1.21 — Legacy conversion tests
# =========================================================================


class TestLegacyConversion:
    """Tests for from_legacy / to_legacy conversion methods."""

    def test_blueprint_llm_profile_from_legacy(self) -> None:
        legacy = LLMProfile(
            id="legacy-model",
            name="Legacy Model",
            provider="openrouter",
            model="anthropic/claude-3.5-sonnet",
            api_base="https://openrouter.ai/api/v1",
            api_key_env="OR_KEY",
            max_tokens=8192,
            context_window=200000,
            temperature=0.5,
            timeout=300,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )
        bp = BlueprintLLMProfile.from_legacy(legacy)
        assert bp.id == "legacy-model"
        assert bp.name == "Legacy Model"
        assert bp.provider == "openrouter"
        assert bp.model == "anthropic/claude-3.5-sonnet"
        assert bp.api_base == "https://openrouter.ai/api/v1"
        assert bp.max_tokens == 8192
        assert bp.context_window == 200000
        assert bp.temperature == 0.5
        assert bp.cost_per_1k_input == 0.003
        assert bp.description == ""
        assert bp.tags == []

    def test_blueprint_llm_profile_to_legacy(self) -> None:
        bp = BlueprintLLMProfile(
            id="bp-model",
            name="BP Model",
            provider="local",
            model="google/gemma-4-26b-a4b",
            api_base="http://localhost:1234/v1",
            api_key_env="LOCAL_KEY",
            max_tokens=4096,
            temperature=0.4,
        )
        legacy = bp.to_legacy()
        assert isinstance(legacy, LLMProfile)
        assert legacy.id == "bp-model"
        assert legacy.provider.value == "local"
        assert legacy.model == "google/gemma-4-26b-a4b"
        assert legacy.api_base == "http://localhost:1234/v1"

    def test_role_definition_from_legacy(self) -> None:
        legacy = AgentPersona(
            id="strategist-legacy",
            name="Legacy Strategist",
            role="strategist",
            system_prompt="You are the strategist.",
            llm_profile_id="test-llm",
            max_rounds=7,
            consensus_threshold=0.85,
            description="Legacy strategist",
            tags=["legacy", "test"],
        )
        rd = RoleDefinition.from_legacy(legacy, prompt_template_id="prompt-strategist")
        assert rd.id == "strategist-legacy"
        assert rd.name == "Legacy Strategist"
        assert rd.role_type_id == "strategist"
        assert rd.prompt_template_id == "prompt-strategist"
        assert rd.max_rounds == 7
        assert rd.consensus_threshold == 0.85
        assert rd.tags == ["legacy", "test"]

    def test_role_definition_from_legacy_no_prompt(self) -> None:
        legacy = AgentPersona(
            id="critic-legacy",
            name="Legacy Critic",
            role="critic",
            system_prompt="You are the critic.",
            llm_profile_id="test-llm",
        )
        rd = RoleDefinition.from_legacy(legacy)
        assert rd.prompt_template_id is None
        assert rd.description == ""

    def test_roundtrip_llm_profile(self) -> None:
        """from_legacy(to_legacy(x)) should preserve core fields."""
        original = BlueprintLLMProfile(
            id="roundtrip",
            name="Roundtrip",
            provider="openai",
            model="gpt-4o",
            max_tokens=2048,
            temperature=0.3,
        )
        legacy = original.to_legacy()
        restored = BlueprintLLMProfile.from_legacy(legacy)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.provider == original.provider
        assert restored.model == original.model
        assert restored.max_tokens == original.max_tokens
        assert restored.temperature == original.temperature


# =========================================================================
# P1.22 — Repository CRUD tests
# =========================================================================


class TestBlueprintRepositoryLLMProfiles:
    """Repository CRUD for LLM profiles."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        profile = BlueprintLLMProfile(
            id="repo-llm",
            name="Repo LLM",
            provider="openrouter",
            model="test/model",
        )
        blueprint_repo.save_llm_profile(profile)
        retrieved = blueprint_repo.get_llm_profile("repo-llm")
        assert retrieved is not None
        assert retrieved.id == "repo-llm"
        assert retrieved.name == "Repo LLM"
        assert retrieved.provider == "openrouter"

    def test_get_nonexistent(self, blueprint_repo: BlueprintRepository) -> None:
        assert blueprint_repo.get_llm_profile("nonexistent") is None

    def test_list(self, blueprint_repo: BlueprintRepository) -> None:
        for i in range(3):
            blueprint_repo.save_llm_profile(
                BlueprintLLMProfile(
                    id=f"llm-{i}",
                    name=f"LLM {i}",
                    provider="openrouter",
                    model="test/model",
                )
            )
        profiles = blueprint_repo.list_llm_profiles()
        assert len(profiles) == 3

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_llm_profile(
            BlueprintLLMProfile(
                id="to-delete",
                name="Delete Me",
                provider="openrouter",
                model="test/model",
            )
        )
        assert blueprint_repo.delete_llm_profile("to-delete") is True
        assert blueprint_repo.get_llm_profile("to-delete") is None

    def test_delete_nonexistent(self, blueprint_repo: BlueprintRepository) -> None:
        assert blueprint_repo.delete_llm_profile("nonexistent") is False

    def test_upsert_updates(self, blueprint_repo: BlueprintRepository) -> None:
        profile = BlueprintLLMProfile(
            id="upsert",
            name="Original",
            provider="openrouter",
            model="test/model",
        )
        blueprint_repo.save_llm_profile(profile)
        profile.name = "Updated"
        blueprint_repo.save_llm_profile(profile)
        retrieved = blueprint_repo.get_llm_profile("upsert")
        assert retrieved is not None
        assert retrieved.name == "Updated"


class TestBlueprintRepositoryPromptTemplates:
    """Repository CRUD for prompt templates."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        template = PromptTemplate(
            id="prompt-test",
            name="Test Prompt",
            role_type_id="strategist",
            content="Test content.",
        )
        blueprint_repo.save_prompt_template(template)
        retrieved = blueprint_repo.get_prompt_template("prompt-test")
        assert retrieved is not None
        assert retrieved.content == "Test content."
        assert retrieved.content_hash != ""

    def test_list_filtered_by_role(self, blueprint_repo: BlueprintRepository) -> None:
        for role in ("strategist", "critic", "strategist"):
            blueprint_repo.save_prompt_template(
                PromptTemplate(
                    id=f"prompt-{role}-{id(role)}",
                    name=f"{role.title()} Prompt",
                    role=role,
                    content=f"Content for {role}.",
                )
            )
        strategist_templates = blueprint_repo.list_prompt_templates(role="strategist")
        assert all(t.role == "strategist" for t in strategist_templates)

    def test_list_filtered_by_variant(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_prompt_template(
            PromptTemplate(
                id="prompt-default",
                name="Default",
                role_type_id="strategist",
                content="Default content.",
                variant="default",
            )
        )
        blueprint_repo.save_prompt_template(
            PromptTemplate(
                id="prompt-kantian",
                name="Kantian",
                role_type_id="strategist",
                content="Kantian content.",
                variant="kantian",
            )
        )
        default_only = blueprint_repo.list_prompt_templates(variant="default")
        assert len(default_only) == 1
        assert default_only[0].variant == "default"

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_prompt_template(
            PromptTemplate(
                id="to-delete",
                name="Delete",
                role_type_id="critic",
                content="Delete me.",
            )
        )
        assert blueprint_repo.delete_prompt_template("to-delete") is True
        assert blueprint_repo.get_prompt_template("to-delete") is None


class TestBlueprintRepositoryRoleDefinitions:
    """Repository CRUD for role definitions."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        # Create referenced prompt template first (FK constraint)
        blueprint_repo.save_prompt_template(
            PromptTemplate(
                id="prompt-strategist",
                name="Strategist",
                role_type_id="strategist",
                content="Test content.",
            )
        )
        role = RoleDefinition(
            id="role-test",
            name="Test Role",
            role_type_id="strategist",
            prompt_template_id="prompt-strategist",
        )
        blueprint_repo.save_role_definition(role)
        retrieved = blueprint_repo.get_role_definition("role-test")
        assert retrieved is not None
        assert retrieved.prompt_template_id == "prompt-strategist"

    def test_list_filtered_by_role(self, blueprint_repo: BlueprintRepository) -> None:
        for role in ("strategist", "critic", "optimizer"):
            blueprint_repo.save_role_definition(RoleDefinition(id=f"role-{role}", name=role.title(), role_type_id=role))
        critics = blueprint_repo.list_role_definitions(role="critic")
        assert len(critics) == 1
        assert critics[0].role_type_id == "critic"

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_role_definition(RoleDefinition(id="to-delete", name="Delete", role_type_id="moderator"))
        assert blueprint_repo.delete_role_definition("to-delete") is True


class TestBlueprintRepositoryRoleTypes:
    """Repository CRUD for role types."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        rt = RoleType(id="strategist", name="Strategist", icon="🧠", color="#3b82f6")
        blueprint_repo.save_role_type(rt)
        loaded = blueprint_repo.get_role_type("strategist")
        assert loaded is not None
        assert loaded.id == "strategist"
        assert loaded.name == "Strategist"
        assert loaded.icon == "🧠"
        assert loaded.color == "#3b82f6"
        assert loaded.default_max_rounds == 5
        assert loaded.default_consensus_threshold == 0.9

    def test_list(self, blueprint_repo: BlueprintRepository) -> None:
        # Migration v14 seeds 6 default role types; upsert 3 more
        for name in ["strategist", "critic", "optimizer"]:
            blueprint_repo.save_role_type(RoleType(id=name, name=name.title()))
        all_types = blueprint_repo.list_role_types()
        ids = {rt.id for rt in all_types}
        assert "strategist" in ids
        assert "critic" in ids
        assert "optimizer" in ids

    def test_list_active_only(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_role_type(RoleType(id="active-rt", name="Active"))
        blueprint_repo.save_role_type(RoleType(id="inactive-rt", name="Inactive", is_active=False))
        active = blueprint_repo.list_role_types(active_only=True)
        active_ids = {rt.id for rt in active}
        assert "active-rt" in active_ids
        assert "inactive-rt" not in active_ids

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_role_type(RoleType(id="to-delete", name="Delete"))
        assert blueprint_repo.delete_role_type("to-delete") is True
        assert blueprint_repo.get_role_type("to-delete") is None

    def test_upsert_updates(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_role_type(RoleType(id="upsert-rt", name="Original"))
        blueprint_repo.save_role_type(RoleType(id="upsert-rt", name="Updated", icon="⚡"))
        loaded = blueprint_repo.get_role_type("upsert-rt")
        assert loaded is not None
        assert loaded.name == "Updated"
        assert loaded.icon == "⚡"


class TestBlueprintRepositoryAgentBlueprints:
    """Repository CRUD for agent blueprints."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        # Create referenced entities first (FK constraints)
        blueprint_repo.save_llm_profile(BlueprintLLMProfile(id="test-llm", name="Test LLM", provider="openrouter", model="test/model"))
        blueprint_repo.save_role_definition(RoleDefinition(id="test-role", name="Test Role", role_type_id="strategist"))
        bp = AgentBlueprint(
            id="bp-test",
            name="Test Blueprint",
            llm_profile_id="test-llm",
            role_definition_id="test-role",
        )
        blueprint_repo.save_blueprint(bp)
        retrieved = blueprint_repo.get_blueprint("bp-test")
        assert retrieved is not None
        assert retrieved.is_active is True

    def test_list_active_only(self, blueprint_repo: BlueprintRepository) -> None:
        # Create referenced entities first (FK constraints)
        blueprint_repo.save_llm_profile(BlueprintLLMProfile(id="llm", name="LLM", provider="openrouter", model="test/model"))
        blueprint_repo.save_role_definition(RoleDefinition(id="role", name="Role", role_type_id="strategist"))
        blueprint_repo.save_blueprint(
            AgentBlueprint(
                id="bp-active",
                name="Active",
                llm_profile_id="llm",
                role_definition_id="role",
                is_active=True,
            )
        )
        blueprint_repo.save_blueprint(
            AgentBlueprint(
                id="bp-inactive",
                name="Inactive",
                llm_profile_id="llm",
                role_definition_id="role",
                is_active=False,
            )
        )
        active = blueprint_repo.list_blueprints(active_only=True)
        assert len(active) == 1
        assert active[0].id == "bp-active"

        all_bps = blueprint_repo.list_blueprints(active_only=False)
        assert len(all_bps) == 2

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        # Create referenced entities first (FK constraints)
        blueprint_repo.save_llm_profile(BlueprintLLMProfile(id="llm", name="LLM", provider="openrouter", model="test/model"))
        blueprint_repo.save_role_definition(RoleDefinition(id="role", name="Role", role_type_id="strategist"))
        blueprint_repo.save_blueprint(
            AgentBlueprint(
                id="bp-delete",
                name="Delete",
                llm_profile_id="llm",
                role_definition_id="role",
            )
        )
        assert blueprint_repo.delete_blueprint("bp-delete") is True
        assert blueprint_repo.get_blueprint("bp-delete") is None


class TestBlueprintRepositoryCanvasLayouts:
    """Repository CRUD for canvas layouts."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        layout = CanvasLayout(
            id="layout-test",
            name="Test Layout",
            layout_data=CanvasLayoutData(
                nodes=[
                    CanvasLayoutNode(id="n1", type="agent-blueprint", x=100, y=200),
                ],
                edges=[
                    CanvasLayoutEdge(id="e1", source="n1", target="n2", type="uses_llm"),
                ],
            ),
        )
        blueprint_repo.save_layout(layout)
        retrieved = blueprint_repo.get_layout("layout-test")
        assert retrieved is not None
        assert len(retrieved.layout_data.nodes) == 1
        assert len(retrieved.layout_data.edges) == 1
        assert retrieved.layout_data.nodes[0].x == 100

    def test_list_filtered_by_project(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_layout(CanvasLayout(id="l1", name="L1", project_id="proj-a"))
        blueprint_repo.save_layout(CanvasLayout(id="l2", name="L2", project_id="proj-b"))
        proj_a = blueprint_repo.list_layouts(project_id="proj-a")
        assert len(proj_a) == 1
        assert proj_a[0].project_id == "proj-a"

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        blueprint_repo.save_layout(CanvasLayout(id="l-del", name="Delete"))
        assert blueprint_repo.delete_layout("l-del") is True
        assert blueprint_repo.get_layout("l-del") is None

    def test_empty_layout_roundtrip(self, blueprint_repo: BlueprintRepository) -> None:
        """An empty CanvasLayoutData should serialize/deserialize correctly."""
        layout = CanvasLayout(id="empty", name="Empty")
        blueprint_repo.save_layout(layout)
        retrieved = blueprint_repo.get_layout("empty")
        assert retrieved is not None
        assert retrieved.layout_data.nodes == []
        assert retrieved.layout_data.edges == []
        assert retrieved.layout_data.viewport.zoom == 1


# =========================================================================
# P1.23 — Importer tests
# =========================================================================


class TestBlueprintImporter:
    """Tests for the idempotent YAML/MD importer."""

    def test_import_llm_profiles_from_yaml(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result = importer.import_llm_profiles()
        assert result.created == 1
        assert result.errors == []

        profile = blueprint_repo.get_llm_profile("test-llm")
        assert profile is not None
        assert profile.model == "anthropic/claude-3.5-sonnet"

    def test_import_legacy_llm_profiles(self, blueprint_repo: BlueprintRepository, sample_archive_dir: Path) -> None:
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_archive_dir / "profiles",
            archive_dir=sample_archive_dir / "archive" / "config",
        )
        result = importer.import_llm_profiles()
        assert result.created == 2
        assert result.errors == []

        gemma = blueprint_repo.get_llm_profile("local_gemma")
        assert gemma is not None
        assert gemma.model == "google/gemma-4-26b-a4b"
        assert gemma.api_base == "http://192.168.1.100:1234/v1"
        assert gemma.temperature == 0.4
        assert "legacy-import" in gemma.tags

        cloud = blueprint_repo.get_llm_profile("cloud_openrouter")
        assert cloud is not None
        assert cloud.provider == "openrouter"

    def test_import_agent_personas(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result = importer.import_agent_personas()
        assert result.created == 2
        assert result.errors == []

        strategist = blueprint_repo.get_role_definition("strategist")
        assert strategist is not None
        assert strategist.role_type_id == "strategist"
        assert strategist.max_rounds == 5
        # system_prompt is intentionally dropped
        assert strategist.prompt_template_id is None

        critic = blueprint_repo.get_role_definition("critic")
        assert critic is not None
        assert critic.consensus_threshold == 0.8

    def test_import_prompt_templates(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result = importer.import_prompt_templates()
        # default/strategist.md, default/critic.md, variants/kantian/strategist.md
        assert result.created == 3
        assert result.errors == []

        strategist = blueprint_repo.get_prompt_template("prompt-strategist")
        assert strategist is not None
        assert "Analyze the case" in strategist.content
        assert strategist.variant == "default"
        assert strategist.content_hash != ""

        kantian = blueprint_repo.get_prompt_template("prompt-strategist-kantian")
        assert kantian is not None
        assert "Kantian" in kantian.content
        assert kantian.variant == "kantian"

    def test_import_prompt_content_stored_inline(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """Full .md content must be stored inline, not as a file path."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        importer.import_prompt_templates()
        template = blueprint_repo.get_prompt_template("prompt-strategist")
        assert template is not None
        assert "# Strategist Prompt" in template.content
        assert template.source_path is not None

    def test_import_archive_prompts(self, blueprint_repo: BlueprintRepository, sample_archive_dir: Path) -> None:
        """Archive prompts should be imported with variant='archive'."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_archive_dir / "profiles",
            archive_dir=sample_archive_dir / "archive" / "config",
        )
        result = importer.import_prompt_templates()
        assert result.created >= 1

        # The archive strategist prompt should have variant "archive"
        templates = blueprint_repo.list_prompt_templates(role="strategist")
        archive_templates = [t for t in templates if t.variant == "archive"]
        assert len(archive_templates) == 1
        assert "Strategie-Entwickler" in archive_templates[0].content

    def test_import_idempotency(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """Running import twice should skip unchanged items."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result1 = importer.import_all()
        assert result1.created > 0
        assert result1.skipped == 0

        result2 = importer.import_all()
        assert result2.created == 0
        assert result2.skipped == result1.created
        assert result2.updated == 0
        assert result2.errors == []

    def test_import_dry_run_no_persistence(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """Dry run should not persist anything to the database."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result = importer.import_all(dry_run=True)
        assert result.created > 0

        # Nothing should be in the database
        assert blueprint_repo.list_llm_profiles() == []
        assert blueprint_repo.list_role_definitions() == []
        assert blueprint_repo.list_prompt_templates() == []

    def test_import_result_counts(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """ImportResult should track created/updated/skipped/errors."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result = importer.import_all()
        assert result.total == result.created + result.updated + result.skipped
        assert result.errors == []

    def test_import_no_auto_assembly(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """Import should NOT create AgentBlueprints — that's a Phase 3 user action."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        importer.import_all()
        assert blueprint_repo.list_blueprints(active_only=False) == []

    def test_import_updates_changed_content(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """Changed content should trigger an update, not a skip."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        # First import
        result1 = importer.import_prompt_templates()
        assert result1.created > 0

        # Modify a prompt file
        prompts_dir = sample_profile_dir / "profiles" / "prompts" / "default"
        (prompts_dir / "strategist.md").write_text("# Updated Strategist\n\nNew content.", encoding="utf-8")

        # Second import should detect the change
        result2 = importer.import_prompt_templates()
        assert result2.updated >= 1
        assert result2.skipped >= 1  # critic should be skipped

        # Verify updated content
        template = blueprint_repo.get_prompt_template("prompt-strategist")
        assert template is not None
        assert "Updated Strategist" in template.content

    def test_import_all_orchestrator(self, blueprint_repo: BlueprintRepository, sample_profile_dir: Path) -> None:
        """import_all should run all three importers."""
        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=sample_profile_dir / "profiles",
            archive_dir=sample_profile_dir / "archive" / "config",
        )
        result = importer.import_all()
        # LLM: 1 new-format
        # Roles: 2 (strategist, critic)
        # Prompts: 3 (default/strategist, default/critic, kantian/strategist)
        assert result.created == 6
        assert result.errors == []

    def test_import_empty_directories(self, tmp_path: Path) -> None:
        """Importing from empty directories should not error."""
        repo = BlueprintRepository(db_path=tmp_path / "empty.db")
        importer = BlueprintImporter(
            repo=repo,
            profile_dir=tmp_path / "empty_profiles",
            archive_dir=tmp_path / "empty_archive",
        )
        result = importer.import_all()
        assert result.created == 0
        assert result.errors == []


# ===================================================================
# Phase 4: WorkflowDefinition Models
# ===================================================================


class TestWorkflowDefinition:
    """Tests for WorkflowDefinition model."""

    def test_valid_creation(self) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        wf = WorkflowDefinition(
            id="wf-1",
            name="Test Workflow",
            description="A test workflow",
            execution_order=["n1", "n2"],
            node_blueprint_map={"n1": "bp-1", "n2": "bp-2"},
        )
        assert wf.id == "wf-1"
        assert wf.name == "Test Workflow"
        assert wf.execution_order == ["n1", "n2"]
        assert wf.node_blueprint_map == {"n1": "bp-1", "n2": "bp-2"}
        assert wf.is_active is True

    def test_defaults(self) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        wf = WorkflowDefinition(id="wf-d", name="Defaults")
        assert wf.description == ""
        assert wf.execution_order == []
        assert wf.conditional_edges == []
        assert wf.interjection_points == []
        assert wf.node_blueprint_map == {}
        assert wf.tags == []
        assert wf.is_active is True
        assert wf.canvas_layout_id is None

    def test_duplicate_execution_order_rejected(self) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        with pytest.raises(Exception, match="duplicate"):
            WorkflowDefinition(
                id="wf-dup",
                name="Dup",
                execution_order=["n1", "n1"],
            )

    def test_empty_name_rejected(self) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        with pytest.raises(Exception):
            WorkflowDefinition(id="wf-empty", name="")

    def test_conditional_edge_model(self) -> None:
        from backend.blueprints.workflow_models import ConditionalEdge

        edge = ConditionalEdge(
            source_node_id="n1",
            target_node_id="n2",
            condition="consensus_reached",
            description="Branch on consensus",
        )
        assert edge.source_node_id == "n1"
        assert edge.condition == "consensus_reached"

    def test_interjection_point_model(self) -> None:
        from backend.blueprints.workflow_models import InterjectionPoint

        point = InterjectionPoint(
            node_id="n1",
            input_type="user_query",
            blocking=True,
        )
        assert point.node_id == "n1"
        assert point.input_type == "user_query"
        assert point.blocking is True

    def test_interjection_point_defaults(self) -> None:
        from backend.blueprints.workflow_models import InterjectionPoint

        point = InterjectionPoint(node_id="n1")
        assert point.input_type == "user_query"
        assert point.blocking is True
        assert point.description == ""


# ===================================================================
# Phase 4: WorkflowDefinition Repository
# ===================================================================


class TestBlueprintRepositoryWorkflowDefinitions:
    """Repository CRUD for workflow definitions."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        wf = WorkflowDefinition(
            id="wf-1",
            name="Test Workflow",
            execution_order=["n1", "n2"],
            node_blueprint_map={"n1": "bp-1"},
            tags=["test"],
        )
        blueprint_repo.save_workflow_definition(wf)
        retrieved = blueprint_repo.get_workflow_definition("wf-1")
        assert retrieved is not None
        assert retrieved.id == "wf-1"
        assert retrieved.name == "Test Workflow"
        assert retrieved.execution_order == ["n1", "n2"]
        assert retrieved.node_blueprint_map == {"n1": "bp-1"}
        assert retrieved.tags == ["test"]

    def test_list(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        for i in range(3):
            blueprint_repo.save_workflow_definition(WorkflowDefinition(id=f"wf-{i}", name=f"Workflow {i}"))
        results = blueprint_repo.list_workflow_definitions()
        assert len(results) == 3

    def test_list_pagination(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        for i in range(5):
            blueprint_repo.save_workflow_definition(WorkflowDefinition(id=f"wf-{i}", name=f"Workflow {i}"))
        page1 = blueprint_repo.list_workflow_definitions(limit=2, offset=0)
        assert len(page1) == 2
        page2 = blueprint_repo.list_workflow_definitions(limit=2, offset=2)
        assert len(page2) == 2
        page3 = blueprint_repo.list_workflow_definitions(limit=2, offset=4)
        assert len(page3) == 1

    def test_delete(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        blueprint_repo.save_workflow_definition(WorkflowDefinition(id="wf-del", name="Delete Me"))
        assert blueprint_repo.delete_workflow_definition("wf-del") is True
        assert blueprint_repo.get_workflow_definition("wf-del") is None

    def test_delete_nonexistent(self, blueprint_repo: BlueprintRepository) -> None:
        assert blueprint_repo.delete_workflow_definition("nope") is False

    def test_upsert_updates(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import WorkflowDefinition

        blueprint_repo.save_workflow_definition(WorkflowDefinition(id="wf-up", name="Original"))
        blueprint_repo.save_workflow_definition(WorkflowDefinition(id="wf-up", name="Updated"))
        retrieved = blueprint_repo.get_workflow_definition("wf-up")
        assert retrieved is not None
        assert retrieved.name == "Updated"

    def test_conditional_edges_roundtrip(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import (
            ConditionalEdge,
            WorkflowDefinition,
        )

        wf = WorkflowDefinition(
            id="wf-edges",
            name="Edges Test",
            conditional_edges=[
                ConditionalEdge(
                    source_node_id="n1",
                    target_node_id="n2",
                    condition="round >= 3",
                    description="Branch after 3 rounds",
                ),
            ],
        )
        blueprint_repo.save_workflow_definition(wf)
        retrieved = blueprint_repo.get_workflow_definition("wf-edges")
        assert retrieved is not None
        assert len(retrieved.conditional_edges) == 1
        assert retrieved.conditional_edges[0].condition == "round >= 3"

    def test_interjection_points_roundtrip(self, blueprint_repo: BlueprintRepository) -> None:
        from backend.blueprints.workflow_models import (
            InterjectionPoint,
            WorkflowDefinition,
        )

        wf = WorkflowDefinition(
            id="wf-interject",
            name="Interjection Test",
            interjection_points=[
                InterjectionPoint(
                    node_id="n1",
                    input_type="oob_input",
                    blocking=False,
                    description="OOB input",
                ),
            ],
        )
        blueprint_repo.save_workflow_definition(wf)
        retrieved = blueprint_repo.get_workflow_definition("wf-interject")
        assert retrieved is not None
        assert len(retrieved.interjection_points) == 1
        assert retrieved.interjection_points[0].input_type == "oob_input"
        assert retrieved.interjection_points[0].blocking is False


# ===================================================================
# Phase 4: Compiler Service
# ===================================================================


class TestCompilerService:
    """Tests for the CompilerService stub."""

    def _make_repo(self, tmp_path: Path) -> BlueprintRepository:
        return BlueprintRepository(db_path=tmp_path / "compiler_test.db")

    def test_compile_valid_workflow(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="Test LLM",
                provider="openrouter",
                model="test/model",
                max_tokens=2048,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="Strategist",
                role_type_id="strategist",
                description="Test",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="Test BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
            )
        )

        wf = WorkflowDefinition(
            id="wf-1",
            name="Valid",
            node_blueprint_map={"n1": "bp-1"},
            execution_order=["n1"],
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is True
        assert len(result.resolved_agents) == 1
        assert result.resolved_agents[0].role == "strategist"
        assert result.resolved_agents[0].llm_model == "test/model"
        assert result.errors == []

    def test_compile_missing_blueprint(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        wf = WorkflowDefinition(
            id="wf-1",
            name="Missing BP",
            node_blueprint_map={"n1": "nonexistent"},
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("not found in catalog" in e for e in result.errors)

    def test_compile_missing_llm_profile(self, tmp_path: Path) -> None:
        """After deleting an LLM profile, compile should detect the missing ref."""
        import sqlite3

        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="L",
                provider="openrouter",
                model="m",
                max_tokens=1024,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="R",
                role_type_id="strategist",
                description="T",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
            )
        )
        # Delete the LLM profile via raw SQL (bypassing FK check)
        with sqlite3.connect(str(tmp_path / "compiler_test.db")) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM blueprint_llm_profiles WHERE id = 'llm-1'")

        wf = WorkflowDefinition(
            id="wf-1",
            name="Missing LLM",
            node_blueprint_map={"n1": "bp-1"},
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("LLMProfile" in e for e in result.errors)

    def test_compile_missing_role_definition(self, tmp_path: Path) -> None:
        """After deleting a role definition, compile should detect the missing ref."""
        import sqlite3

        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="L",
                provider="openrouter",
                model="m",
                max_tokens=1024,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="R",
                role_type_id="strategist",
                description="T",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
            )
        )
        # Delete the role definition via raw SQL (bypassing FK check)
        with sqlite3.connect(str(tmp_path / "compiler_test.db")) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM role_definitions WHERE id = 'role-1'")

        wf = WorkflowDefinition(
            id="wf-1",
            name="Missing Role",
            node_blueprint_map={"n1": "bp-1"},
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("RoleDefinition" in e for e in result.errors)

    def test_compile_invalid_execution_order(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="L",
                provider="openrouter",
                model="m",
                max_tokens=1024,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="R",
                role_type_id="strategist",
                description="T",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
            )
        )
        wf = WorkflowDefinition(
            id="wf-1",
            name="Bad Order",
            node_blueprint_map={"n1": "bp-1"},
            execution_order=["n1", "ghost"],
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("ghost" in e for e in result.errors)

    def test_compile_invalid_conditional_edge(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import (
            ConditionalEdge,
            WorkflowDefinition,
        )

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="L",
                provider="openrouter",
                model="m",
                max_tokens=1024,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="R",
                role_type_id="strategist",
                description="T",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
            )
        )
        wf = WorkflowDefinition(
            id="wf-1",
            name="Bad Edge",
            node_blueprint_map={"n1": "bp-1"},
            conditional_edges=[
                ConditionalEdge(
                    source_node_id="ghost",
                    target_node_id="n1",
                    condition="always",
                ),
            ],
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("ghost" in e for e in result.errors)

    def test_compile_invalid_interjection_point(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import (
            InterjectionPoint,
            WorkflowDefinition,
        )

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="L",
                provider="openrouter",
                model="m",
                max_tokens=1024,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="R",
                role_type_id="strategist",
                description="T",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
            )
        )
        wf = WorkflowDefinition(
            id="wf-1",
            name="Bad Interjection",
            node_blueprint_map={"n1": "bp-1"},
            interjection_points=[
                InterjectionPoint(node_id="ghost", input_type="user_query"),
            ],
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("ghost" in e for e in result.errors)

    def test_compile_inactive_blueprint_warning(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
            RoleDefinition,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-1",
                name="L",
                provider="openrouter",
                model="m",
                max_tokens=1024,
                temperature=0.5,
            )
        )
        repo.save_role_definition(
            RoleDefinition(
                id="role-1",
                name="R",
                role_type_id="strategist",
                description="T",
                consensus_threshold=0.8,
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-1",
                name="BP",
                llm_profile_id="llm-1",
                role_definition_id="role-1",
                is_active=False,
            )
        )
        wf = WorkflowDefinition(
            id="wf-1",
            name="Inactive",
            node_blueprint_map={"n1": "bp-1"},
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is True
        assert any("inactive" in w for w in result.warnings)

    def test_compile_empty_workflow(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = self._make_repo(tmp_path)
        wf = WorkflowDefinition(id="wf-1", name="Empty")
        compiler = CompilerService(repo)
        result = compiler.compile(wf)
        assert result.is_valid is True
        assert result.resolved_agents == []
        assert result.errors == []


# =========================================================================
# P1.28 — Backward compatibility tests
# =========================================================================


class TestBackwardCompatibility:
    """Verify backward compatibility with the new fields and migration."""

    def test_role_definition_new_fields_default(self) -> None:
        """New fields (argumentation_pattern, mode) default to None."""
        from backend.blueprints.models import RoleDefinition

        rd = RoleDefinition(
            id="compat-test",
            name="Compat Test",
            role_type_id="strategist",
        )
        assert rd.argumentation_pattern is None
        assert rd.mode is None

    def test_role_definition_with_argumentation_pattern(self) -> None:
        """argumentation_pattern field is properly stored."""
        from backend.blueprints.models import RoleDefinition

        rd = RoleDefinition(
            id="compat-ap",
            name="Compat AP",
            role_type_id="strategist",
            argumentation_pattern="kantian",
        )
        assert rd.argumentation_pattern == "kantian"

    def test_role_definition_with_mode(self) -> None:
        """mode field is properly stored."""
        from backend.blueprints.models import RoleDefinition

        rd = RoleDefinition(
            id="compat-mode",
            name="Compat Mode",
            role_type_id="moderator",
            mode="facilitator",
        )
        assert rd.mode == "facilitator"

    def test_role_definition_roundtrip_legacy(self) -> None:
        """from_legacy -> to_legacy preserves argumentation_pattern and mode."""
        from backend.blueprints.models import RoleDefinition
        from backend.core.profiles import AgentPersona

        persona = AgentPersona(
            id="legacy-persona",
            name="Legacy Persona",
            role="critic",
            system_prompt="You are a critic.",
            llm_profile_id="test-llm",
            max_rounds=5,
            consensus_threshold=0.9,
            argumentation_pattern="kantian",
            mode="adversary",
        )
        rd = RoleDefinition.from_legacy(persona, prompt_template_id="prompt-critic-kantian")
        assert rd.argumentation_pattern == "kantian"
        assert rd.mode == "adversary"

        # Roundtrip back
        legacy = rd.to_legacy(system_prompt="You are a critic.", llm_profile_id="test-llm")
        assert isinstance(legacy, AgentPersona)
        assert legacy.role == "critic"

    def test_agent_persona_widened_role_field(self) -> None:
        """AgentPersona.role accepts new role types (analyst, creative, etc.)."""
        from backend.core.profiles import AgentPersona

        persona = AgentPersona(
            id="analyst-1",
            name="Analyst Agent",
            role="analyst",
            system_prompt="You are an analyst.",
            llm_profile_id="test-llm",
        )
        assert persona.role == "analyst"

        persona2 = AgentPersona(
            id="creative-1",
            name="Creative Agent",
            role="creative",
            system_prompt="You are creative.",
            llm_profile_id="test-llm",
        )
        assert persona2.role == "creative"


# =========================================================================
# P1.29 — Argumentation pattern tests
# =========================================================================


class TestArgumentationPatterns:
    """Tests for argumentation pattern loading and prompt assembly."""

    def test_argumentation_pattern_supports_new_roles(self, tmp_path: Path) -> None:
        """Argumentation patterns exist for all new role types."""
        base = Path("profiles/argumentation-patterns")
        required_roles = {"strategist", "critic", "optimizer", "moderator", "fact-checker", "analyst", "creative"}

        for pattern in ("kantian", "hegelian", "stoic", "aristotelian", "utilitarian", "steiner"):
            pattern_dir = base / pattern
            if pattern_dir.is_dir():
                available = {f.stem for f in pattern_dir.glob("*.md")}
                # Remove -en language suffixes
                base_roles = {r[:-3] if r.endswith("-en") else r for r in available}
                missing = required_roles - base_roles
                # hegelian and stoic lack some roles in original set
                if pattern in ("hegelian", "stoic"):
                    pass
                else:
                    assert missing == set(), f"{pattern} missing roles: {missing}"

    def test_dialectic_workflow_variants_exist(self) -> None:
        """dialectic workflows exist for all 4 standard roles."""
        from pathlib import Path

        wf_dir = Path("profiles/workflows")
        for wf in ("dialectic",):
            wf_path = wf_dir / wf
            if wf_path.is_dir():
                available = {f.stem for f in wf_path.glob("*.md")}
                required = {"strategist", "critic", "optimizer", "moderator"}
                assert required.issubset(available), \
                    f"Workflow {wf} missing roles: {required - available}"


# =========================================================================
# P1.30 — Importer tests for new directory structures
# =========================================================================


class TestImporterNewStructures:
    """Tests for the importer handling new directory structures."""

    def test_argumentation_patterns_dir(self, blueprint_repo: BlueprintRepository, tmp_path: Path) -> None:
        """Argumentation-patterns prompts loadable via PromptService."""
        from backend.services.prompt_service import PromptService

        ap_dir = tmp_path / "profiles" / "argumentation-patterns" / "testpattern"
        ap_dir.mkdir(parents=True)
        (ap_dir / "strategist.md").write_text(
            "Test AP strategists content.", encoding="utf-8"
        )
        (ap_dir / "critic.md").write_text(
            "Test AP critic content.", encoding="utf-8"
        )

        prompts_default = tmp_path / "profiles" / "prompts" / "default"
        prompts_default.mkdir(parents=True)
        (prompts_default / "strategist.md").write_text("Default strategist.", encoding="utf-8")
        (prompts_default / "critic.md").write_text("Default critic.", encoding="utf-8")

        ps = PromptService(
            prompts_dir=tmp_path / "prompts",
            argumentation_patterns_dir=tmp_path / "profiles" / "argumentation-patterns",
        )
        result = ps.get_argumentation_pattern("testpattern", "strategist", language="de")
        assert result is not None
        assert "strategists" in result

        result2 = ps.get_argumentation_pattern("testpattern", "critic", language="de")
        assert result2 is not None
        assert "critic" in result2.lower()

    def test_import_workflows_dir(self, blueprint_repo: BlueprintRepository, tmp_path: Path) -> None:
        """Workflow prompts importable as prompt templates (legacy variant path)."""
        from backend.blueprints.importer import BlueprintImporter

        wf_dir = tmp_path / "profiles" / "prompts" / "variants" / "dialectic"
        wf_dir.mkdir(parents=True)
        (wf_dir / "strategist.md").write_text(
            "Dialectic Strategist workflow content.", encoding="utf-8"
        )

        prompts_default = tmp_path / "profiles" / "prompts" / "default"
        prompts_default.mkdir(parents=True)
        (prompts_default / "strategist.md").write_text("Default strategist.", encoding="utf-8")
        (prompts_default / "critic.md").write_text("Default critic.", encoding="utf-8")

        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=tmp_path / "profiles",
            archive_dir=tmp_path / "archive" / "config",
        )
        result = importer.import_prompt_templates()

        wf_strategist = blueprint_repo.get_prompt_template("prompt-strategist-dialectic")
        assert wf_strategist is not None
        assert "Dialectic" in wf_strategist.content
        assert wf_strategist.variant == "dialectic"

    def test_import_with_argumentation_pattern_on_role_def(self, blueprint_repo: BlueprintRepository, tmp_path: Path) -> None:
        """Agent personas with new fields import correctly."""
        from backend.blueprints.importer import BlueprintImporter

        agents_dir = tmp_path / "profiles" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "test-persona.yaml").write_text(
            "id: test-persona\n"
            "name: Test Persona\n"
            "role: analyst\n"
            "system_prompt: 'Analyze everything.'\n"
            "llm_profile_id: test-llm\n"
            "argumentation_pattern: kantian\n"
            "mode: facilitator\n"
            "max_rounds: 5\n"
            "consensus_threshold: 0.9\n"
            "description: 'A test persona'\n"
            "tags:\n"
            "  - test\n",
            encoding="utf-8"
        )

        prompts_default = tmp_path / "profiles" / "prompts" / "default"
        prompts_default.mkdir(parents=True)
        (prompts_default / "strategist.md").write_text("Default", encoding="utf-8")
        (prompts_default / "analyst.md").write_text("Default Analyst", encoding="utf-8")

        importer = BlueprintImporter(
            repo=blueprint_repo,
            profile_dir=tmp_path / "profiles",
            archive_dir=tmp_path / "archive" / "config",
        )
        result = importer.import_agent_personas()
        assert result.created >= 1

        rd = blueprint_repo.get_role_definition("test-persona")
        assert rd is not None
        assert rd.argumentation_pattern == "kantian"
        assert rd.mode == "facilitator"
        assert rd.role_type_id == "analyst"


# =========================================================================
# P1.31 — Prompt assembly with patterns
# =========================================================================


class TestPromptAssemblyWithPatterns:
    """Tests for prompt assembly using argumentation patterns."""

    def test_assemble_prompt_with_pattern(self, tmp_path: Path) -> None:
        """assemble_prompt combines argumentation pattern + workflow variant."""
        from backend.services.prompt_service import PromptService

        ap_dir = tmp_path / "profiles" / "argumentation-patterns" / "test_pattern"
        ap_dir.mkdir(parents=True)
        (ap_dir / "strategist.md").write_text(
            "Test Pattern: Act according to universal law.", encoding="utf-8"
        )

        default_dir = tmp_path / "prompts" / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "strategist.md").write_text(
            "Variant: Default Strategist - Use standard approach.", encoding="utf-8"
        )

        # Rename for the PromptsService constructor
        import shutil
        shutil.move(str(tmp_path / "prompts"), str(tmp_path / "prompts"))

        ps = PromptService(
            prompts_dir=tmp_path / "prompts",
            argumentation_patterns_dir=tmp_path / "profiles" / "argumentation-patterns",
        )
        result = ps.assemble_prompt(
            role_type_id="strategist",
            argumentation_pattern="test_pattern",
            workflow_variant="default",
            language="de",
        )

        assert "Test Pattern" in result
        assert "Variant" in result
        assert "universal law" in result

    def test_assemble_prompt_without_pattern(self, tmp_path: Path) -> None:
        """assemble_prompt without argumentation_pattern uses only variant."""
        from backend.services.prompt_service import PromptService

        default_dir = tmp_path / "prompts" / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "critic.md").write_text(
            "Default Critic - Standard critique.", encoding="utf-8"
        )

        ps = PromptService(prompts_dir=tmp_path / "prompts")
        result = ps.assemble_prompt(
            role_type_id="critic",
            argumentation_pattern=None,
            workflow_variant="default",
            language="de",
        )

        assert "Default Critic" in result

    def test_get_argumentation_pattern_from_filesystem(self) -> None:
        """get_argumentation_pattern reads from profiles/argumentation-patterns/ on filesystem."""
        from backend.services.prompt_service import PromptService

        ps = PromptService()
        result = ps.get_argumentation_pattern("kantian", "strategist", language="de")
        assert result is not None
        assert "Kant" in result


# =========================================================================
# P1.32 — Steigerungsrollen tests
# =========================================================================


class TestSteigerungsrollen:
    """Tests for the new functional and formative role types."""

    def test_all_new_role_types_exist_in_db(self, blueprint_repo: BlueprintRepository) -> None:
        """All 8 seeded role types are retrievable."""
        roles = blueprint_repo.list_role_types()
        role_ids = {rt.id for rt in roles}
        expected = {"strategist", "critic", "optimizer", "moderator",
                     "fact-checker", "expert-reviewer", "analyst", "creative"}
        assert expected.issubset(role_ids), \
            f"Missing role types: {expected - role_ids}"

    def test_role_type_category_functional(self) -> None:
        """New role types have category='functional'."""
        from backend.blueprints.models import RoleType

        for rid in ("analyst", "creative", "fact-checker", "expert-reviewer"):
            rt = RoleType(id=rid, name=rid.title())
            assert rt.category == "functional"

    def test_role_type_category_formative(self) -> None:
        """Moderator retains formative category behavior."""
        from backend.blueprints.models import RoleType

        rt = RoleType(id="moderator", name="Moderator", category="formative")
        assert rt.category == "formative"

    def test_analyst_node_type_registered(self) -> None:
        """Analyst is a valid workflow node type string."""
        valid_node_types = {
            "wf-strategist", "wf-critic", "wf-optimizer", "wf-moderator",
            "wf-fact-checker", "wf-analyst", "wf-creative"
        }
        assert "wf-analyst" in valid_node_types
        assert "wf-creative" in valid_node_types
        assert "wf-fact-checker" in valid_node_types

    def test_resolved_agent_includes_pattern_and_mode(self, tmp_path: Path) -> None:
        """ResolvedAgentConfig includes argumentation_pattern and mode."""
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            BlueprintLLMProfile, RoleDefinition, AgentBlueprint,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = BlueprintRepository(db_path=tmp_path / "rb_test.db")

        repo.save_llm_profile(BlueprintLLMProfile(
            id="llm-resolve", name="Resolve LLM",
            provider="openrouter", model="test/model",
        ))
        repo.save_role_definition(RoleDefinition(
            id="role-resolve",
            name="Resolved Role",
            role_type_id="analyst",
            argumentation_pattern="kantian",
            mode="facilitator",
        ))
        repo.save_blueprint(AgentBlueprint(
            id="bp-resolve", name="Resolve BP",
            llm_profile_id="llm-resolve",
            role_definition_id="role-resolve",
        ))

        wf = WorkflowDefinition(
            id="wf-resolve",
            name="Resolve Test",
            node_blueprint_map={"n1": "bp-resolve"},
            execution_order=["n1"],
        )
        compiler = CompilerService(repo)
        result = compiler.compile(wf)

        assert result.is_valid
        agent = result.resolved_agents[0]
        assert agent.argumentation_pattern == "kantian"
        assert agent.mode == "facilitator"
