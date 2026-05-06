/**
 * Bridge: Store → Svelte Flow
 *
 * Derived store that provides everything needed by WorkflowCanvas.
 * Layout is triggered externally by WorkflowCanvas via $effect,
 * NOT inside this derived store (side effects in derived() are unreliable).
 */

import { derived } from 'svelte/store';
import { flowNodes, flowEdges, runtime, dispatchEvent } from './store.js';

/**
 * Derived store that provides everything needed by WorkflowCanvas.
 * Pure — no side effects. Layout is triggered separately.
 */
export const workflowGraph = derived(
  [flowNodes, flowEdges, runtime],
  ([$nodes, $edges, $runtime]) => {
    return {
      nodes: $nodes,
      edges: $edges,
      status: $runtime.status,
      currentRound: $runtime.currentRound,
      dispatchEvent,
    };
  }
);
