"""Blueprint Canvas — CanvasLayout → WorkflowDefinition converter.

Transforms a CanvasLayout's ``layout_data`` (positions + entity references)
into a valid ``WorkflowDefinition`` (nodes, edges, entry_point) that can be
compiled and executed via the workflow engine.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from backend.blueprints.models import (
    CanvasLayout,
    CanvasLayoutData,
    CanvasLayoutEdge,
    CanvasLayoutNode,
)
from backend.blueprints.repository import BlueprintRepository
from backend.blueprints.workflow_models import (
    AGENT_NODE_TYPES,
    TerminationCondition,
    WorkflowDefinition,
    WorkflowEdge,
    WorkflowNode,
)

logger = logging.getLogger(__name__)

# Canvas node types that map to workflow node types.
# Asset-node types (blueprint, llm, role, prompt) are NOT workflow nodes —
# they are references resolved via edges.
CANVAS_TO_WF_NODE_TYPE: dict[str, str] = {
    "wf-input": "wf-input",
    "wf-initialize": "wf-initialize",
    "wf-strategist": "wf-strategist",
    "wf-critic": "wf-critic",
    "wf-fact-checker": "wf-fact-checker",
    "wf-optimizer": "wf-optimizer",
    "wf-moderator": "wf-moderator",
    "wf-analyst": "wf-analyst",
    "wf-creative": "wf-creative",
    "wf-socratic-questioner": "wf-socratic-questioner",
    "wf-expert-reviewer": "wf-expert-reviewer",
    "wf-steel-manner": "wf-steel-manner",
    "wf-devils-advocate": "wf-devils-advocate",
    "wf-troll": "wf-troll",
    "wf-mediator": "wf-mediator",
    "wf-ethicist": "wf-ethicist",
    "wf-synthesizer": "wf-synthesizer",
    "wf-user-injection": "wf-user-injection",
    "wf-gate": "wf-gate",
    "wf-tone-profile": "wf-tone-profile",
    "wf-agent": "wf-agent",
    "wf-phase": "wf-phase",
    "wf-angels-advocate": "wf-angels-advocate",
}

# Asset-node types that should be resolved to their linked workflow node.
ASSET_NODE_TYPES = {
    "agent-blueprint",
    "llm-profile",
    "role-definition",
    "prompt-template",
    "role-type",
    "tone-profile",
}

# Edge types that are valid in a WorkflowDefinition.
VALID_WF_EDGE_TYPES = {"sequential", "conditional", "interjection", "feedback", "injects_config"}


class ConversionError(Exception):
    """Raised when canvas-to-workflow conversion fails."""

    def __init__(self, message: str, errors: list[str] | None = None):
        """Initialise ConversionError."""
        super().__init__(message)
        self.errors = errors or []


class CanvasToWorkflowConverter:
    """Converts a CanvasLayout into a WorkflowDefinition.

    Steps:
    1. Filter canvas nodes to workflow-type nodes only (skip asset nodes)
    2. Map canvas node data to WorkflowNode objects
    3. Resolve agent_blueprint_id from edges (asset → workflow node links)
    4. Map canvas edges to WorkflowEdge objects
    5. Detect entry point
    6. Extract termination conditions
    7. Validate and return WorkflowDefinition
    """

    def __init__(self, repo: BlueprintRepository) -> None:
        """Initialise CanvasToWorkflowConverter."""
        self._repo = repo

    def convert(
        self,
        layout: CanvasLayout,
        name: str | None = None,
        description: str = "",
        max_rounds: int = 5,
        consensus_threshold: float = 0.9,
    ) -> WorkflowDefinition:
        """Convert a canvas layout to a WorkflowDefinition.

        Args:
            layout: The canvas layout to convert.
            name: Workflow name (defaults to layout name).
            description: Optional description.
            max_rounds: Default max rounds for termination.
            consensus_threshold: Default consensus threshold.

        Returns:
            A valid WorkflowDefinition.

        Raises:
            ConversionError: If the canvas has no workflow nodes or validation fails.
        """
        layout_data: CanvasLayoutData = layout.layout_data
        canvas_nodes: list[CanvasLayoutNode] = layout_data.nodes
        canvas_edges: list[CanvasLayoutEdge] = layout_data.edges

        # Separate workflow nodes from asset nodes
        wf_canvas_nodes = [n for n in canvas_nodes if n.type in CANVAS_TO_WF_NODE_TYPE]
        asset_canvas_nodes = [n for n in canvas_nodes if n.type in ASSET_NODE_TYPES]

        if not wf_canvas_nodes:
            raise ConversionError(
                "Canvas has no workflow nodes. Add at least one workflow node (Input, Strategist, Critic, etc.) before converting to a workflow.",
            )

        # Build a set of workflow node IDs for validation
        wf_node_ids = {n.id for n in wf_canvas_nodes}

        # Build a map of asset node ID → asset data for resolving blueprint references
        asset_node_map: dict[str, CanvasLayoutNode] = {n.id: n for n in asset_canvas_nodes}

        # Convert canvas nodes to WorkflowNode objects
        workflow_nodes, agent_blueprint_map = self._convert_nodes(
            wf_canvas_nodes,
            asset_node_map,
            canvas_edges,
        )

        # Convert canvas edges to WorkflowEdge objects
        workflow_edges = self._convert_edges(canvas_edges, wf_node_ids)

        # Detect entry point
        entry_point = self._detect_entry_point(workflow_nodes, workflow_edges)

        # Build termination conditions
        termination_conditions = self._build_termination_conditions(
            workflow_nodes,
            max_rounds,
            consensus_threshold,
        )

        # Build node_blueprint_map for legacy compatibility
        node_blueprint_map: dict[str, str] = {}
        for node in workflow_nodes:
            if node.agent_blueprint_id:
                node_blueprint_map[node.id] = node.agent_blueprint_id
            elif node.bundle_id:
                node_blueprint_map[node.id] = f"bundle:{node.bundle_id}"

        now = datetime.now(UTC)

        wf = WorkflowDefinition(
            id=f"wf-{str(uuid.uuid4())[:8]}",
            name=name or layout.name or "Untitled Workflow",
            description=description,
            canvas_layout_id=layout.id,
            nodes=workflow_nodes,
            edges=workflow_edges,
            entry_point=entry_point,
            termination_conditions=termination_conditions,
            node_blueprint_map=node_blueprint_map,
            tags=[],
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        logger.info(
            "Converted canvas layout '%s' (%s) to workflow '%s' (%s): %d nodes, %d edges, entry_point=%s",
            layout.name,
            layout.id,
            wf.name,
            wf.id,
            len(wf.nodes),
            len(wf.edges),
            wf.entry_point,
        )

        return wf

    def _convert_nodes(
        self,
        wf_canvas_nodes: list[CanvasLayoutNode],
        asset_node_map: dict[str, CanvasLayoutNode],
        canvas_edges: list[CanvasLayoutEdge],
    ) -> tuple[list[WorkflowNode], dict[str, str | None]]:
        """Convert canvas workflow nodes to WorkflowNode objects.

        Also resolves agent_blueprint_id from connected asset nodes via edges.

        Returns:
            Tuple of (workflow_nodes, agent_blueprint_map).
        """
        # Build a map of workflow node ID → connected agent-blueprint ID
        # by scanning edges from asset nodes to workflow nodes
        wf_to_blueprint: dict[str, str | None] = {}
        wf_to_tone: dict[str, str | None] = {}
        for edge in canvas_edges:
            source_asset = asset_node_map.get(edge.source)
            if source_asset and source_asset.type == "agent-blueprint":
                blueprint_id = source_asset.blueprint_id or source_asset.id
                wf_to_blueprint[edge.target] = blueprint_id
            elif source_asset and source_asset.type == "tone-profile":
                tone_id = source_asset.blueprint_id or source_asset.id
                wf_to_tone[edge.target] = tone_id

        nodes = []
        for cn in wf_canvas_nodes:
            node_id = cn.id
            node_type: str = CANVAS_TO_WF_NODE_TYPE.get(cn.type, cn.type)

            # Resolve agent_blueprint_id / bundle_id — priority:
            # 1. node-level agent_blueprint_id field
            # 2. node-level blueprint_id / bundle_id field
            # 3. data dict fallbacks (for round-tripped data)
            # 4. connected asset edge resolution
            agent_blueprint_id: str | None = None
            bundle_id: str | None = None
            if node_type in AGENT_NODE_TYPES:
                if node_type == "wf-agent":
                    bundle_id = cn.data.get("bundle_id") or cn.config.get("bundle_id") or cn.blueprint_id
                    # Fallback: try agent_blueprint_id for legacy compat
                    if not bundle_id:
                        agent_blueprint_id = cn.agent_blueprint_id or cn.data.get("agent_blueprint_id") or wf_to_blueprint.get(node_id)
                else:
                    agent_blueprint_id = (
                        cn.agent_blueprint_id
                        or cn.blueprint_id
                        or cn.data.get("agent_blueprint_id")
                        or cn.data.get("blueprint_id")
                        or wf_to_blueprint.get(node_id)
                    )

            # Extract label — prefer explicit label, then data fallbacks
            label = cn.label or cn.data.get("label", cn.data.get("name", ""))

            # Extract config — prefer explicit config, then data fallbacks
            config: dict = dict(cn.config) if cn.config else {}
            if not config:
                data_config = cn.data.get("config")
                if isinstance(data_config, dict):
                    config = dict(data_config)

            # Type-specific config extraction
            if node_type == "wf-gate" and not config.get("condition"):
                if cn.data.get("condition"):
                    config["condition"] = cn.data["condition"]
            elif node_type == "wf-user-injection" and not config.get("input_type"):
                if cn.data.get("input_type"):
                    config["input_type"] = cn.data["input_type"]
            elif node_type == "wf-tone-profile":
                if not config.get("tone_profile_id") and cn.data.get("tone_profile_id"):
                    config["tone_profile_id"] = cn.data["tone_profile_id"]
                if not config.get("inline_profile") and cn.data.get("inline_profile"):
                    config["inline_profile"] = cn.data["inline_profile"]

            # Resolve tone_profile_id from connected tone-profile asset node
            if node_type in AGENT_NODE_TYPES and not config.get("tone_profile_id"):
                connected_tone = wf_to_tone.get(node_id)
                if connected_tone:
                    config["tone_profile_id"] = connected_tone

            # Position
            position = {"x": cn.x, "y": cn.y}

            # Phase container membership (parent_id from canvas node)
            parent_id = cn.parent_id or cn.data.get("parentId") or None

            try:
                node = WorkflowNode(
                    id=node_id,
                    type=node_type,  # type: ignore[arg-type]
                    label=label,
                    agent_blueprint_id=agent_blueprint_id,
                    bundle_id=bundle_id,
                    parent_id=parent_id,
                    config=config,
                    position=position,
                )
                nodes.append(node)
            except Exception as exc:
                logger.warning(
                    "Skipping canvas node '%s' (type=%s): %s",
                    node_id,
                    node_type,
                    exc,
                )

        return nodes, wf_to_blueprint

    def _convert_edges(
        self,
        canvas_edges: list[CanvasLayoutEdge],
        wf_node_ids: set[str],
    ) -> list[WorkflowEdge]:
        """Convert canvas edges to WorkflowEdge objects.

        Only includes edges where both source and target are workflow nodes.
        """
        edges = []
        for ce in canvas_edges:
            # Only include edges between workflow nodes
            if ce.source not in wf_node_ids or ce.target not in wf_node_ids:
                continue

            edge_type = ce.type if ce.type in VALID_WF_EDGE_TYPES else "sequential"

            # Extract condition/label from data dict
            condition = None
            label = ""
            if isinstance(ce.data, dict):
                condition = ce.data.get("condition")
                label = ce.data.get("label", "")

            try:
                edge = WorkflowEdge(
                    id=ce.id,
                    source=ce.source,
                    target=ce.target,
                    type=edge_type,  # type: ignore[arg-type]
                    condition=condition,
                    label=label,
                )
                edges.append(edge)
            except Exception as exc:
                logger.warning(
                    "Skipping canvas edge '%s' (%s → %s): %s",
                    ce.id,
                    ce.source,
                    ce.target,
                    exc,
                )

        return edges

    def _detect_entry_point(
        self,
        nodes: list[WorkflowNode],
        edges: list[WorkflowEdge],
    ) -> str | None:
        """Detect the entry point node.

        Priority:
        1. Explicit wf-input node
        2. Node with no incoming edges
        3. First node in the list
        """
        # 1. Prefer wf-input
        for node in nodes:
            if node.type == "wf-input":
                return node.id

        # 2. Node with no incoming edges
        incoming_targets = {e.target for e in edges}
        for node in nodes:
            if node.id not in incoming_targets:
                return node.id

        # 3. First node
        return nodes[0].id if nodes else None

    def _build_termination_conditions(
        self,
        nodes: list[WorkflowNode],
        max_rounds: int,
        consensus_threshold: float,
    ) -> list[TerminationCondition]:
        """Build default termination conditions.

        Checks moderator node config for max_rounds and threshold overrides.
        """
        # Check if any moderator node has custom values
        for node in nodes:
            if node.type == "wf-moderator":
                config_max = node.config.get("max_rounds") or node.config.get("default_max_rounds")
                config_thresh = node.config.get("consensus_threshold") or node.config.get("default_consensus_threshold")
                if config_max:
                    max_rounds = int(config_max)
                if config_thresh:
                    consensus_threshold = float(config_thresh)

        return [
            TerminationCondition(
                type="max_rounds",
                value=max_rounds,
                description=f"Stop after {max_rounds} rounds",
            ),
            TerminationCondition(
                type="consensus_reached",
                value=consensus_threshold,
                description=f"Stop when consensus ≥ {consensus_threshold}",
            ),
        ]
