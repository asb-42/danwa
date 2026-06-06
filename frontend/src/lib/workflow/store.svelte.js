/**
 * Workflow State Store (Svelte 5 Runes)
 *
 * Three layers of state:
 * - Graph (topology): nodes and edges
 * - Runtime (active state): who is active, current round
 * - History (snapshots): round snapshots for timeline
 *
 * Migrated from Svelte 4 writable/derived stores to Svelte 5 $state runes.
 * Eliminates full-array re-renders on derived store changes and removes
 * the need for the _wg hack in WorkflowCanvas.svelte.
 *
 * Usage in components:
 *   import { workflowStore } from './store.svelte.js';
 *   // Direct use — no intermediate $derived needed:
 *   <SvelteFlow nodes={workflowStore.flowNodes} edges={workflowStore.flowEdges} />
 */

import { applyEventToGraph } from './graphReducer.js';
import { applyEventToRuntime } from './runtimeReducer.js';
import { createRoundSnapshot } from './snapshot.js';

class WorkflowStore {
  // ─── Layer 1: Topology (who is connected to whom) ───
  graphNodes = $state(new Map()); // Map<nodeId, WorkflowNode>
  graphEdges = $state(new Map()); // Map<edgeId, WorkflowEdge>

  // ─── Layer 2: Runtime (who is currently active) ───
  runtimeStatus = $state('idle'); // 'idle' | 'running' | 'waiting_for_user' | 'completed'
  runtimeCurrentRound = $state(0);
  runtimeActiveNodeId = $state(null);
  runtimeActiveEdgeId = $state(null);
  runtimeBlockingUserRequestId = $state(null);
  runtimeExecutionPath = $state([]); // Chronological Node-IDs

  // ─── Layer 3: History (for timeline & audit) ───
  roundSnapshots = $state([]); // RoundSnapshot[]
  eventLog = $state([]); // WorkflowEvent[] — Complete audit log

  // ─── OOB Queue ───
  oobQueueItems = $state([]); // OOBInput[]
  oobQueueIndexByTarget = $state(new Map()); // Map<targetKey, OOBInput[]>

  // ─── View Mode ───
  viewMode = $state('current'); // 'current' | 'timeline'

  // ─── Phase Groups (for phase visual grouping) ───
  // Maps child node ID → phase node ID for runtime phase tracking.
  // Populated by loadPhaseGroups().
  #phaseChildMap = new Map(); // Map<childNodeId, phaseNodeId>
  #phaseNodeIds = new Set();  // Set<phaseNodeId>

  // ─── Derived: Svelte Flow compatible nodes with runtime overlay ───
  // $derived.by memoizes the result — only recalculates when dependencies change.
  // This avoids creating a new array on every access (which a getter would do).
  flowNodes = $derived.by(() => {
    // Reading graphNodes and runtimeActiveNodeId establishes reactive dependencies
    const nodes = this.graphNodes;
    const activeId = this.runtimeActiveNodeId;
    const executionPath = this.runtimeExecutionPath;
    const status = this.runtimeStatus;

    // Compute which phase is currently active (contains the active node)
    let activePhaseId = null;
    if (activeId && this.#phaseChildMap.has(activeId)) {
      activePhaseId = this.#phaseChildMap.get(activeId);
    }

    // Compute which phases are completed (all children completed)
    const completedPhases = new Set();
    if (this.#phaseNodeIds.size > 0) {
      for (const phaseId of this.#phaseNodeIds) {
        const children = [...this.#phaseChildMap.entries()]
          .filter(([, pid]) => pid === phaseId)
          .map(([cid]) => cid);
        if (children.length > 0) {
          const allCompleted = children.every(cid => {
            const childNode = nodes.get(cid);
            return childNode?.data?.status === 'completed';
          });
          if (allCompleted) completedPhases.add(phaseId);
        }
      }
    }

    return Array.from(nodes.values()).map(node => {
      const isNodeActive = activeId === node.id;
      const isPhase = this.#phaseNodeIds.has(node.id);
      const parentId = node.parentId || this.#phaseChildMap.get(node.id) || null;

      // Svelte Flow requires child positions relative to the parent.
      // Convert absolute positions to relative when a node has a parentId.
      let position = node.position || { x: 0, y: 0 };
      if (parentId) {
        const parentNode = nodes.get(parentId);
        if (parentNode?.position) {
          position = {
            x: position.x - parentNode.position.x,
            y: position.y - parentNode.position.y,
          };
        }
      }

      return {
        id: node.id,
        type: node.type,
        parentId,
        data: {
          ...node.data,
          isActive: isNodeActive,
          ...(isPhase ? {
            isActive: activePhaseId === node.id,
            isCompleted: completedPhases.has(node.id),
          } : {}),
        },
        position,
        className: this.#getNodeClassName(
          isNodeActive ? 'active' : node.data?.status
        ),
      };
    });
  });

