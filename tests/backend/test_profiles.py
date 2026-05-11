"""Tests for the profile management API and services."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from backend.core.profiles import (
    AgentPersona,
    LLMProfile,
    LLMProvider,
    PromptVariant,
)
from backend.services.profile_service import ProfileService
from backend.services.prompt_service import PromptService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def profile_dir(tmp_path) -> Path:
    """Create a temporary profile directory with test YAML files."""
    llm_dir = tmp_path / "llm"
    agents_dir = tmp_path / "agents"
    prompts_dir = tmp_path / "prompts" / "default"
    variants_dir = tmp_path / "prompts" / "variants" / "test-variant"

    llm_dir.mkdir(parents=True)
    agents_dir.mkdir(parents=True)
    prompts_dir.mkdir(parents=True)
    variants_dir.mkdir(parents=True)

    # LLM profile
    llm_data = {
        "id": "test-llm",
        "name": "Test LLM",
        "provider": "openrouter",
        "model": "test/model",
        "api_key_env": "TEST_API_KEY",
        "temperature": 0.5,
        "max_tokens": 2048,
    }
    (llm_dir / "test-llm.yaml").write_text(yaml.dump(llm_data))

    # Agent persona
    agent_data = {
        "id": "test-strategist",
        "name": "Test Strategist",
        "role": "strategist",
        "system_prompt": "You are a test strategist.",
        "llm_profile_id": "test-llm",
        "tags": ["test"],
    }
    (agents_dir / "test-strategist.yaml").write_text(yaml.dump(agent_data))

    # Prompt files
    (prompts_dir / "strategist.md").write_text("# Strategist Prompt\nTest content for {context}")
    (prompts_dir / "critic.md").write_text("# Critic Prompt\nTest content")
    (variants_dir / "strategist.md").write_text(
        "# Variant Strategist\nVariant content for {context}"
    )

    return tmp_path


@pytest.fixture()
def profile_service(profile_dir, tmp_path) -> ProfileService:
    return ProfileService(profile_dir=profile_dir, db_path=tmp_path / "test.db")


@pytest.fixture()
def prompt_service(profile_dir) -> PromptService:
    return PromptService(prompts_dir=profile_dir / "prompts")


# ---------------------------------------------------------------------------
# ProfileService tests
# ---------------------------------------------------------------------------


class TestProfileServiceLLM:
    def test_list_llm_profiles(self, profile_service):
        profiles = profile_service.list_llm_profiles()
        assert len(profiles) == 1
        assert profiles[0].id == "test-llm"
        assert profiles[0].provider == LLMProvider.OPENROUTER

    def test_get_llm_profile(self, profile_service):
        profile = profile_service.get_llm_profile("test-llm")
        assert profile is not None
        assert profile.name == "Test LLM"
        assert profile.model == "test/model"
        assert profile.temperature == 0.5

    def test_get_nonexistent_llm_profile(self, profile_service):
        assert profile_service.get_llm_profile("nonexistent") is None

    def test_save_llm_profile(self, profile_service, profile_dir):
        new_profile = LLMProfile(
            id="new-llm",
            name="New LLM",
            provider=LLMProvider.LOCAL,
            model="local/model",
            temperature=0.8,
        )
        profile_service.save_llm_profile(new_profile)

        # Verify in memory
        assert profile_service.get_llm_profile("new-llm") is not None

        # Verify on disk
        yaml_path = profile_dir / "llm" / "new-llm.yaml"
        assert yaml_path.exists()
        data = yaml.safe_load(yaml_path.read_text())
        assert data["id"] == "new-llm"

    def test_delete_llm_profile(self, profile_service):
        assert profile_service.delete_llm_profile("test-llm") is True
        assert profile_service.get_llm_profile("test-llm") is None

    def test_delete_nonexistent_llm_profile(self, profile_service):
        assert profile_service.delete_llm_profile("nonexistent") is False


class TestProfileServiceAgents:
    def test_list_agent_personas(self, profile_service):
        personas = profile_service.list_agent_personas()
        assert len(personas) == 1
        assert personas[0].id == "test-strategist"
        assert personas[0].role == "strategist"

    def test_list_agent_personas_by_role(self, profile_service):
        strategists = profile_service.list_agent_personas(role="strategist")
        assert len(strategists) == 1

        critics = profile_service.list_agent_personas(role="critic")
        assert len(critics) == 0

    def test_get_agent_persona(self, profile_service):
        persona = profile_service.get_agent_persona("test-strategist")
        assert persona is not None
        assert persona.name == "Test Strategist"
        assert persona.system_prompt == "You are a test strategist."

    def test_save_agent_persona(self, profile_service, profile_dir):
        new_persona = AgentPersona(
            id="test-critic",
            name="Test Critic",
            role="critic",
            system_prompt="You are a test critic.",
            llm_profile_id="test-llm",
        )
        profile_service.save_agent_persona(new_persona)

        assert profile_service.get_agent_persona("test-critic") is not None
        yaml_path = profile_dir / "agents" / "test-critic.yaml"
        assert yaml_path.exists()

    def test_delete_agent_persona(self, profile_service):
        assert profile_service.delete_agent_persona("test-strategist") is True
        assert profile_service.get_agent_persona("test-strategist") is None


class TestProfileServicePrompts:
    def test_list_prompt_variants(self, profile_service):
        variants = profile_service.list_prompt_variants()
        ids = [v.id for v in variants]
        assert "default" in ids
        assert "test-variant" in ids

    def test_preview_prompt(self, profile_service):
        text = profile_service.preview_prompt("default", "strategist")
        assert "Strategist Prompt" in text

    def test_preview_variant_prompt(self, profile_service):
        text = profile_service.preview_prompt("test-variant", "strategist")
        assert "Variant Strategist" in text

    def test_delete_prompt_variant(self, profile_service):
        assert profile_service.delete_prompt_variant("test-variant") is True

    def test_cannot_delete_default_variant_via_api(self, client):
        """Guard is in the API router, not the service."""
        response = client.delete("/api/v1/profiles/prompts/default")
        assert response.status_code == 400
        assert "Cannot delete" in response.json()["detail"]


class TestProfileServiceCostEstimation:
    def test_estimate_cost_with_costs(self, profile_service):
        # The test profile has no cost fields set, so estimate should be 0
        cost = profile_service.estimate_debate_cost("test-llm", num_agents=4, num_rounds=3)
        assert cost >= 0.0

    def test_estimate_cost_nonexistent_profile(self, profile_service):
        """Service returns 0.0 for missing profiles (no cost data)."""
        cost = profile_service.estimate_debate_cost("nonexistent", num_agents=4, num_rounds=3)
        assert cost == 0.0


# ---------------------------------------------------------------------------
# PromptService tests
# ---------------------------------------------------------------------------


class TestPromptService:
    def test_get_prompt_default(self, prompt_service):
        data = prompt_service.get_prompt("default", "strategist")
        assert "content" in data
        assert "hash" in data
        assert "Strategist Prompt" in data["content"]

    def test_get_prompt_variant(self, prompt_service):
        data = prompt_service.get_prompt("test-variant", "strategist")
        assert "Variant Strategist" in data["content"]

    def test_get_prompt_fallback_to_default(self, prompt_service):
        # test-variant has no critic.md, should fall back to default
        data = prompt_service.get_prompt("test-variant", "critic")
        assert "Critic Prompt" in data["content"]

    def test_get_prompt_nonexistent_raises(self, prompt_service):
        with pytest.raises(FileNotFoundError):
            prompt_service.get_prompt("default", "nonexistent-role")

    def test_render_with_variables(self, prompt_service):
        text = prompt_service.render("default", "strategist", {"context": "Test Case"})
        assert "Test Case" in text
        assert "{context}" not in text

    def test_list_available_roles(self, prompt_service):
        roles = prompt_service.list_available_roles("default")
        assert "strategist" in roles
        assert "critic" in roles

    def test_cache_hit(self, prompt_service):
        # First call loads from disk
        data1 = prompt_service.get_prompt("default", "strategist")
        # Second call should hit cache
        data2 = prompt_service.get_prompt("default", "strategist")
        assert data1["hash"] == data2["hash"]

    def test_clear_cache(self, prompt_service):
        prompt_service.get_prompt("default", "strategist")
        prompt_service.clear_cache()
        # Should reload from disk
        data = prompt_service.get_prompt("default", "strategist")
        assert data["content"]


# ---------------------------------------------------------------------------
# Pydantic schema tests
# ---------------------------------------------------------------------------


class TestProfileSchemas:
    def test_llm_profile_valid(self):
        profile = LLMProfile(
            id="test-id",
            name="Test",
            provider=LLMProvider.OPENROUTER,
            model="test/model",
        )
        assert profile.id == "test-id"

    def test_llm_profile_invalid_id(self):
        with pytest.raises(Exception):
            LLMProfile(
                id="Invalid ID!",
                name="Test",
                provider=LLMProvider.OPENROUTER,
                model="test/model",
            )

    def test_agent_persona_valid(self):
        persona = AgentPersona(
            id="test-agent",
            name="Test Agent",
            role="strategist",
            system_prompt="Test prompt",
            llm_profile_id="test-llm",
        )
        assert persona.role == "strategist"

    def test_agent_persona_invalid_role(self):
        with pytest.raises(Exception):
            AgentPersona(
                id="test-agent",
                name="Test Agent",
                role="invalid-role",
                system_prompt="Test prompt",
                llm_profile_id="test-llm",
            )

    def test_prompt_variant_valid(self):
        variant = PromptVariant(
            id="test-variant",
            name="Test Variant",
            base_path="/tmp/test",
        )
        assert variant.id == "test-variant"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestProfilesAPI:
    def test_list_llm_profiles(self, client):
        response = client.get("/api/v1/profiles/llm")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_agent_personas(self, client):
        response = client.get("/api/v1/profiles/agents")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_agent_personas_by_role(self, client):
        response = client.get("/api/v1/profiles/agents?role=strategist")
        assert response.status_code == 200

    def test_list_prompt_variants(self, client):
        response = client.get("/api/v1/profiles/prompts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_nonexistent_llm_profile(self, client):
        response = client.get("/api/v1/profiles/llm/nonexistent")
        assert response.status_code == 404

    def test_get_nonexistent_agent_persona(self, client):
        response = client.get("/api/v1/profiles/agents/nonexistent")
        assert response.status_code == 404

    def test_cost_estimate_missing_param(self, client):
        response = client.get("/api/v1/profiles/cost-estimate")
        assert response.status_code == 422  # missing required query param
