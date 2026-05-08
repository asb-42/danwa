"""Blueprint Canvas — Compiler service stub.

Validates WorkflowDefinitions against the Blueprint catalog.
Full LangGraph compilation is a future phase.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import WorkflowDefinition

logger = logging.getLogger(__name__)


@dataclass
class ResolvedAgent:
    """A resolved agent reference from a WorkflowDefinition."""

    node_id: str
    blueprint_id: str
    blueprint_name: str
    llm_profile_id: str
    llm_model: str
    role_definition_id: str
    role: str
    prompt_template_id: str | None


@dataclass
class CompilationResult:
    """Result of compiling a WorkflowDefinition."""

    is_valid: bool
    resolved_agents: list[ResolvedAgent] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class CompilerService:
    """Validates and compiles WorkflowDefinitions into executable form.

    Currently a stub that validates blueprint references only.
    Future phases will generate LangGraph StateGraph objects.
    """

    def __init__(self, repo: BlueprintRepository) -> None:
        self._repo = repo

    def compile(self, workflow: WorkflowDefinition) -> CompilationResult:
        """Validate blueprint references and resolve agent configurations.

        Does NOT generate a LangGraph StateGraph — that is a future phase.

        Checks:
        1. All referenced AgentBlueprints exist and are active
        2. All LLM profiles referenced by blueprints exist
        3. All role definitions referenced by blueprints exist
        4. execution_order references valid node IDs
        5. Conditional edges reference valid nodes
        6. Interjection points reference valid nodes
        """
        errors: list[str] = []
        warnings: list[str] = []
        resolved: list[ResolvedAgent] = []

        # 1. Validate all referenced blueprints exist
        for node_id, blueprint_id in workflow.node_blueprint_map.items():
            blueprint = self._repo.get_blueprint(blueprint_id)
            if blueprint is None:
                errors.append(
                    f"Node '{node_id}': AgentBlueprint '{blueprint_id}' not found in catalog"
                )
                continue

            if not blueprint.is_active:
                warnings.append(
                    f"Node '{node_id}': AgentBlueprint '{blueprint_id}' is inactive"
                )

            # Resolve LLM profile
            llm_profile = self._repo.get_llm_profile(blueprint.llm_profile_id)
            if llm_profile is None:
                errors.append(
                    f"Node '{node_id}': LLMProfile '{blueprint.llm_profile_id}' not found"
                )
                continue

            # Resolve role definition
            role_def = self._repo.get_role_definition(blueprint.role_definition_id)
            if role_def is None:
                errors.append(
                    f"Node '{node_id}': RoleDefinition '{blueprint.role_definition_id}' not found"
                )
                continue

            resolved.append(ResolvedAgent(
                node_id=node_id,
                blueprint_id=blueprint.id,
                blueprint_name=blueprint.name,
                llm_profile_id=llm_profile.id,
                llm_model=llm_profile.model,
                role_definition_id=role_def.id,
                role=role_def.role,
                prompt_template_id=blueprint.prompt_template_id or role_def.prompt_template_id,
            ))

        # 2. Validate execution_order references valid node IDs
        all_node_ids = set(workflow.node_blueprint_map.keys())
        for node_id in workflow.execution_order:
            if node_id not in all_node_ids:
                errors.append(
                    f"execution_order references unknown node '{node_id}'"
                )

        # 3. Validate conditional edges reference valid nodes
        for edge in workflow.conditional_edges:
            if edge.source_node_id not in all_node_ids:
                errors.append(
                    f"Conditional edge source '{edge.source_node_id}' not in node map"
                )
            if edge.target_node_id not in all_node_ids:
                errors.append(
                    f"Conditional edge target '{edge.target_node_id}' not in node map"
                )

        # 4. Validate interjection points reference valid nodes
        for point in workflow.interjection_points:
            if point.node_id not in all_node_ids:
                errors.append(
                    f"Interjection point '{point.node_id}' not in node map"
                )

        # TODO: Future phase — translate to LangGraph StateGraph
        # graph = self._build_langgraph(workflow, resolved)

        return CompilationResult(
            is_valid=len(errors) == 0,
            resolved_agents=resolved,
            errors=errors,
            warnings=warnings,
        )
