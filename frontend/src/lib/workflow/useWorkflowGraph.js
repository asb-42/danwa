/**
 * Bridge: Store → Svelte Flow
 *
 * Derived store that provides everything needed by WorkflowCanvas.
 * Automatically triggers ELK layout when topology changes.
 */

import { derived } from 'svelte/store';
import { flowNodes, flowEdges, runtime, dispatchEvent } from './store.js';
import { applyLayout } from './layout.js';

/**
 * Derived store that provides everything needed by WorkflowCanvas.
 * Automatically triggers ELK layout when topology changes.
 */
export const workflowGraph = derived(
  [flowNodes, flowEdges, runtime],
  ([$nodes, $edges, $runtime]) => {
    // Trigger layout recalculation when node/edge count changes
    // (debounced inside applyLayout)
    applyLayout($nodes, $edges);

    return {
      nodes: $nodes,
      edges: $edges,
      status: $runtime.status,
      currentRound: $runtime.currentRound,
      dispatchEvent,
    };
  }
);
