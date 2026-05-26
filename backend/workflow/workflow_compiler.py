"""WorkflowCompiler — translates WorkflowDefinition into a LangGraph StateGraph.

Takes a structured ``WorkflowDefinition`` (nodes, edges, entry_point) and
produces a compiled LangGraph graph that can be executed via ``graph.ainvoke()``.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field

from langgraph.graph import END, StateGraph

from backend.blueprints.compiler import CompilerService
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.resolver import BundleResolver
from backend.blueprints.workflow_models import (
    AGENT_NODE_TYPES,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)
from backend.workflow.node_functions import (
    agent_node_factory,
    complete_wf_node,
    gate_node_factory,
    initialize_wf_node,
    input_node,
    interjection_node,
    moderator_node_factory,
    tone_profile_node_factory,
)
from backend.workflow.workflow_routers import (
    route_conditional,
    route_feedback,
)
from backend.workflow.workflow_state import WorkflowState

logger = logging.getLogger(__name__)


@dataclass
class ResolvedAgentConfig:
    """Resolved configuration for an agent workflow node."""

    node_id: str
    blueprint_id: str
    blueprint_name: str
    llm_profile_id: str
    llm_model: str
    role_definition_id: str
    role: str
    prompt_template_id: str | None = None
    # RoleType metadata (resolved from RoleDefinition.role_type_id or Bundle)
    role_type_name: str = ""
    role_type_icon: str = "👤"
    role_type_color: str = "#8b5cf6"
    default_max_rounds: int = 5
    default_consensus_threshold: float = 0.9
    argumentation_pattern: str = ""
    mode: str = ""
    system_prompt: str = ""  # Assembled system prompt (from Bundle or legacy assembly)
    model_params: dict = field(default_factory=dict)  # LLM inference overrides (top_p, frequency_penalty, etc.)


@dataclass
class CompiledWorkflow:
    """Result of compiling a WorkflowDefinition into a LangGraph graph."""

    graph: object  # Compiled StateGraph (langgraph.graph.CompiledGraph)
    resolved_agents: list[ResolvedAgentConfig] = field(default_factory=list)
    node_sequence: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


class WorkflowCompiler:
    """Compiles a WorkflowDefinition into an executable LangGraph StateGraph.

    Steps:
    1. Validate all blueprint references (delegates to CompilerService)
    2. Resolve agent configurations from the repository
    3. Topological sort of nodes
    4. Build StateGraph with node functions and edge routing
    5. Compile and return
    """

    def __init__(self, repo: BlueprintRepository) -> None:
        self._repo = repo

    def compile(self, workflow: WorkflowDefinition) -> CompiledWorkflow:
        """Compile a WorkflowDefinition into a LangGraph StateGraph.

        Args:
            workflow: The workflow definition with nodes, edges, entry_point.

        Returns:
            CompiledWorkflow with the compiled graph, resolved agents, and any
            errors/warnings.
        """
        result = CompiledWorkflow(graph=None)

        if not workflow.nodes:
            result.errors.append("Workflow has no nodes")
            return result

        if not workflow.entry_point:
            result.errors.append("Workflow has no entry_point")
            return result

        # --- Step 1: Validate using existing CompilerService ---
        compiler = CompilerService(self._repo)
        validation = compiler.compile(workflow)
        result.errors.extend(validation.errors)
        result.warnings.extend(validation.warnings)

        if not validation.is_valid:
            return result

        # --- Step 2: Resolve agent configurations ---
        node_map = {n.id: n for n in workflow.nodes}
        resolved_configs: dict[str, dict] = {}

        for node in workflow.nodes:
            if node.type in AGENT_NODE_TYPES:
                config = self._resolve_agent_config(node, result.errors)
                if config:
                    resolved_configs[node.id] = {
                        "blueprint_id": config.blueprint_id,
                        "blueprint_name": config.blueprint_name,
                        "llm_profile_id": config.llm_profile_id,
                        "llm_model": config.llm_model,
                        "role_definition_id": config.role_definition_id,
                        "role": config.role,
                        "prompt_template_id": config.prompt_template_id,
                        "role_type_name": config.role_type_name,
                        "role_type_icon": config.role_type_icon,
                        "role_type_color": config.role_type_color,
                        "default_max_rounds": config.default_max_rounds,
                        "default_consensus_threshold": config.default_consensus_threshold,
                        "argumentation_pattern": config.argumentation_pattern,
                        "mode": config.mode,
                        "system_prompt": config.system_prompt,
                        "model_params": config.model_params,
                    }
                    result.resolved_agents.append(config)

        if result.errors:
            return result

        # --- Step 3: Topological sort ---
        node_sequence = self._topological_sort(workflow)
        result.node_sequence = node_sequence

        # --- Step 4: Build StateGraph ---
        try:
            graph = self._build_graph(workflow, node_map, resolved_configs)
            result.graph = graph
        except Exception as exc:
            result.errors.append(f"Graph compilation failed: {exc}")
            logger.error("Workflow compilation failed: %s", exc, exc_info=True)

        return result

    def _resolve_agent_config(self, node: WorkflowNode, errors: list[str]) -> ResolvedAgentConfig | None:
        """Resolve an agent node's configuration from either a Bundle or an AgentBlueprint."""
        # --- wf-agent: resolve via Bundle ---
        if node.type == "wf-agent":
            return self._resolve_bundle_config(node, errors)

        # --- Legacy agent types: resolve via AgentBlueprint ---
        blueprint_id = node.agent_blueprint_id
        if not blueprint_id:
            errors.append(f"Agent node '{node.id}' has no agent_blueprint_id")
            return None

        blueprint = self._repo.get_blueprint(blueprint_id)
        if blueprint is None:
            errors.append(f"AgentBlueprint '{blueprint_id}' not found for node '{node.id}'")
            return None

        llm_profile = self._repo.get_llm_profile(blueprint.llm_profile_id)
        if llm_profile is None:
            errors.append(f"LLMProfile '{blueprint.llm_profile_id}' not found for blueprint '{blueprint_id}'")
            return None

        role_def = self._repo.get_role_definition(blueprint.role_definition_id)
        if role_def is None:
            errors.append(f"RoleDefinition '{blueprint.role_definition_id}' not found for blueprint '{blueprint_id}'")
            return None

        # Resolve RoleType chain: RoleDefinition.role_type_id → RoleType
        role_type = self._repo.get_role_type(role_def.role_type_id)
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

        return ResolvedAgentConfig(
            node_id=node.id,
            blueprint_id=blueprint.id,
            blueprint_name=blueprint.name,
            llm_profile_id=llm_profile.id,
            llm_model=llm_profile.model,
            role_definition_id=role_def.id,
            role=role_def.role_type_id,
            prompt_template_id=blueprint.prompt_template_id or role_def.prompt_template_id,
            role_type_name=role_type_name,
            role_type_icon=role_type_icon,
            role_type_color=role_type_color,
            default_max_rounds=default_max_rounds,
            default_consensus_threshold=default_consensus_threshold,
            argumentation_pattern=role_def.argumentation_pattern or "",
            mode=role_def.mode or "",
        )

    def _resolve_bundle_config(self, node: WorkflowNode, errors: list[str]) -> ResolvedAgentConfig | None:
        """Resolve a wf-agent node via AgentBundle."""
        bundle_id = node.bundle_id or node.config.get("bundle_id")
        if not bundle_id:
            errors.append(f"wf-agent node '{node.id}' has no bundle_id")
            return None

        try:
            resolver = BundleResolver(self._repo)
            resolved = resolver.resolve_bundle(bundle_id)
        except ValueError as exc:
            errors.append(f"Bundle resolution failed for node '{node.id}': {exc}")
            return None

        return ResolvedAgentConfig(
            node_id=node.id,
            blueprint_id=resolved.bundle_id,
            blueprint_name=resolved.bundle_name,
            llm_profile_id=resolved.llm_profile.id,
            llm_model=resolved.llm_profile.model,
            role_definition_id=resolved.role_definition.id if resolved.role_definition else "",
            role=resolved.role_type.id,
            prompt_template_id=resolved.prompt_template.id if resolved.prompt_template else None,
            role_type_name=resolved.role_type.name,
            role_type_icon=resolved.role_type.icon,
            role_type_color=resolved.role_type.color,
            default_max_rounds=resolved.role_type.default_max_rounds,
            default_consensus_threshold=resolved.role_type.default_consensus_threshold,
            argumentation_pattern=resolved.role_definition.argumentation_pattern or "" if resolved.role_definition else "",
            mode=resolved.role_definition.mode or "" if resolved.role_definition else "",
            system_prompt=resolved.system_prompt,
            model_params=resolved.model_params,
        )

    def _topological_sort(self, workflow: WorkflowDefinition) -> list[str]:
        """Topological sort of workflow nodes respecting non-feedback edges.

        Feedback and injects_config edges are excluded from the sort to
        avoid cycles and to treat config injection as a non-sequential relationship.
        """
        node_ids = {n.id for n in workflow.nodes}
        # Build adjacency (non-feedback, non-injects_config only)
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for edge in workflow.edges:
            if edge.type not in ("feedback", "injects_config"):
                adj[edge.source].append(edge.target)
                in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Kahn's algorithm
        queue = [nid for nid in node_ids if in_degree.get(nid, 0) == 0]
        result: list[str] = []

        while queue:
            # Prefer entry_point first
            if workflow.entry_point in queue:
                current = workflow.entry_point
                queue.remove(current)
            else:
                current = queue.pop(0)

            result.append(current)
            for neighbor in adj.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Add any nodes not reached (isolated or in feedback-only cycles)
        for nid in node_ids:
            if nid not in result:
                result.append(nid)

        return result

    def _build_graph(
        self,
        workflow: WorkflowDefinition,
        node_map: dict[str, WorkflowNode],
        resolved_configs: dict[str, dict],
    ) -> object:
        """Build and compile the LangGraph StateGraph."""
        graph = StateGraph(WorkflowState)

        # --- Resolve injects_config edges ---
        # For each agent node, find if a tone_profile node injects config into it
        tone_injection_map: dict[str, str] = {}  # agent_node_id → tone_profile_node_id
        for edge in workflow.edges:
            if edge.type == "injects_config":
                source_node = node_map.get(edge.source)
                if source_node and source_node.type == "wf-tone-profile":
                    tone_injection_map[edge.target] = edge.source

        # Propagate tone_profile_source_node_id into agent node configs
        for agent_node_id, tone_node_id in tone_injection_map.items():
            if agent_node_id in resolved_configs:
                resolved_configs[agent_node_id]["tone_profile_source_node_id"] = tone_node_id

        # --- Add nodes ---
        entry_point = workflow.entry_point

        for node in workflow.nodes:
            node_fn = self._create_node_function(node, resolved_configs)
            graph.add_node(node.id, node_fn)

        # Add a complete node for final output
        graph.add_node("__complete__", complete_wf_node)

        # --- Set entry point ---
        graph.set_entry_point(entry_point)

        # --- Build edge index ---
        # Group edges by source
        edges_by_source: dict[str, list[WorkflowEdge]] = defaultdict(list)
        for edge in workflow.edges:
            edges_by_source[edge.source].append(edge)

        # --- Add edges ---
        for node in workflow.nodes:
            outgoing = edges_by_source.get(node.id, [])

            if not outgoing:
                # Terminal node → END
                graph.add_edge(node.id, END)
                continue

            # Separate feedback, injects_config edges from non-feedback
            non_feedback = [e for e in outgoing if e.type not in ("feedback", "injects_config")]
            feedback_edges = [e for e in outgoing if e.type == "feedback"]

            # Handle gate nodes (conditional routing)
            if node.type == "wf-gate" and len(non_feedback) >= 2:
                conditions = {}
                for edge in non_feedback:
                    target = edge.target
                    condition = edge.condition or "True"
                    conditions[target] = condition

                router = route_conditional(conditions)
                mapping = {tid: tid for tid in conditions}
                mapping["end"] = END
                graph.add_conditional_edges(node.id, router, mapping)

            # Handle feedback edges
            elif feedback_edges:
                # Has feedback + possibly sequential edges
                feedback_target = feedback_edges[0].target
                max_rounds = 10  # Default, could be from termination_conditions

                # Read max_rounds from termination conditions
                for tc in workflow.termination_conditions:
                    if tc.type == "max_rounds":
                        max_rounds = tc.value if isinstance(tc.value, int) else 10

                if non_feedback:
                    # Has both sequential exit edge and feedback edge
                    exit_target = non_feedback[0].target
                    router = route_feedback(max_rounds)
                    graph.add_conditional_edges(
                        node.id,
                        router,
                        {
                            "continue": feedback_target,
                            "exit": exit_target if exit_target != node.id else END,
                        },
                    )
                else:
                    # Only feedback edge — loop back or complete
                    router = route_feedback(max_rounds)
                    graph.add_conditional_edges(
                        node.id,
                        router,
                        {
                            "continue": feedback_target,
                            "exit": "__complete__",
                        },
                    )

            # Handle interjection edges
            elif any(e.type == "interjection" for e in non_feedback):
                interjection_edge = next(e for e in non_feedback if e.type == "interjection")
                # Insert interjection node between source and target
                inj_node_id = f"__inj_{node.id}"
                graph.add_node(inj_node_id, interjection_node)
                graph.add_edge(node.id, inj_node_id)
                graph.add_conditional_edges(
                    inj_node_id,
                    lambda state: "next",
                    {"next": interjection_edge.target},
                )

                # Handle other non-interjection edges
                other_edges = [e for e in non_feedback if e.type != "interjection"]
                if other_edges:
                    # This is unusual but handle it
                    graph.add_edge(node.id, other_edges[0].target)

            # Handle single sequential edge
            elif len(non_feedback) == 1:
                target = non_feedback[0].target
                graph.add_edge(node.id, target)

            # Handle multiple non-feedback, non-gate edges (take first)
            elif len(non_feedback) > 1:
                # Multiple targets without gate — use first as primary
                graph.add_edge(node.id, non_feedback[0].target)
                logger.warning(
                    "Node '%s' has %d non-feedback outgoing edges but is not a gate. Using first target '%s'.",
                    node.id,
                    len(non_feedback),
                    non_feedback[0].target,
                )

        # --- Ensure terminal nodes connect to END ---
        # Find nodes with no outgoing edges that aren't already connected
        all_sources = {e.source for e in workflow.edges}
        for node in workflow.nodes:
            if node.id not in all_sources:
                # This node has no outgoing edges — it's already handled above
                pass

        logger.info(
            "Compiled workflow graph: %d nodes, %d edges, entry='%s'",
            len(workflow.nodes),
            len(workflow.edges),
            entry_point,
        )

        return graph.compile()

    def _create_node_function(
        self,
        node: WorkflowNode,
        resolved_configs: dict[str, dict],
    ) -> callable:
        """Create the appropriate node function for a workflow node type."""
        if node.type == "wf-input":
            return input_node
        elif node.type == "wf-initialize":
            return initialize_wf_node
        elif node.type in AGENT_NODE_TYPES:
            config = resolved_configs.get(node.id, {})
            if node.type == "wf-moderator":
                # Use RoleType default_consensus_threshold if available
                threshold = config.get("default_consensus_threshold", 0.7)
                return moderator_node_factory(node.id, config, threshold)
            elif node.type == "wf-agent":
                # Generic agent node — uses system_prompt from resolved Bundle
                return agent_node_factory(node.id, "wf-agent", config)
            else:
                return agent_node_factory(node.id, node.type, config)
        elif node.type == "wf-gate":
            condition = ""
            if node.config:
                condition = node.config.get("condition", "")
            return gate_node_factory(node.id, condition)
        elif node.type == "wf-user-injection":
            return interjection_node
        elif node.type == "wf-tone-profile":
            return tone_profile_node_factory(node.id, node.config)
        else:
            logger.warning("Unknown node type '%s' for node '%s', using passthrough", node.type, node.id)
            return input_node
