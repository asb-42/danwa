"""Blueprint Canvas — Compiler service.

Validates WorkflowDefinitions against the Blueprint catalog.
LangGraph compilation delegates to WorkflowCompiler.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    AGENT_NODE_TYPES,
    WorkflowDefinition,
)

if TYPE_CHECKING:
    from backend.workflow.workflow_compiler import CompiledWorkflow

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

    Validates both the legacy list-based representation and the new
    structured graph representation (nodes/edges/entry_point).
    Future phases will generate LangGraph StateGraph objects.
    """

    def __init__(self, repo: BlueprintRepository) -> None:
        self._repo = repo

    def compile(self, workflow: WorkflowDefinition) -> CompilationResult:
        """Validate blueprint references and resolve agent configurations.

        Does NOT generate a LangGraph StateGraph — that is a future phase.

        Checks (legacy):
        1. All referenced AgentBlueprints exist and are active
        2. All LLM profiles referenced by blueprints exist
        3. All role definitions referenced by blueprints exist
        4. execution_order references valid node IDs
        5. Conditional edges reference valid nodes
        6. Interjection points reference valid nodes

        Checks (graph — Phase 1):
        7. entry_point references a valid node
        8. All agent nodes have valid agent_blueprint_id references
        9. Gate nodes have at least 2 outgoing edges
        10. No isolated nodes (every node must have at least one edge)
        11. Detect cycles (warning, not error — feedback edges create intentional cycles)
        12. Edge source/target reference valid node IDs
        """
        errors: list[str] = []
        warnings: list[str] = []
        resolved: list[ResolvedAgent] = []

        # ------------------------------------------------------------------
        # Legacy validation (node_blueprint_map based)
        # ------------------------------------------------------------------

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
                role=role_def.role_type_id,
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

        # ------------------------------------------------------------------
        # Graph validation (nodes/edges based — Phase 1)
        # ------------------------------------------------------------------

        if workflow.nodes:
            self._validate_graph(workflow, errors, warnings)

        return CompilationResult(
            is_valid=len(errors) == 0,
            resolved_agents=resolved,
            errors=errors,
            warnings=warnings,
        )

    def compile_to_langgraph(self, workflow: WorkflowDefinition) -> "CompiledWorkflow":
        """Compile a WorkflowDefinition into an executable LangGraph StateGraph.

        Delegates to ``WorkflowCompiler`` which handles:
        - Blueprint reference validation (via this service)
        - Agent configuration resolution
        - Topological sort
        - StateGraph construction and compilation

        Args:
            workflow: The workflow definition with nodes, edges, entry_point.

        Returns:
            CompiledWorkflow with the compiled graph, resolved agents, and any
            errors/warnings.
        """
        from backend.workflow.workflow_compiler import WorkflowCompiler

        wf_compiler = WorkflowCompiler(self._repo)
        return wf_compiler.compile(workflow)

    # ------------------------------------------------------------------
    # Graph validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_graph(
        workflow: WorkflowDefinition,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Validate the structured graph representation (nodes + edges)."""
        node_ids = {n.id for n in workflow.nodes}
        node_type_map = {n.id: n.type for n in workflow.nodes}

        # 7. entry_point must reference a valid node
        if workflow.entry_point and workflow.entry_point not in node_ids:
            errors.append(
                f"entry_point '{workflow.entry_point}' does not reference any node"
            )

        # 8. Agent nodes must have agent_blueprint_id
        for node in workflow.nodes:
            if node.type in AGENT_NODE_TYPES and not node.agent_blueprint_id:
                errors.append(
                    f"Agent node '{node.id}' (type={node.type}) is missing agent_blueprint_id"
                )

        # Build adjacency for edge-based checks
        outgoing: dict[str, list[str]] = defaultdict(list)
        incoming: dict[str, list[str]] = defaultdict(list)
        non_feedback_edges: list[tuple[str, str]] = []

        for edge in workflow.edges:
            # 12. Edge source/target must reference valid node IDs
            if edge.source not in node_ids:
                errors.append(
                    f"Edge '{edge.id}': source '{edge.source}' is not a valid node ID"
                )
            if edge.target not in node_ids:
                errors.append(
                    f"Edge '{edge.id}': target '{edge.target}' is not a valid node ID"
                )
            outgoing[edge.source].append(edge.target)
            incoming[edge.target].append(edge.source)
            if edge.type != "feedback":
                non_feedback_edges.append((edge.source, edge.target))

        # 9. Gate nodes must have at least 2 outgoing edges
        for node in workflow.nodes:
            if node.type == "wf-gate" and len(outgoing[node.id]) < 2:
                errors.append(
                    f"Gate node '{node.id}' must have at least 2 outgoing edges "
                    f"(found {len(outgoing[node.id])})"
                )

        # 10. No isolated nodes (every node must have at least one edge)
        for node in workflow.nodes:
            if not outgoing[node.id] and not incoming[node.id]:
                errors.append(
                    f"Node '{node.id}' is isolated — it has no incoming or outgoing edges"
                )

        # 11. Detect cycles (warning only — feedback edges create intentional cycles)
        if non_feedback_edges:
            cycle = _detect_cycle(node_ids, non_feedback_edges)
            if cycle:
                warnings.append(
                    f"Cycle detected in non-feedback edges: {' → '.join(cycle)}. "
                    "This may be intentional if feedback edges are used."
                )


def _detect_cycle(
    node_ids: set[str],
    edges: list[tuple[str, str]],
) -> list[str] | None:
    """Detect a cycle in a directed graph using DFS.

    Returns the cycle path if found, otherwise ``None``.
    Only considers non-feedback edges.
    """
    adj: dict[str, list[str]] = defaultdict(list)
    for src, tgt in edges:
        adj[src].append(tgt)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {nid: WHITE for nid in node_ids}
    parent: dict[str, str | None] = {nid: None for nid in node_ids}

    def _dfs(u: str) -> list[str] | None:
        color[u] = GRAY
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == GRAY:
                # Reconstruct cycle
                cycle = [v, u]
                p = parent[u]
                while p is not None and p != v:
                    cycle.append(p)
                    p = parent[p]
                cycle.reverse()
                return cycle
            if color[v] == WHITE:
                parent[v] = u
                result = _dfs(v)
                if result:
                    return result
        color[u] = BLACK
        return None

    for nid in node_ids:
        if color[nid] == WHITE:
            result = _dfs(nid)
            if result:
                return result
    return None
