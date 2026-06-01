/**
 * Blueprint Canvas state store using Svelte 5 runes.
 *
 * Single source of truth for canvas nodes, edges, and selection.
 * Follows the class-based rune store pattern for shared reactive state.
 * Supports Blueprint Mode (Phase 3) and Workflow Mode (Phase 4).
 */

import { getNodeRegistration, getEdgeRegistration } from './registry.js';

class BlueprintCanvasStore {
  /** @type {import('@xyflow/svelte').Node[]} */
  nodes = $state([]);

  /** @type {import('@xyflow/svelte').Edge[]} */
  edges = $state([]);

  /** @type {string|null} */
  selectedNodeId = $state(null);

  /** @type {string|null} */
  currentLayoutId = $state(null);

  /** @type {string|null} */
  currentLayoutName = $state(null);

  /** @type {boolean} */
  isDirty = $state(false);

  /** @type {'blueprint'|'workflow'} */
  mode = $state('blueprint');

  /** @type {boolean} */
  isLoading = $state(false);

  /** @type {string|null} */
  error = $state(null);

  /** @type {string|null} — Linked WorkflowDefinition ID (set after "Save as Workflow") */
  currentWorkflowId = $state(null);

  /** @returns {import('@xyflow/svelte').Node|null} */
  get selectedNode() {
    return this.nodes.find((n) => n.id === this.selectedNodeId) || null;
  }

  // ─── Node mutations ───────────────────────────────────────────────

  /**
   * Add a node to the canvas.
   * @param {import('@xyflow/svelte').Node} node
   */
  addNode(node) {
    this.nodes = [...this.nodes, node];
    this.isDirty = true;
  }

  /**
   * Remove a node and all connected edges.
   * @param {string} nodeId
   */
  removeNode(nodeId) {
    this.nodes = this.nodes.filter((n) => n.id !== nodeId);
    this.edges = this.edges.filter(
      (e) => e.source !== nodeId && e.target !== nodeId,
    );
    if (this.selectedNodeId === nodeId) {
      this.selectedNodeId = null;
    }
    this.isDirty = true;
  }

  /**
   * Update data properties of a specific node.
   * @param {string} nodeId
   * @param {Record<string, any>} data
   */
  updateNodeData(nodeId, data) {
    this.nodes = this.nodes.map((n) =>
      n.id === nodeId ? { ...n, data: { ...n.data, ...data } } : n,
    );
    this.isDirty = true;
  }

  /**
   * Update position of a specific node (used after drag).
   * @param {string} nodeId
   * @param {{ x: number, y: number }} position
   */
  updateNodePosition(nodeId, position) {
    this.nodes = this.nodes.map((n) =>
      n.id === nodeId ? { ...n, position } : n,
    );
    this.isDirty = true;
  }

  /**
   * Update position and parentId of a specific node atomically.
   * @param {string} nodeId
   * @param {{ x: number, y: number }} position
   * @param {string|null} parentId
   */
  updateNode(nodeId, position, parentId) {
    this.nodes = this.nodes.map((n) =>
      n.id === nodeId ? { ...n, position, parentId } : n,
    );
    this.isDirty = true;
  }

  // ─── Edge mutations ───────────────────────────────────────────────

  /**
   * Add an edge to the canvas.
   * @param {import('@xyflow/svelte').Edge} edge
   */
  addEdge(edge) {
    // Prevent duplicate edges
    const exists = this.edges.some(
      (e) => e.source === edge.source && e.target === edge.target && e.type === edge.type,
    );
    if (exists) return;
    this.edges = [...this.edges, edge];
    this.isDirty = true;
  }

  /**
   * Remove an edge by ID.
   * @param {string} edgeId
   */
  removeEdge(edgeId) {
    this.edges = this.edges.filter((e) => e.id !== edgeId);
    this.isDirty = true;
  }

  // ─── Selection ────────────────────────────────────────────────────

  /**
   * Select a node by ID (or null to deselect).
   * @param {string|null} nodeId
   */
  selectNode(nodeId) {
    this.selectedNodeId = nodeId;
  }

  /** Clear the current selection. */
  clearSelection() {
    this.selectedNodeId = null;
  }

  // ─── Serialization ────────────────────────────────────────────────

  /**
   * Serialize the current canvas state to the CanvasLayout API format.
   * @returns {{ nodes: Array, edges: Array }}
   */
  toLayoutJson() {
    return {
      nodes: this.nodes.map((n) => ({
        id: n.id,
        type: n.type,
        x: n.position?.x ?? 0,
        y: n.position?.y ?? 0,
        parent_id: n.parentId || null,
        blueprint_id: n.data?.blueprint_id || n.id,
        // Persist workflow-relevant data for canvas-to-workflow conversion
        label: n.data?.label || n.data?.name || '',
        config: n.data?.config || {},
        agent_blueprint_id: n.data?.agent_blueprint_id || null,
        data: n.data || {},
      })),
      edges: this.edges.map((e) => ({
        id: e.id,
        source: e.source,
        sourceHandle: e.sourceHandle || null,
        target: e.target,
        targetHandle: e.targetHandle || null,
        type: e.type,
        data: e.data || {},
      })),
    };
  }

