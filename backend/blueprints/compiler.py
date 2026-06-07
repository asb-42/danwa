"""Blueprint Canvas — Compiler service.

Validates WorkflowDefinitions against the Blueprint catalog.
LangGraph compilation delegates to WorkflowCompiler.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from backend.blueprints.module_lookups import (
    resolve_role_definition,
    resolve_role_type,
)
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
    # RoleType metadata (resolved from RoleDefinition.role_type_id)
    role_type_name: str = ""
    role_type_icon: str = "👤"
    role_type_color: str = "#8b5cf6"
    default_max_rounds: int = 5
    default_consensus_threshold: float = 0.9
    # Argumentation & Mode
    argumentation_pattern: str = ""
    mode: str = ""


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
        """Initialise CompilerService."""
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
                errors.append(f"Node '{node_id}': AgentBlueprint '{blueprint_id}' not found in catalog")
                continue

            if not blueprint.is_active:
                warnings.append(f"Node '{node_id}': AgentBlueprint '{blueprint_id}' is inactive")

            # Resolve LLM profile
            llm_profile = self._repo.get_llm_profile(blueprint.llm_profile_id)
            if llm_profile is None:
                errors.append(f"Node '{node_id}': LLMProfile '{blueprint.llm_profile_id}' not found")
                continue

            # Resolve role definition
            role_def = resolve_role_definition(blueprint.role_definition_id)
            if role_def is None:
                errors.append(f"Node '{node_id}': RoleDefinition '{blueprint.role_definition_id}' not found")
                continue

            # Resolve RoleType chain
            role_type = resolve_role_type(role_def.role_type_id)
            role_type_name = ""
            role_type_icon = "👤"
            role_type_color = "#8b5cf6"
            default_max_rounds = 5
            default_consensus_threshold = 0.9
            if role_type:
                role_type_name = role_type.name
                role_type_icon = role_type.icon
                role_type_color = role_type.color
                default_max_rounds = role_type.default_max_rounds
                default_consensus_threshold = role_type.default_consensus_threshold
            else:
                logger.warning(
                    "RoleType '%s' not found for RoleDefinition '%s', using defaults",
                    role_def.role_type_id,
                    role_def.id,
                )

            resolved.append(
                ResolvedAgent(
                    node_id=node_id,
                    blueprint_id=blueprint.id,
                    blueprint_name=blueprint.name,
                    llm_profile_id=llm_profile.id,
                    llm_model=llm_profile.model,
                    role_definition_id=role_def.id,
                    role=role_def.role_type_id,
                    role_type_name=role_type_name,
                    role_type_icon=role_type_icon,
                    role_type_color=role_type_color,
                    default_max_rounds=default_max_rounds,
                    default_consensus_threshold=default_consensus_threshold,
                    argumentation_pattern=role_def.argumentation_pattern or "",
                    mode=role_def.mode or "",
                )
            )

        # 2. Validate execution_order references valid node IDs
        all_node_ids = set(workflow.node_blueprint_map.keys())
        for node_id in workflow.execution_order:
            if node_id not in all_node_ids:
                errors.append(f"execution_order references unknown node '{node_id}'")

        # 3. Validate conditional edges reference valid nodes
        for edge in workflow.conditional_edges:
            if edge.source_node_id not in all_node_ids:
                errors.append(f"Conditional edge source '{edge.source_node_id}' not in node map")
            if edge.target_node_id not in all_node_ids:
                errors.append(f"Conditional edge target '{edge.target_node_id}' not in node map")

        # 4. Validate interjection points reference valid nodes
        for point in workflow.interjection_points:
            if point.node_id not in all_node_ids:
                errors.append(f"Interjection point '{point.node_id}' not in node map")

        # ------------------------------------------------------------------
        # Graph validation (nodes/edges based — Phase 1)
        # ------------------------------------------------------------------

        if workflow.nodes:
            self._validate_graph(workflow, errors, warnings)
            self._validate_tone_profile_edges(workflow, errors, warnings)

        return CompilationResult(
            is_valid=len(errors) == 0,
            resolved_agents=resolved,
            errors=errors,
            warnings=warnings,
        )

    def compile_to_langgraph(self, workflow: WorkflowDefinition) -> CompiledWorkflow:
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
        {n.id: n.type for n in workflow.nodes}

        # 7. entry_point must reference a valid node
        if workflow.entry_point and workflow.entry_point not in node_ids:
            errors.append(f"entry_point '{workflow.entry_point}' does not reference any node")

        # 8. Agent nodes must have agent_blueprint_id
        for node in workflow.nodes:
            if node.type in AGENT_NODE_TYPES and not node.agent_blueprint_id:
                errors.append(f"Agent node '{node.id}' (type={node.type}) is missing agent_blueprint_id")

        # Build adjacency for edge-based checks
        outgoing: dict[str, list[str]] = defaultdict(list)
        incoming: dict[str, list[str]] = defaultdict(list)
        non_feedback_edges: list[tuple[str, str]] = []

        for edge in workflow.edges:
            # 12. Edge source/target must reference valid node IDs
            if edge.source not in node_ids:
                errors.append(f"Edge '{edge.id}': source '{edge.source}' is not a valid node ID")
            if edge.target not in node_ids and edge.target not in ("__end__",):
                errors.append(f"Edge '{edge.id}': target '{edge.target}' is not a valid node ID")
            outgoing[edge.source].append(edge.target)
            incoming[edge.target].append(edge.source)
            if edge.type != "feedback":
                non_feedback_edges.append((edge.source, edge.target))

        # 9. Gate nodes must have at least 2 outgoing edges
        for node in workflow.nodes:
            if node.type == "wf-gate" and len(outgoing[node.id]) < 2:
                errors.append(f"Gate node '{node.id}' must have at least 2 outgoing edges (found {len(outgoing[node.id])})")

        # 10. No isolated nodes (every node must have at least one edge)
        # wf-phase nodes are visual-only containers — they have no edges by design.
        for node in workflow.nodes:
            if node.type == "wf-phase":
                continue
            if not outgoing[node.id] and not incoming[node.id]:
                errors.append(f"Node '{node.id}' is isolated — it has no incoming or outgoing edges")

        # 11. Detect cycles (warning only — feedback edges create intentional cycles)
        if non_feedback_edges:
            cycle = _detect_cycle(node_ids, non_feedback_edges)
            if cycle:
                warnings.append(f"Cycle detected in non-feedback edges: {' → '.join(cycle)}. This may be intentional if feedback edges are used.")

    @staticmethod
    @staticmethod
    def _validate_tone_profile_edges(
        workflow: WorkflowDefinition,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """Validate injects_config edges for tone profile nodes.

        Rules:
        1. injects_config source must be a wf-tone-profile node.
        2. injects_config target must be an agent node type (not input, gate, etc.).
        3. An agent node may have at most one incoming injects_config edge.
        4. A tone_profile node may have at most one injects_config edge to a given agent.
        5. Tone profile nodes must not be isolated (must have at least one injects_config or sequential edge).
        """
        node_type_map = {n.id: n.type for n in workflow.nodes}
        injectable_types = set(AGENT_NODE_TYPES)

        # Track: agent_node_id -> list of source tone_profile node IDs
        agent_incoming_config: dict[str, list[str]] = {}
        # Track: tone_profile_node_id -> list of target agent node IDs
        tone_outgoing_config: dict[str, list[str]] = {}
        # Track all edges for isolation check
        all_edge_sources: set[str] = set()
        all_edge_targets: set[str] = set()

        for edge in workflow.edges:
            all_edge_sources.add(edge.source)
            all_edge_targets.add(edge.target)

            if edge.type != "injects_config":
                continue

            source_type = node_type_map.get(edge.source, "")
            target_type = node_type_map.get(edge.target, "")

            # Rule 1: source must be wf-tone-profile
            if source_type != "wf-tone-profile":
                errors.append(f"injects_config edge '{edge.id}': source '{edge.source}' is type '{source_type}', expected 'wf-tone-profile'")

            # Rule 2: target must be an agent node type
            if target_type not in injectable_types:
                errors.append(
                    f"injects_config edge '{edge.id}': target '{edge.target}' "
                    f"is type '{target_type}', must be an agent node "
                    f"({', '.join(sorted(injectable_types))})"
                )

            # Collect for Rule 3 and 4
            agent_incoming_config.setdefault(edge.target, []).append(edge.source)
            tone_outgoing_config.setdefault(edge.source, []).append(edge.target)

        # Rule 3: Agent node may have at most one incoming injects_config
        for agent_id, sources in agent_incoming_config.items():
            if len(sources) > 1:
                errors.append(f"Agent node '{agent_id}' has {len(sources)} incoming injects_config edges (max 1 allowed): {sources}")

        # Rule 4: Tone profile node may have at most one injects_config per agent
        for tone_id, targets in tone_outgoing_config.items():
            if len(targets) != len(set(targets)):
                errors.append(f"Tone profile node '{tone_id}' has duplicate injects_config edges to the same agent node")

        # Rule 5: Tone profile nodes must not be isolated
        for node in workflow.nodes:
            if node.type == "wf-tone-profile":
                has_edge = node.id in all_edge_sources or node.id in all_edge_targets
                if not has_edge:
                    errors.append(
                        f"Tone profile node '{node.id}' is isolated — "
                        f"it must have at least one injects_config or "
                        f"sequential edge connecting it to the workflow"
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

    white, gray, black = 0, 1, 2
    color: dict[str, int] = {nid: white for nid in node_ids}
    parent: dict[str, str | None] = {nid: None for nid in node_ids}

    def _dfs(u: str) -> list[str] | None:
        color[u] = gray
        for v in adj.get(u, []):
            if v not in color:
                continue
            if color[v] == gray:
                # Reconstruct cycle
                cycle = [v, u]
                p = parent[u]
                while p is not None and p != v:
                    cycle.append(p)
                    p = parent[p]
                cycle.reverse()
                return cycle
            if color[v] == white:
                parent[v] = u
                result = _dfs(v)
                if result:
                    return result
        color[u] = black
        return None

    for nid in node_ids:
        if color[nid] == white:
            result = _dfs(nid)
            if result:
                return result
    return None
