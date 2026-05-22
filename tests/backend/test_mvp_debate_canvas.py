"""Tests for MVP Debate Canvas — per-agent LLM WorkflowDefinition factory."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.blueprints.models import BlueprintLLMProfile
from backend.blueprints.mvp_debate_canvas import build_mvp_debate_workflow
from backend.blueprints.repository import BlueprintRepository


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def four_llm_profiles(repo: BlueprintRepository) -> dict[str, str]:
    """Create 4 distinct LLM profiles, one per debate role."""
    profiles = {}
    for role in ("strategist", "critic", "optimizer", "moderator"):
        profile_id = f"llm-{role}"
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id=profile_id,
                name=f"{role.title()} LLM",
                provider="openai",
                model=f"gpt-4-{role}",
                api_base="http://localhost:11434/v1",
                api_key_env="OPENAI_API_KEY",
                temperature=0.7,
                max_tokens=2048,
            )
        )
        profiles[role] = profile_id
    return profiles


class TestMvpDebateCanvas:
    """Test build_mvp_debate_workflow with various configurations."""

    def test_builds_with_distinct_llm_profiles(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Each agent should be assigned its own LLM profile."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)

        assert wf.name == "MVP Debate"
        assert len(wf.nodes) == 4
        assert len(wf.edges) == 4  # 3 sequential + 1 feedback
        assert wf.entry_point == "node-strategist"

        # Verify each node has a distinct blueprint with distinct LLM
        node_map = {n.id: n for n in wf.nodes}
        for role in ("strategist", "critic", "optimizer", "moderator"):
            node = node_map[f"node-{role}"]
            assert node.agent_blueprint_id == f"mvp-{role}"
            bp = repo.get_blueprint(f"mvp-{role}")
            assert bp is not None
            assert bp.llm_profile_id == four_llm_profiles[role]

    def test_builds_with_single_llm_profile(self, repo: BlueprintRepository) -> None:
        """When no LLM profile mapping is given, use first available for all."""
        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-default",
                name="Default LLM",
                provider="local",
                model="gemma-4-26b-a4b",
                api_base="http://localhost:11434/v1",
                api_key_env="LOCAL_KEY",
                temperature=0.4,
                max_tokens=2048,
            )
        )

        build_mvp_debate_workflow(repo)

        for role in ("strategist", "critic", "optimizer", "moderator"):
            bp = repo.get_blueprint(f"mvp-{role}")
            assert bp is not None
            assert bp.llm_profile_id == "llm-default"

    def test_sequential_edges(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Edges should connect strategist→critic→optimizer→moderator."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)

        sequential = [e for e in wf.edges if e.type == "sequential"]
        assert len(sequential) == 3
        assert sequential[0].source == "node-strategist"
        assert sequential[0].target == "node-critic"
        assert sequential[1].source == "node-critic"
        assert sequential[1].target == "node-optimizer"
        assert sequential[2].source == "node-optimizer"
        assert sequential[2].target == "node-moderator"

    def test_feedback_edge(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Moderator should have a feedback edge back to strategist."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)

        feedback = [e for e in wf.edges if e.type == "feedback"]
        assert len(feedback) == 1
        assert feedback[0].source == "node-moderator"
        assert feedback[0].target == "node-strategist"

    def test_termination_conditions(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Should include max_rounds and consensus_reached conditions."""
        wf = build_mvp_debate_workflow(
            repo,
            llm_profile_ids=four_llm_profiles,
            max_rounds=3,
            consensus_threshold=0.85,
        )

        assert len(wf.termination_conditions) == 2
        tc = {t.type: t for t in wf.termination_conditions}
        assert tc["max_rounds"].value == 3
        assert tc["consensus_reached"].value == 0.85

    def test_custom_name_and_description(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Should accept custom name and description."""
        wf = build_mvp_debate_workflow(
            repo,
            llm_profile_ids=four_llm_profiles,
            name="Custom Debate",
            description="My custom debate workflow",
        )

        assert wf.name == "Custom Debate"
        assert wf.description == "My custom debate workflow"

    def test_raises_on_missing_llm_profile(self, repo: BlueprintRepository) -> None:
        """Should raise ValueError when referenced LLM profile doesn't exist."""
        with pytest.raises(ValueError, match="not found"):
            build_mvp_debate_workflow(
                repo,
                llm_profile_ids={"strategist": "nonexistent-llm"},
            )

    def test_raises_on_no_llm_profiles(self, repo: BlueprintRepository) -> None:
        """Should raise ValueError when no LLM profiles exist and none provided."""
        with pytest.raises(ValueError, match="No LLM profiles available"):
            build_mvp_debate_workflow(repo)

    def test_idempotent_blueprint_creation(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Calling build twice should not duplicate blueprints."""
        wf1 = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)
        wf2 = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)

        # Both workflows should reference the same blueprints
        for role in ("strategist", "critic", "optimizer", "moderator"):
            bp1 = repo.get_blueprint(f"mvp-{role}")
            assert bp1 is not None
            assert wf1.nodes[("strategist", "critic", "optimizer", "moderator").index(role)].agent_blueprint_id == bp1.id
            assert wf2.nodes[("strategist", "critic", "optimizer", "moderator").index(role)].agent_blueprint_id == bp1.id

    def test_node_types_match_roles(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Node types should be wf-strategist, wf-critic, wf-optimizer, wf-moderator."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)

        expected_types = {"wf-strategist", "wf-critic", "wf-optimizer", "wf-moderator"}
        actual_types = {n.type for n in wf.nodes}
        assert actual_types == expected_types
