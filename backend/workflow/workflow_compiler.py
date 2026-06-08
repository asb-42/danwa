"""WorkflowCompiler — translates WorkflowDefinition into a LangGraph StateGraph.

Takes a structured ``WorkflowDefinition`` (nodes, edges, entry_point) and
produces a compiled LangGraph graph that can be executed via ``graph.ainvoke()``.

Compilation steps:

1. Validate all blueprint references (delegates to ``CompilerService``).
2. Resolve agent configurations from the repository (Bundle, AgentBlueprint,
   or module agent-core).
3. Topological sort of nodes (Kahn's algorithm with fallback for cycles).
4. Build ``StateGraph`` with node functions, conditional edge routing
   (gate, decision, feedback), and fan-out/fan-in wiring.
5. **Convergence validation** — for fan-out nodes, verify that all
   parallel branches eventually reach a common downstream node via
   :meth:`_find_common_downstream`. Warns if branches diverge to
   ``__complete__`` independently, which would cause duplicate output
   assembly.
6. Compile and return a :class:`CompiledWorkflow`.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field

from langgraph.graph import END, StateGraph

from backend.blueprints.compiler import CompilerService
from backend.blueprints.module_lookups import (
    is_module_agent_id,
    resolve_agent_from_module,
    resolve_role_definition,
    resolve_role_type,
)
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
    angels_advocate_node_factory,
    builder_node_factory,
    complete_wf_node,
    gate_node_factory,
    initialize_wf_node,
    input_node,
    interjection_node,
    moderator_node_factory,
    pragmatist_node_factory,
    tone_profile_node_factory,
)
from backend.workflow.safe_eval import SafeEvalError, evaluate_condition
from backend.workflow.workflow_routers import (
    route_conditional,
    route_decision,
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
    # Human-readable LLM profile name (never a raw UUID)
    llm_profile_name: str = ""
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
    node_config: dict = field(default_factory=dict)  # WorkflowNode.config fields (mode, template, etc.)
    agent_tags: list[str] = field(default_factory=list)  # Blueprint / RoleType tags, used to pick domain-specific prompts


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
        """Return ``True`` if the instance passes validation."""
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
        """Initialise WorkflowCompiler."""
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
                        "llm_profile_name": config.llm_profile_name,
                        "role_definition_id": config.role_definition_id,
                        "role": config.role,
                        "role_type_name": config.role_type_name,
                        "role_type_icon": config.role_type_icon,
                        "role_type_color": config.role_type_color,
                        "default_max_rounds": config.default_max_rounds,
                        "default_consensus_threshold": config.default_consensus_threshold,
                        "argumentation_pattern": config.argumentation_pattern,
                        "mode": config.mode,
                        "system_prompt": config.system_prompt,
                        "model_params": config.model_params,
                        "node_config": config.node_config,
                        "agent_tags": list(config.agent_tags),
                    }
                    result.resolved_agents.append(config)

        if result.errors:
            return result

        # --- Step 3: Topological sort ---
        node_sequence, unreached = self._topological_sort(workflow)
        result.node_sequence = node_sequence

        # F-08: Warn if Kahn's algorithm couldn't reach all nodes
        # (e.g. decision-edge cycles cause in_degree to never reach 0).
        if unreached:
            result.warnings.append(
                f"Topological sort: {len(unreached)} node(s) not reached "
                f"by Kahn's algorithm due to decision-edge cycles: "
                f"{unreached}. Falling back to insertion order."
            )

        # --- Step 4: Build StateGraph ---
        try:
            graph, graph_warnings = self._build_graph(workflow, node_map, resolved_configs)
            result.graph = graph
            result.warnings.extend(graph_warnings)
        except Exception as exc:
            result.errors.append(f"Graph compilation failed: {exc}")
            logger.error("Workflow compilation failed: %s", exc, exc_info=True)

        return result

    def _resolve_agent_config(self, node: WorkflowNode, errors: list[str]) -> ResolvedAgentConfig | None:
        """Resolve an agent node's configuration from Bundle, AgentBlueprint, or module agent-core."""
        # --- wf-agent: resolve via Bundle ---
        if node.type == "wf-agent":
            return self._resolve_bundle_config(node, errors)

        # --- Legacy agent types: resolve via AgentBlueprint or module agent-core ---
        blueprint_id = node.agent_blueprint_id
        if not blueprint_id:
            errors.append(f"Agent node '{node.id}' has no agent_blueprint_id")
            return None

        blueprint = self._repo.get_blueprint(blueprint_id)

        # --- Module agent-core fallback (ac-* UUID pattern) ---
        if blueprint is None and is_module_agent_id(blueprint_id):
            return self._resolve_module_agent_config(node, blueprint_id, errors)

        if blueprint is None:
            errors.append(f"AgentBlueprint '{blueprint_id}' not found for node '{node.id}'")
            return None

        llm_profile = self._repo.get_llm_profile(blueprint.llm_profile_id)
        if llm_profile is None:
            errors.append(f"LLMProfile '{blueprint.llm_profile_id}' not found for blueprint '{blueprint_id}'")
            return None

        role_def = resolve_role_definition(blueprint.role_definition_id)
        if role_def is None:
            errors.append(f"RoleDefinition '{blueprint.role_definition_id}' not found for blueprint '{blueprint_id}'")
            return None

        # Resolve RoleType chain: RoleDefinition.role_type_id → RoleType
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

        return ResolvedAgentConfig(
            node_id=node.id,
            blueprint_id=blueprint.id,
            blueprint_name=blueprint.name,
            llm_profile_id=llm_profile.id,
            llm_model=llm_profile.model,
            llm_profile_name=llm_profile.name,
            role_definition_id=role_def.id,
            role=role_def.role_type_id,
            role_type_name=role_type_name,
            role_type_icon=role_type_icon,
            role_type_color=role_type_color,
            default_max_rounds=default_max_rounds,
            default_consensus_threshold=default_consensus_threshold,
            argumentation_pattern=role_def.argumentation_pattern or "",
            mode=role_def.mode or "",
            node_config=node.config or {},
            agent_tags=list(blueprint.tags or []),
        )

    def _resolve_module_agent_config(self, node: WorkflowNode, module_id: str, errors: list[str]) -> ResolvedAgentConfig | None:
        """Resolve an agent node from a module agent-core (ac-* UUID).

        Called when ``agent_blueprint_id`` is a module UUID and no
        matching AgentBlueprint exists in the DB.
        """
        mod_agent = resolve_agent_from_module(module_id)
        if mod_agent is None:
            errors.append(f"Module agent-core '{module_id}' not found for node '{node.id}'. Ensure the module is installed and enabled.")
            return None

        # Resolve LLM profile: module → node config → service default → first available
        llm_profile_id = mod_agent.llm_profile_id
        if not llm_profile_id:
            llm_profile_id = node.config.get("llm_profile_id", "")
        if not llm_profile_id:
            llm_profile_id = self._get_fallback_llm_profile_id(errors)
        if not llm_profile_id:
            errors.append(
                f"No LLM profile available for module agent '{module_id}' on node '{node.id}'. Assign one via node config or set a service default."
            )
            return None

        llm_profile = self._repo.get_llm_profile(llm_profile_id)
        llm_model = llm_profile.model if llm_profile else ""
        llm_profile_name = llm_profile.name if llm_profile else ""

        # Resolve RoleType from the module agent's role
        role_type = resolve_role_type(mod_agent.role)
        role_type_name = ""
        role_type_icon = "👤"
        role_type_color = "#8b5cf6"
        default_max_rounds = mod_agent.max_rounds
        default_consensus_threshold = mod_agent.consensus_threshold
        if role_type:
            role_type_name = role_type.name
            role_type_icon = role_type.icon
            role_type_color = role_type.color
            default_max_rounds = role_type.default_max_rounds
            default_consensus_threshold = role_type.default_consensus_threshold

        # Read composition component overrides from node.config
        node_cfg = node.config or {}
        argumentation_pattern = node_cfg.get("argumentation_pattern", "")
        tone_profile_id = node_cfg.get("tone_profile_id", "")
        prompt_modifier_id = node_cfg.get("prompt_modifier_id", "")

        # Use ComposerService to compose system_prompt from component IDs
        system_prompt = mod_agent.system_prompt
        composition_ids = [module_id, argumentation_pattern, tone_profile_id, prompt_modifier_id]
        if any(composition_ids):
            try:
                from backend.services.composer_service import ComposerService, Composition

                composer = ComposerService()
                composition = Composition(
                    agent_core_id=module_id,
                    argumentation_pattern_id=argumentation_pattern,
                    tone_profile_id=tone_profile_id,
                    prompt_modifier_id=prompt_modifier_id,
                )
                composed = composer.compose(composition)
                if composed and composed.strip():
                    system_prompt = composed
                    logger.info(
                        "Composed system_prompt for node '%s' from agent_core=%s pattern=%s tone=%s modifier=%s (%d chars)",
                        node.id,
                        module_id or "(none)",
                        argumentation_pattern or "(none)",
                        tone_profile_id or "(none)",
                        prompt_modifier_id or "(none)",
                        len(composed),
                    )
            except Exception as exc:
                logger.warning(
                    "ComposerService failed for node '%s', using module default: %s",
                    node.id,
                    exc,
                )

        return ResolvedAgentConfig(
            node_id=node.id,
            blueprint_id=module_id,
            blueprint_name=mod_agent.name,
            llm_profile_id=llm_profile_id,
            llm_model=llm_model,
            llm_profile_name=llm_profile_name,
            role_definition_id=module_id,
            role=mod_agent.role,
            role_type_name=role_type_name,
            role_type_icon=role_type_icon,
            role_type_color=role_type_color,
            default_max_rounds=default_max_rounds,
            default_consensus_threshold=default_consensus_threshold,
            argumentation_pattern=argumentation_pattern,
            mode="",
            system_prompt=system_prompt,
            node_config=node_cfg,
            agent_tags=list(mod_agent.tags),
        )

    _API_KEY_PLACEHOLDERS = frozenset(
        {
            "YOUR_API_KEY_ENV_VAR",
            "YOUR_API_KEY",
            "REPLACE_ME",
            "CHANGEME",
            "",
        }
    )

    def _get_fallback_llm_profile_id(self, errors: list[str]) -> str:
        """Find a usable LLM profile from the service default or first available.

        Priority order:
        1. ``settings.service_llm_profile_id`` (user-configured utility LLM).
        2. First profile with BYOK ``api_key`` set directly.
        3. First profile whose ``api_key_env`` resolves to a real env var.
        4. First profile with a non-placeholder ``api_key_env``.
        5. Absolute first profile in the DB.
        """
        import os

        # --- 1. Explicit service default ---
        try:
            from backend.core.config import settings as _settings

            if _settings.service_llm_profile_id:
                logger.info(
                    "Using configured service LLM profile: %s",
                    _settings.service_llm_profile_id,
                )
                return _settings.service_llm_profile_id
        except Exception:
            pass
        try:
            profiles = self._repo.list_llm_profiles()
            if not profiles:
                return ""
            # --- 2. BYOK (direct api_key on profile) ---
            for p in profiles:
                if p.api_key:
                    logger.info("Fallback LLM: BYOK profile '%s'", p.id)
                    return p.id
            # --- 3. Env var is actually set in the environment ---
            for p in profiles:
                if p.api_key_env and p.api_key_env not in self._API_KEY_PLACEHOLDERS and os.environ.get(p.api_key_env):
                    logger.info(
                        "Fallback LLM: env '%s' is set → profile '%s'",
                        p.api_key_env,
                        p.id,
                    )
                    return p.id
            # --- 4. Non-placeholder env var name (but env not set) ---
            for p in profiles:
                if p.api_key_env and p.api_key_env not in self._API_KEY_PLACEHOLDERS:
                    logger.warning(
                        "Fallback LLM: env '%s' not set, using profile '%s' anyway",
                        p.api_key_env,
                        p.id,
                    )
                    return p.id
            # --- 5. Last resort ---
            logger.warning("Fallback LLM: no good candidate, using first profile '%s'", profiles[0].id)
            return profiles[0].id
        except Exception:
            pass
        return ""

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
            llm_profile_name=resolved.llm_profile.name,
            role_definition_id="",
            role=resolved.role_type.id,
            role_type_name=resolved.role_type.name,
            role_type_icon=resolved.role_type.icon,
            role_type_color=resolved.role_type.color,
            default_max_rounds=resolved.role_type.default_max_rounds,
            default_consensus_threshold=resolved.role_type.default_consensus_threshold,
            system_prompt=resolved.system_prompt,
            model_params=resolved.model_params,
            agent_tags=list(resolved.role_type.tags or []),
        )

    def _topological_sort(self, workflow: WorkflowDefinition) -> tuple[list[str], list[str]]:
        """Topological sort of workflow nodes respecting ordering edges.

        Edge-type handling:

        * ``sequential`` and ``conditional`` — full ordering
          constraint, included in the sort.
        * ``decision`` — included.  A Moderator's
          ``(approved) → Builder`` edge is a real ordering
          constraint: the Builder's state (e.g. ``draft_version``)
          is read by the next agent, and the static
          ``node_sequence`` (used by Inspector / observability /
          debug tools) must reflect the logical data flow.
          ``Sprint 41 (M3 fix)`` — previously excluded.
        * ``feedback`` — excluded (back-edge; would create
          a cycle that Kahn's algorithm cannot resolve).
        * ``injects_config`` — excluded (config injection,
          not a sequencing edge).
        * ``interjection`` / ``builds_upon`` / ``validates`` —
          excluded.  These are not strict ordering constraints
          for the static ``node_sequence``; the runtime
          ``add_node`` wiring handles them.

        Self-loops on decision edges (Moderator → Moderator on
        ``revision_required``) are skipped: they are part of the
        conditional routing, not a sequence constraint, and
        including them would prevent the source from ever
        reaching ``in_degree == 0``.

        Returns:
            ``(node_sequence, unreached_nodes)`` — the sorted
            sequence and any node IDs that Kahn's algorithm
            could not place (e.g. due to decision-edge cycles).
            Unreached nodes are appended at the end of
            ``node_sequence`` in insertion order.
        """
        node_ids = {n.id for n in workflow.nodes}
        # Build adjacency (sequential, conditional, decision;
        # skip feedback, injects_config, interjection,
        # builds_upon, validates, and self-loops).
        adj: dict[str, list[str]] = defaultdict(list)
        in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

        for edge in workflow.edges:
            if edge.type in ("feedback", "injects_config", "interjection", "builds_upon", "validates"):
                continue
            if edge.source == edge.target:
                # Self-loop (e.g. decision edge that loops back
                # to the same node on a particular condition).
                # Not a sequencing constraint.
                continue
            adj[edge.source].append(edge.target)
            in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        # Kahn's algorithm — use deque for O(1) popleft instead of O(n) list.pop(0).
        # M2 fix (Sprint 33): scales linearly for large workflows.
        queue: deque[str] = deque(nid for nid in node_ids if in_degree.get(nid, 0) == 0)
        result: list[str] = []

        while queue:
            # Prefer entry_point first
            if workflow.entry_point in queue:
                current = workflow.entry_point
                # O(n) — but entry_point is at most one node per call
                queue.remove(current)
            else:
                current = queue.popleft()

            result.append(current)
            for neighbor in adj.get(current, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # F-08: Detect nodes that Kahn's algorithm couldn't reach
        # (e.g. decision-edge cycles keeping in_degree > 0).
        unreached = sorted(nid for nid in node_ids if nid not in result)

        # Fallback: append unreached nodes in insertion order
        for nid in node_ids:
            if nid not in result:
                result.append(nid)

        return result, unreached

    def _build_graph(
        self,
        workflow: WorkflowDefinition,
        node_map: dict[str, WorkflowNode],
        resolved_configs: dict[str, dict],
    ) -> tuple[object, list[str]]:
        """Build and compile the LangGraph StateGraph.

        Returns ``(graph, warnings)`` where ``warnings`` collects
        non-fatal issues encountered during edge construction
        (e.g. a non-gate node with multiple non-feedback outgoing
        edges — see M1 fix in Sprint 33).  Callers should surface
        these to the workflow author so silent-fallback issues
        don't go unnoticed.
        """
        graph = StateGraph(WorkflowState)
        warnings: list[str] = []

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
        # Skip wf-phase nodes — they are visual-only containers
        # used for canvas grouping, not executable workflow nodes.
        phase_only_types = {"wf-phase"}
        entry_point = workflow.entry_point

        for node in workflow.nodes:
            if node.type in phase_only_types:
                continue
            node_fn = self._create_node_function(node, resolved_configs)
            graph.add_node(node.id, node_fn)

        # Add a complete node for final output and connect it to END.
        # This node assembles the final output from all node_outputs
        # before the workflow terminates.
        graph.add_node("__complete__", complete_wf_node)
        graph.add_edge("__complete__", END)

        # --- Set entry point ---
        graph.set_entry_point(entry_point)

        # --- Build edge index ---
        # Group edges by source
        edges_by_source: dict[str, list[WorkflowEdge]] = defaultdict(list)
        for edge in workflow.edges:
            edges_by_source[edge.source].append(edge)

        # --- Add edges ---
        for node in workflow.nodes:
            if node.type in phase_only_types:
                continue
            outgoing = edges_by_source.get(node.id, [])

            if not outgoing:
                # Terminal node → __complete__ → END
                # Ensures final output is assembled before termination.
                graph.add_edge(node.id, "__complete__")
                continue

            # Separate edges by type
            non_feedback = [e for e in outgoing if e.type not in ("feedback", "injects_config", "decision")]
            feedback_edges = [e for e in outgoing if e.type == "feedback"]
            decision_edges = [e for e in outgoing if e.type == "decision"]

            # Handle decision edges (transactional drafting approval gate)
            # Must come BEFORE feedback edges, otherwise a node with both (e.g.
            # Moderator) would get route_feedback instead of route_decision.
            if decision_edges:
                # Read max_rounds from termination conditions
                decision_max_rounds = 5
                for tc in workflow.termination_conditions:
                    if tc.type == "max_rounds":
                        decision_max_rounds = tc.value if isinstance(tc.value, int) else 5

                targets: dict[str, object] = {}
                for edge in decision_edges:
                    cond = edge.condition or "approved"
                    # Redirect __end__ through __complete__ so final output is assembled
                    tgt: object = "__complete__" if edge.target in ("__end__", "") else edge.target
                    targets[cond] = tgt

                # Build verdict_map: maps consensus_result['verdict'] values
                # to mapping keys.  Sprint 32 (C3 fix) — derive from the
                # actual decision edges so renamed conditions don't route
                # to the silent "__complete__" fallback any more.
                verdict_map: dict[str, str] = {}
                _known_verdicts = {"approved", "revision_required", "construction_deadlock"}
                for edge in decision_edges:
                    cond = edge.condition or "approved"
                    if cond in _known_verdicts:
                        # Standard conditions map to themselves as mapping
                        # keys — preserving the historical "approved" →
                        # "approved", "revision_required" → "return_to_builder"
                        # contract.
                        verdict_map[cond] = {
                            "approved": "approved",
                            "revision_required": "return_to_builder",
                            "construction_deadlock": "construction_deadlock",
                        }[cond]
                    else:
                        # Custom condition — accept it as both verdict value
                        # and mapping key.  Log a warning so the designer
                        # knows their template uses a non-standard verb.
                        verdict_map[cond] = cond
                        logger.warning(
                            "Decision edge uses custom condition '%s' (not in "
                            "known set %s) — accepting as both verdict value "
                            "and mapping key for node '%s'",
                            cond,
                            sorted(_known_verdicts),
                            node.id,
                        )

                # Build the LangGraph mapping from the verdict_map keys
                # to their actual target nodes.  End-of-debate verdicts
                # (approved, construction_deadlock) terminate via
                # __complete__ so the final output is assembled.
                mapping: dict[str, object] = {}
                for verdict_value, key in verdict_map.items():
                    if verdict_value == "construction_deadlock":
                        mapping[key] = "__complete__"
                    else:
                        target = targets.get(verdict_value, "__complete__")
                        if target == "__complete__" and verdict_value not in targets:
                            logger.warning(
                                "Decision node '%s': verdict '%s' has no matching decision edge — falling back to __complete__",
                                node.id,
                                verdict_value,
                            )
                        mapping[key] = target
                # construction_deadlock is always present (from the
                # verdict_map we built above) but make it explicit.
                if "construction_deadlock" not in mapping:
                    mapping["construction_deadlock"] = "__complete__"

                graph.add_conditional_edges(
                    node.id,
                    route_decision(decision_max_rounds, verdict_map=verdict_map),
                    mapping,
                )

            # Handle gate nodes (conditional routing)
            # Gate nodes with conditional edges use route_conditional.
            # Feedback edges from the same gate are added as the fallback
            # target when no condition matches.
            elif node.type == "wf-gate" and non_feedback:
                conditions = {}
                has_catch_all = False
                for edge in non_feedback:
                    target = edge.target
                    # Redirect __end__ through __complete__ so the final
                    # output is assembled before the workflow terminates.
                    if target in ("__end__", ""):
                        target = "__complete__"
                    condition = edge.condition or "True"
                    conditions[target] = condition
                    if condition.strip() in ("True", "true", "1"):
                        has_catch_all = True

                # 3.2: Warn if no explicit catch-all condition exists —
                # the fallback will be the last condition's target, which
                # is arbitrary and may surprise template authors.
                if not has_catch_all and not feedback_edges:
                    warnings.append(
                        f"Gate node '{node.id}' has no explicit catch-all "
                        f"condition (e.g. 'True') and no feedback edge.  "
                        f"Unmatched conditions will fall back to the last "
                        f"target ('{list(conditions.keys())[-1]}').  "
                        f"Add a 'True' condition to make the fallback explicit."
                    )

                router = route_conditional(conditions, gate_node_id=node.id)
                mapping = {tid: tid for tid in conditions}
                mapping["end"] = END

                # If there's also a feedback edge, use it as the
                # fallback target (no condition matched → loop back)
                if feedback_edges:
                    fb_target = feedback_edges[0].target
                    # Override the route_conditional fallback so that
                    # unmatched conditions go to the feedback target
                    # instead of the last conditional target.
                    _orig_conditions = dict(conditions)

                    def _make_router(conds, fallback_target, gid):
                        async def _router(state):
                            """Router the instance."""
                            from backend.workflow.workflow_routers import _publish_gate_decision

                            session_id = state.get("session_id", "")
                            current_round = state.get("current_round", 1)
                            state_dict = dict(state)
                            evaluations = []
                            for target_node_id, expr in conds.items():
                                try:
                                    result = evaluate_condition(expr, state_dict)
                                    evaluations.append({"condition": expr, "target": target_node_id, "result": result})
                                    if result:
                                        await _publish_gate_decision(
                                            session_id,
                                            gid,
                                            expr,
                                            True,
                                            target_node_id,
                                            False,
                                            evaluations,
                                            current_round,
                                        )
                                        return target_node_id
                                except SafeEvalError:
                                    evaluations.append({"condition": expr, "target": target_node_id, "result": False})
                                except Exception:
                                    evaluations.append({"condition": expr, "target": target_node_id, "result": False})
                            await _publish_gate_decision(
                                session_id,
                                gid,
                                "(none matched)",
                                False,
                                fallback_target,
                                True,
                                evaluations,
                                current_round,
                            )
                            return fallback_target

                        return _router

                    router = _make_router(_orig_conditions, fb_target, node.id)
                    mapping[fb_target] = fb_target

                graph.add_conditional_edges(node.id, router, mapping)

            # Handle feedback edges (non-gate nodes)
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
                    # Redirect __end__ through __complete__ so final output is assembled
                    if exit_target in ("__end__", ""):
                        exit_target = "__complete__"
                    router = route_feedback(max_rounds)
                    graph.add_conditional_edges(
                        node.id,
                        router,
                        {
                            "continue": feedback_target,
                            "exit": exit_target if exit_target != node.id else "__complete__",
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

            # Handle multiple non-feedback, non-gate edges (fan-out)
            elif len(non_feedback) > 1:
                # Fan-out: add edges to ALL targets. LangGraph runs them
                # in parallel and waits at the fan-in node (the gate).
                for edge in non_feedback:
                    graph.add_edge(node.id, edge.target)
                target_ids = [e.target for e in non_feedback]

                # 3.3: Validate fan-out convergence — check whether all
                # targets eventually reach a common downstream node.
                # If they don't, both branches reach __complete__
                # independently, causing duplicate output assembly.
                common = self._find_common_downstream(target_ids, workflow)
                if common:
                    logger.info(
                        "Fan-out from '%s' converges at: %s",
                        node.id,
                        sorted(common),
                    )
                else:
                    warnings.append(
                        f"Node '{node.id}' fans out to {len(non_feedback)} "
                        f"targets ({', '.join(target_ids)}) that do NOT "
                        f"converge to a common downstream node.  Both "
                        f"branches will reach __complete__ independently, "
                        f"resulting in duplicate final output assembly.  "
                        f"Add a shared downstream node (e.g. a wf-gate or "
                        f"join node) to ensure convergence."
                    )
                    logger.warning(
                        "Fan-out from '%s' has no convergence point — targets %s will each reach __complete__ independently",
                        node.id,
                        target_ids,
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

        return graph.compile(), warnings

    def _find_common_downstream(
        self,
        start_ids: list[str],
        workflow: WorkflowDefinition,
    ) -> set[str]:
        """Find nodes reachable from ALL *start_ids* via BFS.

        Performs a reachability search from each start node and returns
        the intersection — i.e. nodes that every fan-out target can
        eventually reach. Used during graph compilation to validate
        that parallel branches converge before reaching ``__complete__``.

        Implicit terminators (``__complete__`` and ``END``) are excluded
        from the result so only *meaningful* convergence points (e.g.
        a shared gate or join node) are reported.

        Args:
            start_ids: Node IDs of the fan-out targets to check.
            workflow: The workflow definition providing the edge graph.

        Returns:
            Set of node IDs reachable from every *start_id*, excluding
            ``__complete__`` and ``END``. An empty set means the
            branches never converge at a meaningful point.
        """
        # Build adjacency from workflow edges (all non-interjection edges)
        adj: dict[str, list[str]] = {}
        for edge in workflow.edges:
            if edge.type != "interjection":
                adj.setdefault(edge.source, []).append(edge.target)

        def _reachable(start: str) -> set[str]:
            visited: set[str] = set()
            queue: deque[str] = deque([start])
            while queue:
                n = queue.popleft()
                if n in visited:
                    continue
                visited.add(n)
                for child in adj.get(n, []):
                    if child not in visited:
                        queue.append(child)
            return visited

        if not start_ids:
            return set()

        sets = [_reachable(tid) for tid in start_ids]
        common = set.intersection(*sets)
        # Exclude __complete__ and END — these are implicit terminators,
        # not "real" convergence points.
        meaningful = common - {"__complete__", "END"}
        return meaningful

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
                threshold = config.get("default_consensus_threshold", 0.7)
                return moderator_node_factory(node.id, config, threshold)
            elif node.type == "wf-agent":
                return agent_node_factory(node.id, "wf-agent", config)
            elif node.type == "wf-builder":
                return builder_node_factory(node.id, config)
            elif node.type == "wf-pragmatist":
                return pragmatist_node_factory(node.id, config)
            elif node.type == "wf-angels-advocate":
                return angels_advocate_node_factory(node.id, config)
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