  /**
   * Load canvas state from a layout JSON + blueprint data.
   * @param {{ nodes: Array, edges: Array }} layoutJson
   * @param {Record<string, any>} entityDataMap - Map of entity ID → entity data
   */
  loadFromLayout(layoutJson, entityDataMap = {}) {
    const nodeTypeMap = {
      'agent-blueprint': 'agent-blueprint',
      'llm-profile': 'llm-profile',
      'role-definition': 'role-definition',
      'prompt-template': 'prompt-template',
      'role-type': 'role-type',
      'wf-input': 'wf-input',
      'wf-initialize': 'wf-initialize',
      'wf-strategist': 'wf-strategist',
      'wf-critic': 'wf-critic',
      'wf-optimizer': 'wf-optimizer',
      'wf-moderator': 'wf-moderator',
      'wf-fact-checker': 'wf-fact-checker',
      'wf-analyst': 'wf-analyst',
      'wf-creative': 'wf-creative',
      'wf-socratic-questioner': 'wf-socratic-questioner',
      'wf-expert-reviewer': 'wf-expert-reviewer',
      'wf-steel-manner': 'wf-steel-manner',
      'wf-devils-advocate': 'wf-devils-advocate',
      'wf-troll': 'wf-troll',
      'wf-mediator': 'wf-mediator',
      'wf-ethicist': 'wf-ethicist',
      'wf-synthesizer': 'wf-synthesizer',
      'wf-user-injection': 'wf-user-injection',
      'wf-gate': 'wf-gate',
      'wf-tone-profile': 'wf-tone-profile',
      'wf-agent': 'wf-agent',
      'wf-builder': 'wf-builder',
      'wf-pragmatist': 'wf-pragmatist',
      'wf-angels-advocate': 'wf-angels-advocate',
      'wf-phase': 'wf-phase',
      'tone-profile': 'tone-profile',
    };

    this.nodes = (layoutJson.nodes || []).map((n) => ({
      id: n.id,
      type: nodeTypeMap[n.type] || n.type,
      position: { x: n.x ?? 0, y: n.y ?? 0 },
      parentId: n.parent_id || null,
      data: {
        ...(entityDataMap[n.blueprint_id || n.id] || {}),

         // Preserve layout-level fields when entity data is unavailable
         ...(n.label && !(entityDataMap[n.blueprint_id || n.id] || {}).name ? { name: n.label } : {}),
         ...(n.config && Object.keys(n.config).length > 0 && !(entityDataMap[n.blueprint_id || n.id] || {}).config ? { config: n.config } : {}),
        blueprint_id: n.blueprint_id || n.id,
        isDraft: false,
      },
    }));

    this.edges = (layoutJson.edges || []).map((e) => ({
      id: e.id,
      source: e.source,
      sourceHandle: e.sourceHandle ?? e.source_handle ?? null,
      target: e.target,
      targetHandle: e.targetHandle ?? e.target_handle ?? null,
      type: e.type,
      data: e.data ?? {},
    }));

    this.isDirty = false;
  }

  // ─── Bulk operations ──────────────────────────────────────────────

  /**
   * Replace all nodes (used by auto-layout).
   * @param {import('@xyflow/svelte').Node[]} nodes
   */
  setNodes(nodes) {
    this.nodes = nodes;
    this.isDirty = true;
  }

  /**
   * Replace all edges.
   * @param {import('@xyflow/svelte').Edge[]} edges
   */
  setEdges(edges) {
    this.edges = edges;
    this.isDirty = true;
  }

  // ─── Mode switching ──────────────────────────────────────────────

  /**
   * Switch between Blueprint and Workflow mode.
   * When switching to blueprint mode, removes workflow-only nodes/edges.
   * @param {'blueprint'|'workflow'} newMode
   */
  setMode(newMode) {
    if (newMode === this.mode) return;
    this.mode = newMode;

    // When switching to blueprint mode, remove any workflow-only nodes
    if (newMode === 'blueprint') {
      this.nodes = this.nodes.filter((n) => {
        const reg = getNodeRegistration(n.type);
        return reg?.category === 'asset';
      });
      this.edges = this.edges.filter((e) => {
        const reg = getEdgeRegistration(e.type);
        return reg?.category === 'semantic';
      });
    }
  }

  /** Reset the entire canvas state. */
  reset() {
    this.nodes = [];
    this.edges = [];
    this.selectedNodeId = null;
    this.currentLayoutId = null;
    this.currentLayoutName = null;
    this.currentWorkflowId = null;
    this.isDirty = false;
    this.error = null;
    this.mode = 'blueprint';
  }
}

/** Singleton canvas store instance. */
export const canvasStore = new BlueprintCanvasStore();
