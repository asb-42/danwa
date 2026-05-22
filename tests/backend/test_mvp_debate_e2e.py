"""Integration test: MVP Debate Canvas → WorkflowCompiler → LangGraph.

Validates the full pipeline: build_mvp_debate_workflow creates a
WorkflowDefinition, WorkflowCompiler compiles it, and each agent node
resolves to its own distinct LLM profile.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.blueprints.models import BlueprintLLMProfile
from backend.blueprints.mvp_debate_canvas import build_mvp_debate_workflow
from backend.blueprints.repository import BlueprintRepository
from backend.workflow.workflow_compiler import WorkflowCompiler


@pytest.fixture()
def repo(tmp_path: Path) -> BlueprintRepository:
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


@pytest.fixture()
def four_llm_profiles(repo: BlueprintRepository) -> dict[str, str]:
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


class TestMvpDebateEndToEnd:
    """Full pipeline: factory → compiler → LangGraph with per-agent LLM."""

    def test_compilation_produces_distinct_llm_per_agent(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Each compiled agent should resolve to its own LLM profile."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(wf)

        assert result.is_valid, f"Compilation failed: {result.errors}"
        assert result.graph is not None
        assert len(result.resolved_agents) == 4

        resolved_map = {a.role: a for a in result.resolved_agents}
        for role in ("strategist", "critic", "optimizer", "moderator"):
            agent = resolved_map[role]
            assert agent.llm_profile_id == four_llm_profiles[role], f"{role} should use {four_llm_profiles[role]}, got {agent.llm_profile_id}"

    def test_all_agents_have_distinct_llm_models(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Each agent should resolve to a distinct model name."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(wf)

        models = [a.llm_model for a in result.resolved_agents]
        assert len(set(models)) == 4, f"Expected 4 distinct models, got {models}"

    def test_node_sequence_includes_all_agents(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Topological sort should include all 4 agent nodes."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(wf)

        for role in ("strategist", "critic", "optimizer", "moderator"):
            assert f"node-{role}" in result.node_sequence

    def test_strategist_comes_before_moderator(self, repo: BlueprintRepository, four_llm_profiles: dict[str, str]) -> None:
        """Topological order should place strategist before moderator."""
        wf = build_mvp_debate_workflow(repo, llm_profile_ids=four_llm_profiles)
        compiler = WorkflowCompiler(repo)
        result = compiler.compile(wf)

        seq = result.node_sequence
        assert seq.index("node-strategist") < seq.index("node-moderator")