  // ─── Derived: Svelte Flow compatible edges with runtime overlay ───
  flowEdges = $derived.by(() => {
    const edges = this.graphEdges;
    const activeEdgeId = this.runtimeActiveEdgeId;
    return Array.from(edges.values()).map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type || 'default',
      animated: activeEdgeId === edge.id || edge.data?.isActive,
      className: this.#getEdgeClassName(
        activeEdgeId === edge.id ? 'active' : edge.data?.status
      ),
      data: edge.data,
    }));
  });

  // ─── Derived: Count of pending OOB inputs ───
  pendingOOBCount = $derived.by(() => {
    return this.oobQueueItems.filter(o => o.status === 'pending').length;
  });

  // ─── Actions ───

  /**
   * Dispatch a workflow event — updates graph, runtime, and history.
   * This is the single entry point for all state mutations.
   * @param {import('./events.js').WorkflowEvent} event
   */
  dispatchEvent(event) {
    // 1. Event into audit log
    this.eventLog = [...this.eventLog, event];

    // 2. Graph mutation
    applyEventToGraph(this, event);

    // 3. Runtime update
    applyEventToRuntime(this, event);

    // 4. On round completion: create snapshot
    if (event.type === 'ROUND_COMPLETED') {
      createRoundSnapshot(this, event.payload.round);
    }
  }

  /** Reset all workflow state */
  resetWorkflow() {
    this.graphNodes = new Map();
    this.graphEdges = new Map();
    this.runtimeStatus = 'idle';
    this.runtimeCurrentRound = 0;
    this.runtimeActiveNodeId = null;
    this.runtimeActiveEdgeId = null;
    this.runtimeBlockingUserRequestId = null;
    this.runtimeExecutionPath = [];
    this.roundSnapshots = [];
    this.eventLog = [];
    this.oobQueueItems = [];
    this.oobQueueIndexByTarget = new Map();
    this.viewMode = 'current';
    this.#phaseChildMap = new Map();
    this.#phaseNodeIds = new Set();
  }

  /**
   * Load phase group nodes from a workflow definition.
   *
   * Creates `wf-phase` group nodes in graphNodes and records parent
   * relationships so that the flowNodes derived can compute parentId,
   * active phase, and phase completion at runtime.
   *
   * Call this BEFORE debate execution starts — typically when the
   * workflow definition is fetched (e.g. via mapper or SSE init).
   *
   * @param {Object} definition - Workflow definition with nodes and phase_configs
   * @param {Object} [definition.phase_configs] - Map of phaseId → { name, color, description, roles, max_rounds }
   * @param {Array}  [definition.nodes] - Workflow nodes (may include wf-phase entries and parent_id refs)
   */
  loadPhaseGroups(definition) {
    if (!definition) return;

    const phaseNodes = (definition.nodes || []).filter(n => n.type === 'wf-phase');
    const phaseConfigs = definition.phase_configs || {};

    // Add phase group nodes to graphNodes
    for (const pn of phaseNodes) {
      const config = phaseConfigs[pn.id] || pn.config || {};
      const phaseId = pn.id;

      this.#phaseNodeIds.add(phaseId);

      this.graphNodes.set(phaseId, {
        id: phaseId,
        type: 'phase', // Canvas-side type (mapped from wf-phase)
        parentId: null,
        data: {
          name: config.name || pn.label || 'Phase',
          label: config.name || pn.label || 'Phase',
          color: config.color || pn.config?.color || '#6366f1',
          description: config.description || pn.config?.description || '',
          roles: config.roles || [],
          max_rounds: config.max_rounds || 3,
          isActive: false,
          isCompleted: false,
        },
        position: pn.position || { x: 0, y: 0 },
      });
    }

    // Build parent_id → parentId mapping for agent nodes
    for (const node of (definition.nodes || [])) {
      const parentId = node.parent_id;
      if (parentId && this.#phaseNodeIds.has(parentId)) {
        this.#phaseChildMap.set(node.id, parentId);
        // If the node already exists in graphNodes (from an earlier SSE event),
        // set its parentId so Svelte Flow nests it inside the phase group.
        const existing = this.graphNodes.get(node.id);
        if (existing) {
          existing.parentId = parentId;
        }
      }
    }
  }

  /**
   * Get the phase node ID that contains a given child node.
   * @param {string} nodeId
   * @returns {string|null}
   */
  getPhaseForNode(nodeId) {
    return this.#phaseChildMap.get(nodeId) || null;
  }

  // ─── Helpers ───

  #getNodeClassName(status) {
    const map = {
      idle: 'node-idle',
      active: 'node-active',
      completed: 'node-completed',
      error: 'node-error',
      waiting: 'node-waiting',
      draft: 'node-draft',
      final: 'node-final',
      resolved: 'node-resolved',
      passed: 'node-passed',
      below: 'node-below',
    };
    return map[status] || 'node-idle';
  }

  #getEdgeClassName(status) {
    const map = {
      idle: 'edge-idle',
      active: 'edge-active',
      completed: 'edge-completed',
    };
    return map[status] || 'edge-idle';
  }
}

/** Singleton workflow store instance. */
export const workflowStore = new WorkflowStore();

// ─── Named exports for backward compatibility ───
export const dispatchEvent = workflowStore.dispatchEvent.bind(workflowStore);
export const resetWorkflow = workflowStore.resetWorkflow.bind(workflowStore);
