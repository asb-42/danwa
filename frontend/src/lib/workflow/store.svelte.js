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
 *   let nodes = $derived(workflowStore.flowNodes);
 *   let status = $derived(workflowStore.runtimeStatus);
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

  // ─── Derived: Svelte Flow compatible nodes with runtime overlay ───
  get flowNodes() {
    return Array.from(this.graphNodes.values()).map(node => ({
      id: node.id,
      type: node.type,
      data: {
        ...node.data,
        isActive: this.runtimeActiveNodeId === node.id,
      },
      position: node.position || { x: 0, y: 0 },
      className: this.#getNodeClassName(
        this.runtimeActiveNodeId === node.id ? 'active' : node.data?.status
      ),
    }));
  }

  // ─── Derived: Svelte Flow compatible edges with runtime overlay ───
  get flowEdges() {
    return Array.from(this.graphEdges.values()).map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type || 'default',
      animated: this.runtimeActiveEdgeId === edge.id || edge.data?.isActive,
      className: this.#getEdgeClassName(
        this.runtimeActiveEdgeId === edge.id ? 'active' : edge.data?.status
      ),
      data: edge.data,
    }));
  }

  // ─── Derived: Count of pending OOB inputs ───
  get pendingOOBCount() {
    return this.oobQueueItems.filter(o => o.status === 'pending').length;
  }

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
