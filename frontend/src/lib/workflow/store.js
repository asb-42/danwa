/**
 * Workflow State Store (Svelte Stores)
 *
 * Three layers of state:
 * - Graph (topology): nodes and edges
 * - Runtime (active state): who is active, current round
 * - History (snapshots): round snapshots for timeline
 */

import { writable, derived, get } from 'svelte/store';

// ─── Layer 1: Topology (who is connected to whom) ───
export const graphNodes = writable(new Map()); // Map<nodeId, WorkflowNode>
export const graphEdges = writable(new Map()); // Map<edgeId, WorkflowEdge>

// ─── Layer 2: Runtime (who is currently active) ───
export const runtime = writable({
  status: 'idle', // 'idle' | 'running' | 'waiting_for_user' | 'completed'
  currentRound: 0,
  activeNodeId: null,
  activeEdgeId: null,
  blockingUserRequestId: null,
  executionPath: [], // Chronological Node-IDs
});

// ─── Layer 3: History (for timeline & audit) ───
export const roundSnapshots = writable([]); // RoundSnapshot[]
export const eventLog = writable([]); // WorkflowEvent[] — Complete audit log

// ─── OOB Queue ───
export const oobQueue = writable({
  items: [], // OOBInput[]
  indexByTarget: new Map(), // Map<targetKey, OOBInput[]>
});

// ─── View Mode ───
export const viewMode = writable('current'); // 'current' | 'timeline'

// ─── Derived Stores ───

/** Svelte Flow compatible nodes with runtime overlay */
export const flowNodes = derived(
  [graphNodes, runtime],
  ([$nodes, $runtime]) => {
    return Array.from($nodes.values()).map(node => ({
      id: node.id,
      type: node.type,
      data: {
        ...node.data,
        isActive: $runtime.activeNodeId === node.id,
      },
      position: node.position || { x: 0, y: 0 },
      className: getNodeClassName(
        $runtime.activeNodeId === node.id ? 'active' : node.data.status
      ),
    }));
  }
);

/** Svelte Flow compatible edges with runtime overlay */
export const flowEdges = derived(
  [graphEdges, runtime],
  ([$edges, $runtime]) => {
    return Array.from($edges.values()).map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type || 'default',
      animated: $runtime.activeEdgeId === edge.id || edge.data?.isActive,
      className: getEdgeClassName(
        $runtime.activeEdgeId === edge.id ? 'active' : edge.data?.status
      ),
      data: edge.data,
    }));
  }
);

/** Count of pending OOB inputs */
export const pendingOOBCount = derived(oobQueue, ($oob) =>
  $oob.items.filter(o => o.status === 'pending').length
);

// ─── Actions ───

/**
 * Dispatch a workflow event — updates graph, runtime, and history.
 * This is the single entry point for all state mutations.
 * @param {import('./events.js').WorkflowEvent} event
 */
export function dispatchEvent(event) {
  // 1. Event into audit log
  eventLog.update(log => [...log, event]);

  // 2. Graph mutation
  applyEventToGraph(event);

  // 3. Runtime update
  applyEventToRuntime(event);

  // 4. On round completion: create snapshot
  if (event.type === 'ROUND_COMPLETED') {
    createRoundSnapshot(event.payload.round);
  }
}

/** Reset all workflow state */
export function resetWorkflow() {
  graphNodes.set(new Map());
  graphEdges.set(new Map());
  runtime.set({
    status: 'idle', currentRound: 0, activeNodeId: null,
    activeEdgeId: null, blockingUserRequestId: null, executionPath: [],
  });
  roundSnapshots.set([]);
  eventLog.set([]);
  oobQueue.set({ items: [], indexByTarget: new Map() });
}

// ─── Helpers ───

function getNodeClassName(status) {
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

function getEdgeClassName(status) {
  const map = {
    idle: 'edge-idle',
    active: 'edge-active',
    completed: 'edge-completed',
  };
  return map[status] || 'edge-idle';
}

// Import reducers (will be created next)
// These are imported lazily to avoid circular dependencies at module load time.
// The actual imports happen at the bottom of this file after all stores are defined.

import { applyEventToGraph } from './graphReducer.js';
import { applyEventToRuntime } from './runtimeReducer.js';
import { createRoundSnapshot } from './snapshot.js';
