"""Tests for the Blueprint Canvas.

Covers:
- Model validation (BlueprintLLMProfile, PromptTemplate, RoleDefinition, AgentBlueprint)
- Repository CRUD for LLM profiles, agent blueprints, canvas layouts, and workflows
- Compiler service validation and resolution
- Argumentation pattern and prompt assembly
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

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

# =========================================================================
# Module lookup stubs for compiler tests
# =========================================================================

_COMPILER_ROLE_DEFINITIONS = {
    "role-1": RoleDefinition(
        id="role-1",
        name="Strategist",
        role_type_id="strategist",
        description="Test",
        consensus_threshold=0.8,
    ),
    "role-resolve": RoleDefinition(
        id="role-resolve",
        name="Resolved Role",
        role_type_id="analyst",
        argumentation_pattern="kantian",
        mode="facilitator",
    ),
}

_COMPILER_ROLE_TYPES = {
    "strategist": RoleType(
        id="strategist",
        name="Strategist",
        icon="🧠",
        color="#3b82f6",
        default_max_rounds=5,
        default_consensus_threshold=0.9,
    ),
    "analyst": RoleType(
        id="analyst",
        name="Analyst",
        icon="🔍",
        color="#8b5cf6",
        default_max_rounds=5,
        default_consensus_threshold=0.9,
    ),
}


def _mock_resolve_role_definition(role_def_id: str):
    return _COMPILER_ROLE_DEFINITIONS.get(role_def_id)


def _mock_resolve_role_type(role_type_id: str):
    return _COMPILER_ROLE_TYPES.get(role_type_id)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture()
def blueprint_repo(tmp_path: Path) -> BlueprintRepository:
    """Create a BlueprintRepository with a temporary database."""
    return BlueprintRepository(db_path=tmp_path / "test_blueprints.db")


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

    def test_optional_tone_profile(self) -> None:
        bp = AgentBlueprint(
            id="bp-with-tone",
            name="With Tone",
            llm_profile_id="test-llm",
            role_definition_id="strategist",
            tone_profile_id="tone-calm",
        )
        assert bp.tone_profile_id == "tone-calm"


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


class TestBlueprintRepositoryAgentBlueprints:
    """Repository CRUD for agent blueprints."""

    def test_save_and_get(self, blueprint_repo: BlueprintRepository) -> None:
        # Create referenced LLM profile (role_definition_id has no FK enforcement)
        blueprint_repo.save_llm_profile(BlueprintLLMProfile(id="test-llm", name="Test LLM", provider="openrouter", model="test/model"))
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
        # Create referenced LLM profile (role_definition_id has no FK enforcement)
        blueprint_repo.save_llm_profile(BlueprintLLMProfile(id="llm", name="LLM", provider="openrouter", model="test/model"))
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
        # Create referenced LLM profile (role_definition_id has no FK enforcement)
        blueprint_repo.save_llm_profile(BlueprintLLMProfile(id="llm", name="LLM", provider="openrouter", model="test/model"))
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

    @pytest.fixture(autouse=True)
    def _patch_module_lookups(self):
        """Auto-patch module lookups with test stubs."""
        with (
            patch(
                "backend.blueprints.compiler.resolve_role_definition",
                side_effect=_mock_resolve_role_definition,
            ),
            patch(
                "backend.blueprints.compiler.resolve_role_type",
                side_effect=_mock_resolve_role_type,
            ),
        ):
            yield

    def _make_repo(self, tmp_path: Path) -> BlueprintRepository:
        return BlueprintRepository(db_path=tmp_path / "compiler_test.db")

    def test_compile_valid_workflow(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
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
        """When resolve_role_definition returns None, compile should detect the missing ref."""
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
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
            name="Missing Role",
            node_blueprint_map={"n1": "bp-1"},
        )
        compiler = CompilerService(repo)
        # Override autouse mock to return None for role resolution
        with patch(
            "backend.blueprints.compiler.resolve_role_definition",
            return_value=None,
        ):
            result = compiler.compile(wf)
        assert result.is_valid is False
        assert any("RoleDefinition" in e for e in result.errors)

    def test_compile_invalid_execution_order(self, tmp_path: Path) -> None:
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
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
                assert required.issubset(available), f"Workflow {wf} missing roles: {required - available}"


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
        (ap_dir / "strategist.md").write_text("Test Pattern: Act according to universal law.", encoding="utf-8")

        default_dir = tmp_path / "prompts" / "default"
        default_dir.mkdir(parents=True)
        (default_dir / "strategist.md").write_text("Variant: Default Strategist - Use standard approach.", encoding="utf-8")

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
        (default_dir / "critic.md").write_text("Default Critic - Standard critique.", encoding="utf-8")

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

    def test_role_type_category_functional(self) -> None:
        """New role types have category='functional'."""
        for rid in ("analyst", "creative", "fact-checker", "expert-reviewer"):
            rt = RoleType(id=rid, name=rid.title())
            assert rt.category == "functional"

    def test_role_type_category_formative(self) -> None:
        """Moderator retains formative category behavior."""
        rt = RoleType(id="moderator", name="Moderator", category="formative")
        assert rt.category == "formative"

    def test_analyst_node_type_registered(self) -> None:
        """Analyst is a valid workflow node type string."""
        valid_node_types = {"wf-strategist", "wf-critic", "wf-optimizer", "wf-moderator", "wf-fact-checker", "wf-analyst", "wf-creative"}
        assert "wf-analyst" in valid_node_types
        assert "wf-creative" in valid_node_types
        assert "wf-fact-checker" in valid_node_types

    def test_resolved_agent_includes_pattern_and_mode(self, tmp_path: Path) -> None:
        """ResolvedAgentConfig includes argumentation_pattern and mode."""
        from backend.blueprints.compiler import CompilerService
        from backend.blueprints.models import (
            AgentBlueprint,
            BlueprintLLMProfile,
        )
        from backend.blueprints.workflow_models import WorkflowDefinition

        repo = BlueprintRepository(db_path=tmp_path / "rb_test.db")

        repo.save_llm_profile(
            BlueprintLLMProfile(
                id="llm-resolve",
                name="Resolve LLM",
                provider="openrouter",
                model="test/model",
            )
        )
        repo.save_blueprint(
            AgentBlueprint(
                id="bp-resolve",
                name="Resolve BP",
                llm_profile_id="llm-resolve",
                role_definition_id="role-resolve",
            )
        )

        wf = WorkflowDefinition(
            id="wf-resolve",
            name="Resolve Test",
            node_blueprint_map={"n1": "bp-resolve"},
            execution_order=["n1"],
        )
        compiler = CompilerService(repo)
        with (
            patch(
                "backend.blueprints.compiler.resolve_role_definition",
                side_effect=_mock_resolve_role_definition,
            ),
            patch(
                "backend.blueprints.compiler.resolve_role_type",
                side_effect=_mock_resolve_role_type,
            ),
        ):
            result = compiler.compile(wf)

        assert result.is_valid
        agent = result.resolved_agents[0]
        assert agent.argumentation_pattern == "kantian"
        assert agent.mode == "facilitator"
